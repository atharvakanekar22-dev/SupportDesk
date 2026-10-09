from django.contrib import admin
from .models import Attachment, Comment, Ticket, TicketHistory


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ("created_at",)


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ("uploaded_at", "original_filename")


class TicketHistoryInline(admin.TabularInline):
    model = TicketHistory
    extra = 0
    readonly_fields = ("changed_by", "action", "timestamp")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number",
        "subject",
        "customer",
        "assigned_agent",
        "priority",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "priority", "created_at")
    search_fields = ("ticket_number", "subject", "customer__username", "customer__email")
    readonly_fields = ("ticket_number", "created_at", "updated_at")
    inlines = [CommentInline, AttachmentInline, TicketHistoryInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "created_at")
    list_filter = ("created_at",)
    search_fields = ("content", "ticket__ticket_number", "author__username")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "original_filename", "uploaded_by", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("original_filename", "ticket__ticket_number", "uploaded_by__username")


@admin.register(TicketHistory)
class TicketHistoryAdmin(admin.ModelAdmin):
    list_display = ("ticket", "changed_by", "action", "timestamp")
    list_filter = ("timestamp",)
    search_fields = ("ticket__ticket_number", "action", "changed_by__username")
    readonly_fields = ("ticket", "changed_by", "action", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
