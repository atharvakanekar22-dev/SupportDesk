import io
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Attachment, Comment, Ticket, TicketHistory

User = get_user_model()


class TicketWorkflowModelTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="cust", password="pwd", role=User.Role.CUSTOMER
        )
        self.agent = User.objects.create_user(
            username="ag1", password="pwd", role=User.Role.AGENT
        )
        self.admin = User.objects.create_user(
            username="adm", password="pwd", role=User.Role.ADMIN
        )

    def test_ticket_number_generation(self):
        ticket = Ticket.objects.create(
            customer=self.customer,
            subject="Cannot connect to VPN",
            description="VPN times out after 30 seconds",
            priority=Ticket.Priority.HIGH,
        )
        self.assertTrue(ticket.ticket_number.startswith("TKT-"))
        self.assertEqual(ticket.status, Ticket.Status.OPEN)

    def test_valid_workflow_transitions(self):
        ticket = Ticket.objects.create(
            customer=self.customer,
            subject="Email not syncing",
            description="IMAP error 500",
            priority=Ticket.Priority.MEDIUM,
        )
        # 1. OPEN -> ASSIGNED
        self.assertTrue(ticket.can_transition_to(Ticket.Status.ASSIGNED))
        ticket.transition_to(Ticket.Status.ASSIGNED, changed_by=self.admin)
        self.assertEqual(ticket.status, Ticket.Status.ASSIGNED)

        # 2. ASSIGNED -> IN_PROGRESS
        self.assertTrue(ticket.can_transition_to(Ticket.Status.IN_PROGRESS))
        ticket.transition_to(Ticket.Status.IN_PROGRESS, changed_by=self.agent)
        self.assertEqual(ticket.status, Ticket.Status.IN_PROGRESS)

        # 3. IN_PROGRESS -> RESOLVED
        self.assertTrue(ticket.can_transition_to(Ticket.Status.RESOLVED))
        ticket.transition_to(Ticket.Status.RESOLVED, changed_by=self.agent)
        self.assertEqual(ticket.status, Ticket.Status.RESOLVED)

        # 4. RESOLVED -> CLOSED
        self.assertTrue(ticket.can_transition_to(Ticket.Status.CLOSED))
        ticket.transition_to(Ticket.Status.CLOSED, changed_by=self.admin)
        self.assertEqual(ticket.status, Ticket.Status.CLOSED)

        # 5. History recorded for all transitions
        history_actions = list(ticket.history.values_list("action", flat=True))
        self.assertEqual(len(history_actions), 4)

    def test_invalid_transitions_are_rejected(self):
        ticket = Ticket.objects.create(
            customer=self.customer,
            subject="Printer offline",
            description="Network printer not found",
            priority=Ticket.Priority.LOW,
        )
        # OPEN -> CLOSED must be rejected
        self.assertFalse(ticket.can_transition_to(Ticket.Status.CLOSED))
        with self.assertRaises(ValidationError):
            ticket.transition_to(Ticket.Status.CLOSED, changed_by=self.admin)

        # OPEN -> RESOLVED must be rejected
        self.assertFalse(ticket.can_transition_to(Ticket.Status.RESOLVED))
        with self.assertRaises(ValidationError):
            ticket.transition_to(Ticket.Status.RESOLVED, changed_by=self.admin)

        # Transition to ASSIGNED
        ticket.transition_to(Ticket.Status.ASSIGNED, changed_by=self.admin)

        # ASSIGNED -> CLOSED must be rejected
        self.assertFalse(ticket.can_transition_to(Ticket.Status.CLOSED))
        with self.assertRaises(ValidationError):
            ticket.transition_to(Ticket.Status.CLOSED, changed_by=self.admin)

        # Advance to RESOLVED
        ticket.transition_to(Ticket.Status.IN_PROGRESS, changed_by=self.agent)
        ticket.transition_to(Ticket.Status.RESOLVED, changed_by=self.agent)

        # RESOLVED -> IN_PROGRESS must be rejected
        self.assertFalse(ticket.can_transition_to(Ticket.Status.IN_PROGRESS))
        with self.assertRaises(ValidationError):
            ticket.transition_to(Ticket.Status.IN_PROGRESS, changed_by=self.agent)

        # Close ticket
        ticket.transition_to(Ticket.Status.CLOSED, changed_by=self.admin)

        # CLOSED is terminal
        self.assertFalse(ticket.can_transition_to(Ticket.Status.OPEN))
        with self.assertRaises(ValidationError):
            ticket.transition_to(Ticket.Status.OPEN, changed_by=self.admin)


class AttachmentValidationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="cust", password="pwd", role=User.Role.CUSTOMER
        )
        self.ticket = Ticket.objects.create(
            customer=self.customer,
            subject="Test ticket",
            description="Testing attachments",
            priority=Ticket.Priority.LOW,
        )

    def test_safe_attachment_allowed(self):
        file = SimpleUploadedFile("log.txt", b"error log content", content_type="text/plain")
        attachment = Attachment(
            ticket=self.ticket,
            uploaded_by=self.customer,
            file=file,
        )
        attachment.full_clean()
        attachment.save()
        self.assertEqual(attachment.original_filename, "log.txt")

    def test_executable_attachment_rejected(self):
        file = SimpleUploadedFile("malicious.exe", b"binarycontent", content_type="application/octet-stream")
        attachment = Attachment(
            ticket=self.ticket,
            uploaded_by=self.customer,
            file=file,
        )
        with self.assertRaises(ValidationError):
            attachment.full_clean()


class TicketViewPermissionTests(TestCase):
    def setUp(self):
        self.cust1 = User.objects.create_user(
            username="cust1", password="pwd", role=User.Role.CUSTOMER
        )
        self.cust2 = User.objects.create_user(
            username="cust2", password="pwd", role=User.Role.CUSTOMER
        )
        self.agent1 = User.objects.create_user(
            username="agent1", password="pwd", role=User.Role.AGENT
        )
        self.agent2 = User.objects.create_user(
            username="agent2", password="pwd", role=User.Role.AGENT
        )
        self.admin = User.objects.create_user(
            username="admin", password="pwd", role=User.Role.ADMIN
        )

        self.ticket1 = Ticket.objects.create(
            customer=self.cust1,
            assigned_agent=self.agent1,
            subject="Cust1 Ticket",
            description="Issue 1 description",
            priority=Ticket.Priority.HIGH,
            status=Ticket.Status.ASSIGNED,
        )
        self.ticket2 = Ticket.objects.create(
            customer=self.cust2,
            assigned_agent=self.agent2,
            subject="Cust2 Ticket",
            description="Issue 2 description",
            priority=Ticket.Priority.LOW,
            status=Ticket.Status.ASSIGNED,
        )

    def test_customer_ticket_creation(self):
        self.client.force_login(self.cust1)
        response = self.client.post(
            reverse("tickets:ticket_create"),
            {
                "subject": "New Laptop Request",
                "description": "Need developer laptop with 32GB RAM",
                "priority": Ticket.Priority.MEDIUM,
            },
        )
        self.assertEqual(response.status_code, 302)
        new_ticket = Ticket.objects.get(subject="New Laptop Request")
        self.assertEqual(new_ticket.customer, self.cust1)
        self.assertEqual(new_ticket.status, Ticket.Status.OPEN)
        self.assertTrue(new_ticket.history.filter(action="Ticket created.").exists())

    def test_customer_scoping_in_list(self):
        self.client.force_login(self.cust1)
        response = self.client.get(reverse("tickets:ticket_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cust1 Ticket")
        self.assertNotContains(response, "Cust2 Ticket")

    def test_customer_cannot_view_other_customer_ticket(self):
        self.client.force_login(self.cust1)
        # Direct URL tampering: cust1 attempts to view cust2's ticket
        response = self.client.get(reverse("tickets:ticket_detail", args=[self.ticket2.pk]))
        self.assertEqual(response.status_code, 403)

    def test_agent_scoping_in_list(self):
        self.client.force_login(self.agent1)
        response = self.client.get(reverse("tickets:ticket_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cust1 Ticket")
        self.assertNotContains(response, "Cust2 Ticket")

    def test_agent_cannot_view_other_agent_ticket(self):
        self.client.force_login(self.agent1)
        # Direct URL tampering: agent1 attempts to view agent2's ticket
        response = self.client.get(reverse("tickets:ticket_detail", args=[self.ticket2.pk]))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_view_all_tickets(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("tickets:ticket_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cust1 Ticket")
        self.assertContains(response, "Cust2 Ticket")

    def test_admin_assignment_transitions_open_ticket(self):
        open_ticket = Ticket.objects.create(
            customer=self.cust1,
            subject="Unassigned issue",
            description="Needs attention",
            priority=Ticket.Priority.CRITICAL,
            status=Ticket.Status.OPEN,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("tickets:ticket_assign", args=[open_ticket.pk]),
            {"assigned_agent": self.agent1.pk},
        )
        self.assertEqual(response.status_code, 302)
        open_ticket.refresh_from_db()
        self.assertEqual(open_ticket.assigned_agent, self.agent1)
        self.assertEqual(open_ticket.status, Ticket.Status.ASSIGNED)
        self.assertTrue(open_ticket.history.filter(action__icontains="Assigned to").exists())

    def test_customer_cannot_assign_ticket(self):
        self.client.force_login(self.cust1)
        response = self.client.post(
            reverse("tickets:ticket_assign", args=[self.ticket1.pk]),
            {"assigned_agent": self.agent1.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_agent_advances_workflow(self):
        self.client.force_login(self.agent1)
        # Advance ASSIGNED -> IN_PROGRESS
        response = self.client.post(
            reverse("tickets:ticket_change_status", args=[self.ticket1.pk]),
            {"new_status": Ticket.Status.IN_PROGRESS},
        )
        self.assertEqual(response.status_code, 302)
        self.ticket1.refresh_from_db()
        self.assertEqual(self.ticket1.status, Ticket.Status.IN_PROGRESS)

    def test_comment_added_and_recorded_in_history(self):
        self.client.force_login(self.cust1)
        response = self.client.post(
            reverse("tickets:ticket_add_comment", args=[self.ticket1.pk]),
            {"content": "Any update on this request?"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.ticket1.comments.filter(content="Any update on this request?").exists())
        self.assertTrue(self.ticket1.history.filter(action="Comment added.").exists())

    def test_customer_cannot_modify_closed_ticket(self):
        closed_ticket = Ticket.objects.create(
            customer=self.cust1,
            subject="Closed ticket",
            description="All done",
            priority=Ticket.Priority.LOW,
            status=Ticket.Status.CLOSED,
        )
        self.client.force_login(self.cust1)
        # Attempt comment on closed ticket
        response = self.client.post(
            reverse("tickets:ticket_add_comment", args=[closed_ticket.pk]),
            {"content": "Trying to reopen"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(closed_ticket.comments.filter(content="Trying to reopen").exists())

    def test_search_and_filtering(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("tickets:ticket_list"),
            {"q": "Cust1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cust1 Ticket")
        self.assertNotContains(response, "Cust2 Ticket")

    def test_dashboards_render_real_metrics(self):
        # Admin dashboard
        self.client.force_login(self.admin)
        res = self.client.get(reverse("core:admin_dashboard"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["metrics"]["total"], 2)

        # Agent dashboard
        self.client.force_login(self.agent1)
        res = self.client.get(reverse("core:agent_dashboard"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["metrics"]["total_assigned"], 1)

        # Customer dashboard
        self.client.force_login(self.cust1)
        res = self.client.get(reverse("core:customer_dashboard"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["metrics"]["total"], 1)
