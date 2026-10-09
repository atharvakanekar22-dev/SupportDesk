from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("agent-dashboard/", views.agent_dashboard, name="agent_dashboard"),
    path("customer-dashboard/", views.customer_dashboard, name="customer_dashboard"),
]
