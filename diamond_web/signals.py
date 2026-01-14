from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib import messages

@receiver(user_logged_in)
def display_login_success_message(sender, request, user, **kwargs):
    messages.success(request, f"Welcome back, {user.username}!")