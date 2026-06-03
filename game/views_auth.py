from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render


def auth_login(request):
    if request.user.is_authenticated:
        return redirect('home')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get('next') or 'home')
        error = 'Benutzername oder Passwort falsch.'

    return render(request, 'game/auth/login.html', {'error': error})


def auth_register(request):
    if request.user.is_authenticated:
        return redirect('home')

    errors = {}
    values = {}
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        values = {'username': username}

        if not username:
            errors['username'] = 'Benutzername darf nicht leer sein.'
        elif len(username) > 150:
            errors['username'] = 'Benutzername ist zu lang (max. 150 Zeichen).'
        elif User.objects.filter(username__iexact=username).exists():
            errors['username'] = 'Dieser Benutzername ist bereits vergeben.'

        if not password1:
            errors['password1'] = 'Bitte ein Passwort eingeben.'
        elif len(password1) < 8:
            errors['password1'] = 'Das Passwort muss mindestens 8 Zeichen lang sein.'

        if password1 and password2 and password1 != password2:
            errors['password2'] = 'Die Passwörter stimmen nicht überein.'

        if not errors:
            user = User.objects.create_user(username=username, password=password1)
            login(request, user)
            return redirect('home')

    return render(request, 'game/auth/register.html', {'errors': errors, 'values': values})


def auth_logout(request):
    logout(request)
    return redirect('auth_login')
