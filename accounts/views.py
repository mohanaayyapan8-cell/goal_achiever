from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from learning.services import seed_default_curriculum

from .forms import ProfileForm, RegisterForm, UserUpdateForm
from .utils import get_profile


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        seed_default_curriculum(user)  # starter domains, technologies and topics
        login(request, user)
        messages.success(request, f"Welcome, {user.first_name}! Your account is ready.")
        return redirect("dashboard:index")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    """Shows ONLY the logged-in user's own profile (no id in the URL)."""
    return render(request, "accounts/profile.html", {"profile": get_profile(request.user)})


@login_required
def profile_edit(request):
    profile_obj = get_profile(request.user)
    user_form = UserUpdateForm(request.POST or None, instance=request.user)
    profile_form = ProfileForm(request.POST or None, instance=profile_obj)
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile_edit.html", {"user_form": user_form, "profile_form": profile_form})
