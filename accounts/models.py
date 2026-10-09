from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for SupportDesk.

    Extends Django's AbstractUser so we inherit all authentication
    machinery (password hashing, sessions, admin integration) while
    adding a role field that drives access control throughout the app.

    Role is stored on the user rather than via groups so that the
    business logic for "who can do what" remains explicit and easy
    to read — groups/permissions can be layered on later if needed.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        AGENT = "AGENT", "Support Agent"
        CUSTOMER = "CUSTOMER", "Customer"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    # Optional profile fields — kept minimal for Part 1
    phone = models.CharField(max_length=30, blank=True)
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="Relevant for support agents.",
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["username"]

    # ------------------------------------------------------------------
    # Convenience properties for cleaner template/view logic
    # ------------------------------------------------------------------

    @property
    def is_admin_user(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_agent(self) -> bool:
        return self.role == self.Role.AGENT

    @property
    def is_customer(self) -> bool:
        return self.role == self.Role.CUSTOMER

    def get_role_display_name(self) -> str:
        return self.get_role_display()

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
