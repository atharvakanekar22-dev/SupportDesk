from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from tickets.models import Ticket

from .decorators import admin_required, agent_or_admin_required, role_required


@login_required
def dashboard(request):
    """
    Route the user to their role-specific dashboard with real database metrics.
    All authenticated users land here after login.
    """
    user = request.user

    if user.role == "ADMIN":
        return admin_dashboard(request)

    if user.role == "AGENT":
        return agent_dashboard(request)

    # Default: Customer
    return customer_dashboard(request)


@admin_required
def admin_dashboard(request):
    """Admin dashboard with system-wide ticket counts and recent activity."""
    all_tickets = Ticket.objects.all()
    metrics = {
        "total": all_tickets.count(),
        "open": all_tickets.filter(status=Ticket.Status.OPEN).count(),
        "assigned": all_tickets.filter(status=Ticket.Status.ASSIGNED).count(),
        "in_progress": all_tickets.filter(status=Ticket.Status.IN_PROGRESS).count(),
        "resolved": all_tickets.filter(status=Ticket.Status.RESOLVED).count(),
        "closed": all_tickets.filter(status=Ticket.Status.CLOSED).count(),
    }
    recent_tickets = all_tickets.select_related("customer", "assigned_agent")[:8]

    context = {
        "metrics": metrics,
        "recent_tickets": recent_tickets,
    }
    return render(request, "core/dashboard_admin.html", context)


@agent_or_admin_required
def agent_dashboard(request):
    """Agent dashboard with metrics for tickets assigned to the logged-in agent."""
    user = request.user
    agent_tickets = Ticket.objects.filter(assigned_agent=user)
    metrics = {
        "total_assigned": agent_tickets.count(),
        "assigned": agent_tickets.filter(status=Ticket.Status.ASSIGNED).count(),
        "in_progress": agent_tickets.filter(status=Ticket.Status.IN_PROGRESS).count(),
        "resolved": agent_tickets.filter(status=Ticket.Status.RESOLVED).count(),
    }
    recent_tickets = agent_tickets.select_related("customer", "assigned_agent")[:8]

    context = {
        "metrics": metrics,
        "recent_tickets": recent_tickets,
    }
    return render(request, "core/dashboard_agent.html", context)


@role_required("CUSTOMER")
def customer_dashboard(request):
    """Customer dashboard with real personal ticket counts and recent submissions."""
    user = request.user
    customer_tickets = Ticket.objects.filter(customer=user)
    metrics = {
        "total": customer_tickets.count(),
        "open": customer_tickets.filter(status__in=[Ticket.Status.OPEN, Ticket.Status.ASSIGNED, Ticket.Status.IN_PROGRESS]).count(),
        "resolved": customer_tickets.filter(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count(),
    }
    recent_tickets = customer_tickets.select_related("customer", "assigned_agent")[:8]

    context = {
        "metrics": metrics,
        "recent_tickets": recent_tickets,
    }
    return render(request, "core/dashboard_customer.html", context)
