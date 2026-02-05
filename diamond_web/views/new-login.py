from django.shortcuts import render

def new_login(request):
    return render(request, 'auth-login-creative.html')