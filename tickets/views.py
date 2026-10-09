from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    AttachmentForm,
    CommentForm,
    TicketAssignForm,
    TicketCreateForm,
    TicketFilterForm,
    TicketStatusTransitionForm,
)
from .models import Attachment, Comment, Ticket, TicketHistory

User = get_user_model()


def get_user_ticket_or_403(user, ticket_id):
    """
    Fetch a Ticket by ID and verify the requesting user's authorization.
    Returns (ticket, None) if authorized, or (None, response) with HTTP 403.
    """
    ticket = get_object_or_404(
        Ticket.objects.select_related("customer", "assigned_agent"),
        pk=ticket_id,
    )

    if user.role == User.Role.ADMIN:
        return ticket, None

    if user.role == User.Role.AGENT:
        if ticket.assigned_agent_id == user.id:
            return ticket, None
        return None, render(None, "403.html", status=403)

    if user.role == User.Role.CUSTOMER:
        if ticket.customer_id == user.id:
            return ticket, None
        return None, render(None, "403.html", status=403)

    return None, render(None, "403.html", status=403)


@login_required
def ticket_list(request):
    """
    Display tickets filtered by role permissions, status, priority, and search keyword.
    """
    user = request.user

    # Base queryset scoped by role
    if user.role == User.Role.ADMIN:
        qs = Ticket.objects.all().select_related("customer", "assigned_agent")
        show_agent_filter = True
    elif user.role == User.Role.AGENT:
        qs = Ticket.objects.filter(assigned_agent=user).select_related("customer", "assigned_agent")
        show_agent_filter = False
    else:  # CUSTOMER
        qs = Ticket.objects.filter(customer=user).select_related("customer", "assigned_agent")
        show_agent_filter = False

    filter_form = TicketFilterForm(request.GET or None, show_agent=show_agent_filter)

    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        status = filter_form.cleaned_data.get("status")
        priority = filter_form.cleaned_data.get("priority")
        agent = filter_form.cleaned_data.get("agent") if show_agent_filter else None

        if q:
            qs = qs.filter(
                Q(ticket_number__icontains=q)
                | Q(subject__icontains=q)
                | Q(description__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if agent:
            qs = qs.filter(assigned_agent=agent)

    qs = qs.order_by("-created_at")

    context = {
        "tickets": qs,
        "filter_form": filter_form,
        "total_count": qs.count(),
    }
    return render(request, "tickets/ticket_list.html", context)


@login_required
def ticket_create(request):
    """
    Allow Customers (and Admins) to create a new ticket.
    Initial status is always OPEN and customer is set automatically.
    """
    if request.user.role == User.Role.AGENT:
        # Agents do not create tickets on behalf of customers in this workflow
        messages.error(request, "Support agents cannot create new customer tickets.")
        return redirect("tickets:ticket_list")

    if request.method == "POST":
        form = TicketCreateForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.customer = request.user
            ticket.status = Ticket.Status.OPEN
            ticket.save()

            # Record creation history
            TicketHistory.objects.create(
                ticket=ticket,
                changed_by=request.user,
                action="Ticket created.",
            )

            # Handle optional initial attachment
            attachment_file = form.cleaned_data.get("attachment")
            if attachment_file:
                Attachment.objects.create(
                    ticket=ticket,
                    uploaded_by=request.user,
                    file=attachment_file,
                    original_filename=attachment_file.name,
                )
                TicketHistory.objects.create(
                    ticket=ticket,
                    changed_by=request.user,
                    action=f"Attachment uploaded: {attachment_file.name}",
                )

            messages.success(request, f"Ticket {ticket.ticket_number} created successfully.")
            return redirect("tickets:ticket_detail", ticket_id=ticket.pk)
    else:
        form = TicketCreateForm()

    return render(request, "tickets/ticket_create.html", {"form": form})


@login_required
def ticket_detail(request, ticket_id):
    """
    Detailed view of a ticket, including history, comments, attachments, and actions.
    """
    ticket, err_response = get_user_ticket_or_403(request.user, ticket_id)
    if err_response:
        return render(request, "403.html", status=403)

    comments = ticket.comments.select_related("author").order_by("created_at")
    attachments = ticket.attachments.select_related("uploaded_by").order_by("-uploaded_at")
    history = ticket.history.select_related("changed_by").order_by("-timestamp")

    is_closed = ticket.status == Ticket.Status.CLOSED
    user = request.user

    # Prepare appropriate action forms
    comment_form = CommentForm() if not (is_closed and user.role == User.Role.CUSTOMER) else None
    attachment_form = AttachmentForm() if not (is_closed and user.role == User.Role.CUSTOMER) else None

    # Status transition form (Agents & Admins only)
    status_form = None
    if user.role in [User.Role.ADMIN, User.Role.AGENT]:
        status_form = TicketStatusTransitionForm(ticket=ticket)

    # Assign form (Admin only)
    assign_form = None
    if user.role == User.Role.ADMIN:
        assign_form = TicketAssignForm(initial={"assigned_agent": ticket.assigned_agent_id})

    context = {
        "ticket": ticket,
        "comments": comments,
        "attachments": attachments,
        "history": history,
        "comment_form": comment_form,
        "attachment_form": attachment_form,
        "status_form": status_form,
        "assign_form": assign_form,
        "is_closed": is_closed,
        "can_transition": status_form is not None and bool(ticket.VALID_TRANSITIONS.get(ticket.status)),
    }
    return render(request, "tickets/ticket_detail.html", context)


@login_required
@require_POST
def ticket_add_comment(request, ticket_id):
    """Add a comment to the ticket."""
    ticket, err_response = get_user_ticket_or_403(request.user, ticket_id)
    if err_response:
        return render(request, "403.html", status=403)

    # Customers cannot comment on CLOSED tickets
    if ticket.status == Ticket.Status.CLOSED and request.user.role == User.Role.CUSTOMER:
        messages.error(request, "You cannot comment on a closed ticket.")
        return redirect("tickets:ticket_detail", ticket_id=ticket.pk)

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        comment.save()

        TicketHistory.objects.create(
            ticket=ticket,
            changed_by=request.user,
            action="Comment added.",
        )
        messages.success(request, "Comment posted successfully.")
    else:
        messages.error(request, "Failed to add comment. Please ensure the message is not empty.")

    return redirect("tickets:ticket_detail", ticket_id=ticket.pk)


@login_required
@require_POST
def ticket_add_attachment(request, ticket_id):
    """Upload a file attachment to the ticket."""
    ticket, err_response = get_user_ticket_or_403(request.user, ticket_id)
    if err_response:
        return render(request, "403.html", status=403)

    if ticket.status == Ticket.Status.CLOSED and request.user.role == User.Role.CUSTOMER:
        messages.error(request, "You cannot upload attachments to a closed ticket.")
        return redirect("tickets:ticket_detail", ticket_id=ticket.pk)

    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.ticket = ticket
        attachment.uploaded_by = request.user
        attachment.original_filename = attachment.file.name
        attachment.save()

        TicketHistory.objects.create(
            ticket=ticket,
            changed_by=request.user,
            action=f"Attachment uploaded: {attachment.original_filename}",
        )
        messages.success(request, "Attachment uploaded successfully.")
    else:
        for error in form.errors.values():
            messages.error(request, error.as_text())

    return redirect("tickets:ticket_detail", ticket_id=ticket.pk)


@login_required
@require_POST
def ticket_change_status(request, ticket_id):
    """
    Change ticket status following strict workflow transition rules.
    Only Support Agents assigned to the ticket and Admins may change status.
    """
    ticket, err_response = get_user_ticket_or_403(request.user, ticket_id)
    if err_response:
        return render(request, "403.html", status=403)

    if request.user.role not in [User.Role.ADMIN, User.Role.AGENT]:
        return render(request, "403.html", status=403)

    form = TicketStatusTransitionForm(request.POST, ticket=ticket)
    if form.is_valid():
        new_status = form.cleaned_data["new_status"]
        try:
            ticket.transition_to(new_status, changed_by=request.user)
            messages.success(request, f"Status updated to '{ticket.get_status_display()}'.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        messages.error(request, "Invalid status transition selected.")

    return redirect("tickets:ticket_detail", ticket_id=ticket.pk)


@login_required
@require_POST
def ticket_assign(request, ticket_id):
    """
    Assign or reassign a ticket to a Support Agent.
    Admin only. If ticket was OPEN, automatically transitions to ASSIGNED.
    """
    if request.user.role != User.Role.ADMIN:
        return render(request, "403.html", status=403)

    ticket = get_object_or_404(Ticket, pk=ticket_id)
    form = TicketAssignForm(request.POST)

    if form.is_valid():
        agent = form.cleaned_data["assigned_agent"]
        old_agent = ticket.assigned_agent
        ticket.assigned_agent = agent

        if ticket.status == Ticket.Status.OPEN:
            ticket.status = Ticket.Status.ASSIGNED
            action_desc = f"Assigned to {agent.get_full_name() or agent.username}. Status updated to Assigned."
        else:
            action_desc = f"Assigned to {agent.get_full_name() or agent.username}."

        ticket.save(update_fields=["assigned_agent", "status", "updated_at"])

        TicketHistory.objects.create(
            ticket=ticket,
            changed_by=request.user,
            action=action_desc,
        )
        messages.success(request, action_desc)
    else:
        messages.error(request, "Failed to assign ticket. Please select a valid support agent.")

    return redirect("tickets:ticket_detail", ticket_id=ticket.pk)
