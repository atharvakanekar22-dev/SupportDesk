from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Attachment, Comment, Ticket

User = get_user_model()


class TicketCreateForm(forms.ModelForm):
    """Form used by Customers to submit a new support ticket."""

    attachment = forms.FileField(
        required=False,
        label="Attachment (Optional)",
        help_text="Max 10 MB. Supported: PDF, Office docs, Images, TXT, CSV, Logs, Archives.",
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Ticket
        fields = ["subject", "description", "priority"]
        widgets = {
            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Brief summary of the issue",
                    "maxlength": "200",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Detailed description of the problem, error messages, and reproduction steps...",
                }
            ),
            "priority": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_subject(self):
        subject = self.cleaned_data.get("subject", "").strip()
        if not subject:
            raise ValidationError("Subject cannot be empty.")
        return subject

    def clean_description(self):
        description = self.cleaned_data.get("description", "").strip()
        if not description:
            raise ValidationError("Description cannot be empty.")
        return description

    def clean_attachment(self):
        file = self.cleaned_data.get("attachment")
        if file:
            ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
            if ext not in Attachment.ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"File type '.{ext}' is not permitted. "
                    f"Allowed types: {', '.join(sorted(Attachment.ALLOWED_EXTENSIONS))}"
                )
            if file.size > Attachment.MAX_SIZE_BYTES:
                raise ValidationError("File size must not exceed 10 MB.")
        return file


class TicketAssignForm(forms.Form):
    """Admin form to assign or reassign a ticket to a support agent."""

    assigned_agent = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.Role.AGENT, is_active=True).order_by("first_name", "username"),
        required=True,
        empty_label="— Select Support Agent —",
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Assign Support Agent",
    )


class TicketStatusTransitionForm(forms.Form):
    """Form to transition ticket status, strictly enforcing valid next statuses."""

    new_status = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Change Status",
    )

    def __init__(self, *args, ticket=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket = ticket
        if ticket:
            allowed_next = ticket.VALID_TRANSITIONS.get(ticket.status, [])
            choices = [
                (status_val, dict(Ticket.Status.choices)[status_val])
                for status_val in allowed_next
            ]
            self.fields["new_status"].choices = choices
            if not choices:
                self.fields["new_status"].widget.attrs["disabled"] = "disabled"
                self.fields["new_status"].help_text = "No further status transitions are allowed (Terminal state)."


class CommentForm(forms.ModelForm):
    """Form to submit a comment on a ticket."""

    class Meta:
        model = Comment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Write a response or note...",
                }
            ),
        }
        labels = {
            "content": "Add Comment",
        }

    def clean_content(self):
        content = self.cleaned_data.get("content", "").strip()
        if not content:
            raise ValidationError("Comment cannot be empty.")
        return content


class AttachmentForm(forms.ModelForm):
    """Form to upload an attachment to an existing ticket."""

    class Meta:
        model = Attachment
        fields = ["file"]
        widgets = {
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }
        labels = {
            "file": "Select File",
        }

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
            if ext not in Attachment.ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"File type '.{ext}' is not permitted. "
                    f"Allowed types: {', '.join(sorted(Attachment.ALLOWED_EXTENSIONS))}"
                )
            if file.size > Attachment.MAX_SIZE_BYTES:
                raise ValidationError("File size must not exceed 10 MB.")
        return file


class TicketFilterForm(forms.Form):
    """Filter and search form for the ticket list view."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search ticket #, subject..."}
        ),
        label="Search",
    )
    status = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Status",
    )
    priority = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Priority",
    )
    agent = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(role=User.Role.AGENT, is_active=True).order_by("first_name", "username"),
        empty_label="All Agents",
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Agent",
    )

    def __init__(self, *args, show_agent=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [("", "All Statuses")] + list(Ticket.Status.choices)
        self.fields["priority"].choices = [("", "All Priorities")] + list(Ticket.Priority.choices)
        if not show_agent:
            self.fields.pop("agent")
