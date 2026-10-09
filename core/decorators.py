"""
Access-control utilities for SupportDesk views.

These decorators wrap Django's login_required and add role-based
checks. They redirect to an appropriate error page rather than
silently failing.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def role_required(*roles):
    """
    Decorator that enforces both authentication and role membership.

    Usage::

        @role_required("ADMIN", "AGENT")
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                return render(request, "403.html", status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def admin_required(view_func):
    """Shortcut: restrict to ADMIN role only."""
    return role_required("ADMIN")(view_func)


def agent_or_admin_required(view_func):
    """Shortcut: restrict to AGENT or ADMIN roles."""
    return role_required("ADMIN", "AGENT")(view_func)
