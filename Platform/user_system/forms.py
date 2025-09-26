#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django import forms
from .models import User

llm_frequency_choices = User.LLM_FREQUENCY_CHOICES
llm_history_choices = User.LLM_HISTORY_CHOICES


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Please input the username',
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Password',
            }
        )
    )


from django.contrib.auth.forms import UserCreationForm as AuthUserCreationForm

class UserCreationForm(AuthUserCreationForm):
    class Meta(AuthUserCreationForm.Meta):
        model = User
        fields = ('username',)

    name = forms.CharField(max_length=50)
    sex = forms.CharField(max_length=50)
    age = forms.IntegerField()
    phone = forms.CharField(max_length=50)
    email = forms.EmailField()
    occupation = forms.CharField(max_length=50)
    llm_frequency = forms.ChoiceField(choices=llm_frequency_choices)
    llm_history = forms.ChoiceField(choices=llm_history_choices)


class SignupForm(forms.Form):
    username = forms.CharField(
        required=True,
        min_length=6,
        label=u'Username',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Please input the username',
            }
        )
    )
    password = forms.CharField(
        required=True,
        min_length=8,
        label=u'Password',
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Password',
            }
        )
    )
    password_retype = forms.CharField(
        required=True,
        min_length=8,
        label=u'Please input the password again',
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Please input the password again',
            }
        )
    )
    name = forms.CharField(
        required=True,
        label=u'Name',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Name',
            }
        )
    )
    sex = forms.CharField(
        required=True,
        label=u'Gender',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Gender',
            }
        )
    )
    age = forms.IntegerField(
        required=True,
        label=u'Age',
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Age',
            }
        )
    )
    phone = forms.CharField(
        required=True,
        label=u'Phone Number',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Phone Number',
            }
        )
    )
    email = forms.EmailField(
        required=True,
        label=u'E-mail Address',
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'E-mail Address',
            }
        )
    )
    occupation = forms.CharField(
        required=True,
        label=u'Occupation',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Occupation',
            }
        )
    )
    llm_frequency = forms.ChoiceField(
        required=True,
        choices=llm_frequency_choices,
        label=u'How often do you use large language models (LLMs)?',
        help_text=u'This helps us understand your experience with LLMs.',
        widget=forms.Select(
            attrs={
                'class': 'select2-container form-control select select-primary',
            }
        )
    )
    llm_history = forms.ChoiceField(
        required=True,
        choices=llm_history_choices,
        label=u'How long have you been using large language models(LLMs)?',
        help_text=u'This helps us understand your experience with LLMs.',
        widget=forms.Select(
            attrs={
                'class': 'select2-container form-control select select-primary' ,
            }
        )
    )

    def clean(self):
        cleaned_data = super(SignupForm, self).clean()
        password = cleaned_data.get('password')
        password_retype = cleaned_data.get('password_retype')

        if password != password_retype:
            raise forms.ValidationError(
                u'The two passwords are inconsistent!'
            )

        return cleaned_data


class EditInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'sex', 'age', 'phone', 'email', 'occupation', 'llm_frequency', 'llm_history']


class EditPasswordForm(forms.Form):

    cur_password = forms.CharField(
        required=True,
        min_length=8,
        label=u'Current password',
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'password',
            }
        )
    )
    new_password = forms.CharField(
        required=True,
        min_length=8,
        label=u'New password',
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'password',
            }
        )
    )
    new_password_retype = forms.CharField(
        required=True,
        min_length=8,
        label=u'Please input the new password again',
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Please input the new password again',
            }
        )
    )

    def clean(self):
        cleaned_data = super(EditPasswordForm, self).clean()
        password = cleaned_data.get('new_password')
        password_retype = cleaned_data.get('new_password_retype')

        if password != password_retype:
            raise forms.ValidationError(
                u'The two passwords are inconsistent!'
            )

        return cleaned_data


class ForgetPasswordForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label=u'E-mail Address',
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Input E-mail address',
            }
        )
    )


class ResetPasswordForm(forms.Form):

    new_password = forms.CharField(
        required=True,
        min_length=8,
        label=u'New password',
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'password',
            }
        )
    )
    new_password_retype = forms.CharField(
        required=True,
        min_length=8,
        label=u'Please input the new password again',
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'Please input the new password again',
            }
        )
    )

    def clean(self):
        cleaned_data = super(ResetPasswordForm, self).clean()
        password = cleaned_data.get('new_password')
        password_retype = cleaned_data.get('new_password_retype')

        if password != password_retype:
            raise forms.ValidationError(
                u'The two passwords are inconsistent!'
            )

        return cleaned_data