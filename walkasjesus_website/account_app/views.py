from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext
from django.conf import settings

from account_app.forms import SignUpForm


def _get_moderator_emails():
    configured_emails = list(getattr(settings, 'ACCOUNT_MODERATOR_EMAILS', []))
    if configured_emails:
        return configured_emails

    admin_tuples = getattr(settings, 'ADMINS', [])
    return [email for _, email in admin_tuples if email]


def _send_activation_email(request, user):
    activation_path = reverse(
        'account:activate',
        kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
        }
    )
    activation_link = request.build_absolute_uri(activation_path)
    site_name = request.get_host()

    context = {
        'user': user,
        'activation_link': activation_link,
        'site_name': site_name,
    }

    subject = render_to_string('registration/account_activation_subject.txt', context).strip()
    message = render_to_string('registration/account_activation_email.txt', context)
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=getattr(settings, 'ACCOUNT_EMAIL_FAIL_SILENTLY', False),
    )


def _send_moderator_notification(user):
    moderator_emails = _get_moderator_emails()
    if not moderator_emails:
        return

    context = {
        'user': user,
    }
    subject = render_to_string('registration/moderator_notification_subject.txt', context).strip()
    message = render_to_string('registration/moderator_notification_email.txt', context)
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        moderator_emails,
        fail_silently=getattr(settings, 'ACCOUNT_EMAIL_FAIL_SILENTLY', False),
    )


def index(request):
    return render(request, 'account/index.html')


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            _send_activation_email(request, user)
            _send_moderator_notification(user)

            messages.success(request, gettext('Your account has been created. Please confirm your email address to activate your account.'))
            return redirect('account:login')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
        messages.success(request, gettext('Your email has been confirmed. You can now log in.'))
        return redirect('account:login')

    messages.error(request, gettext('The activation link is invalid or has expired.'))
    return redirect('account:signup')


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
