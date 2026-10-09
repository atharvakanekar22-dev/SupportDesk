from django.urls import path
from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.ticket_list, name="ticket_list"),
    path("new/", views.ticket_create, name="ticket_create"),
    path("<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("<int:ticket_id>/comment/", views.ticket_add_comment, name="ticket_add_comment"),
    path("<int:ticket_id>/attachment/", views.ticket_add_attachment, name="ticket_add_attachment"),
    path("<int:ticket_id>/status/", views.ticket_change_status, name="ticket_change_status"),
    path("<int:ticket_id>/assign/", views.ticket_assign, name="ticket_assign"),
]
