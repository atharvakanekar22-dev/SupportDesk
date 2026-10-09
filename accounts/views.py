from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm


def login_view(request):
    """Display and process the login form."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    form = LoginForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        # Honour ?next= parameter if present
        next_url = request.GET.get("next") or "core:dashboard"
        return redirect(next_url)

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    """Log the current user out and redirect to login."""
    logout(request)
    return redirect("accounts:login")
