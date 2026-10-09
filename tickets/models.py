import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def attachment_upload_path(instance, filename):
    """Store attachments under media/attachments/<ticket_number>/<filename>."""
    return os.path.join("attachments", str(instance.ticket.ticket_number), filename)


class Ticket(models.Model):
    """Core support ticket."""

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    # Valid transitions: key = current status, value = allowed next statuses
    VALID_TRANSITIONS = {
        Status.OPEN: [Status.ASSIGNED],
        Status.ASSIGNED: [Status.IN_PROGRESS],
        Status.IN_PROGRESS: [Status.RESOLVED],
        Status.RESOLVED: [Status.CLOSED],
        Status.CLOSED: [],  # terminal — no further transitions
    }

    ticket_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets_created",
        limit_choices_to={"role": "CUSTOMER"},
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets_assigned",
        limit_choices_to={"role": "AGENT"},
    )
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["assigned_agent"]),
        ]

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_ticket_number():
        """Generate a human-readable unique ticket number like TKT-20241008-A3F2."""
        date_part = timezone.now().strftime("%Y%m%d")
        unique_part = uuid.uuid4().hex[:4].upper()
        return f"TKT-{date_part}-{unique_part}"

    def can_transition_to(self, new_status):
        """Return True if transitioning from current status to new_status is valid."""
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status, changed_by):
        """
        Apply a status transition and record it in TicketHistory.
        Raises ValidationError if the transition is invalid.
        """
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Cannot change status from '{self.get_status_display()}' "
                f"to '{dict(self.Status.choices).get(new_status, new_status)}'."
            )
        old_status = self.status
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        TicketHistory.objects.create(
            ticket=self,
            changed_by=changed_by,
            action=f"Status changed from {old_status} to {new_status}.",
        )

    def __str__(self):
        return f"{self.ticket_number} — {self.subject}"


class Comment(models.Model):
    """A comment on a support ticket, by a customer, agent, or admin."""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        if not self.content or not self.content.strip():
            raise ValidationError({"content": "Comment cannot be empty."})

    def __str__(self):
        return f"Comment by {self.author} on {self.ticket.ticket_number}"


class Attachment(models.Model):
    """A file attached to a support ticket."""

    ALLOWED_EXTENSIONS = {
        "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt",
        "png", "jpg", "jpeg", "gif", "webp",
        "zip", "tar", "gz",
        "log",
    }
    MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_attachments",
    )
    file = models.FileField(upload_to=attachment_upload_path)
    original_filename = models.CharField(max_length=255, editable=False)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-uploaded_at"]

    def save(self, *args, **kwargs):
        if self.file and not self.pk:
            self.original_filename = self.file.name
        super().save(*args, **kwargs)

    def clean(self):
        if self.file:
            ext = self.file.name.rsplit(".", 1)[-1].lower() if "." in self.file.name else ""
            if ext not in self.ALLOWED_EXTENSIONS:
                raise ValidationError(
                    {"file": f"File type '.{ext}' is not allowed. "
                              f"Allowed types: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}"}
                )
            if self.file.size > self.MAX_SIZE_BYTES:
                raise ValidationError(
                    {"file": "File size must not exceed 10 MB."}
                )

    def __str__(self):
        return f"Attachment on {self.ticket.ticket_number}: {self.original_filename}"


class TicketHistory(models.Model):
    """Audit trail for ticket changes."""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="history",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_history_entries",
    )
    action = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Ticket History"
        verbose_name_plural = "Ticket Histories"

    def __str__(self):
        return f"[{self.ticket.ticket_number}] {self.action} — {self.timestamp:%Y-%m-%d %H:%M}"
