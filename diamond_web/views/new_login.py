from django.shortcuts import render

def new_login(request):
    return render(request, 'login/auth-login-creative.html')