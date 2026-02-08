from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib import messages

@receiver(user_logged_in)
def display_login_success_message(sender, request, user, **kwargs):
    # Get user's full name or fall back to username
    full_name = user.get_full_name().strip() if user.get_full_name() else user.username
    messages.success(request, f"Selamat datang, {full_name}!")