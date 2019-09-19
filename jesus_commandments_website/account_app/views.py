from django.contrib import messages
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.shortcuts import render, redirect
from django.utils.translation import gettext

from account_app.forms import UserForm


def index(request):
    return render(request, 'account/index.html')


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            messages.success(request, gettext('Thank you for your registration. We are validating your registration and will get in touch soon.'))
            return redirect('/account/profile')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, gettext('Your profile was successfully updated!'))
            return redirect('/account/profile')
        else:
            messages.error(request, gettext('Please correct the error below.'))
    else:
        user_form = UserForm(instance=request.user)
    return render(request, 'account/profile.html', {
        'user_form': user_form
    })


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, gettext('Your password was successfully updated!'))
            return redirect('account/change_password')
        else:
            messages.error(request, gettext('Please correct the error below.'))
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'account/change_password.html', {
        'form': form
    })
