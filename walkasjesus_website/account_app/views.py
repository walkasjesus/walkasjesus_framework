from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.utils.translation import gettext
from django.conf import settings

from account_app.forms import SignUpForm


def index(request):
    return render(request, 'account/index.html')

@login_required
def profile(request):
    if request.method == 'POST':
        user_form = SignUpForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, gettext('Your profile was successfully updated!'))
            return redirect('/account/profile')
        else:
            messages.error(request, gettext('Please correct the error below.'))
    else:
        user_form = SignUpForm(instance=request.user)
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
