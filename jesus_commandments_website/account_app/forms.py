from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'placeholder': 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional'}))
    email = forms.EmailField(max_length=254, widget=forms.TextInput(attrs={'placeholder': 'Required. Inform a valid email address.'}))
    password1 = forms.CharField(label=("Password"), widget=forms.PasswordInput(attrs={'placeholder': "Password must contain at least 8 characters and cant be entirely numeric."}))
    password2 = forms.CharField(label=("Password confirmation"), widget=forms.PasswordInput(attrs={'placeholder': "Enter the same password as above, for verification."}))

    agree_toc = forms.BooleanField(required=True, label='I agree with the Terms and Conditions')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'agree_toc')