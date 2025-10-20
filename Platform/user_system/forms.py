#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django import forms
from .models import User


from django.contrib.auth.forms import AuthenticationForm

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Username',
                'autofocus': True
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Password'
            }
        )
    )

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
    gender = forms.ChoiceField(choices=User.GENDER_CHOICES)
    age = forms.IntegerField()
    phone = forms.CharField(max_length=50)
    email = forms.EmailField()
    occupation = forms.ChoiceField(choices=User.OCCUPATION_CHOICES)
    education = forms.ChoiceField(choices=User.EDUCATION_CHOICES)
    field_of_expertise = forms.CharField(max_length=100)
    llm_frequency = forms.ChoiceField(choices=User.LLM_FREQUENCY_CHOICES)
    llm_history = forms.ChoiceField(choices=User.LLM_HISTORY_CHOICES)


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
    gender = forms.ChoiceField(
        required=True,
        choices=User.GENDER_CHOICES,
        label=u'Gender',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
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
    occupation = forms.ChoiceField(
        required=True,
        choices=User.OCCUPATION_CHOICES,
        label=u'Occupation',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
            }
        )
    )
    education = forms.ChoiceField(
        required=True,
        choices=User.EDUCATION_CHOICES,
        label=u'Education Level',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
            }
        )
    )
    field_of_expertise = forms.CharField(
        required=True,
        label=u'Field of Expertise',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control login-field',
                'placeholder': u'e.g., Computer Science, History, etc.',
            }
        )
    )
    llm_frequency = forms.ChoiceField(
        required=True,
        choices=User.LLM_FREQUENCY_CHOICES,
        label=u'How often do you use large language models (LLMs)?',
        help_text=u'This helps us understand your experience with LLMs.',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
            }
        )
    )
    llm_history = forms.ChoiceField(
        required=True,
        choices=User.LLM_HISTORY_CHOICES,
        label=u'How long have you been using large language models(LLMs)?',
        help_text=u'This helps us understand your experience with LLMs.',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
            }
        )
    )

    def clean(self):
        cleaned_data = super(SignupForm, self).clean()
        if password and password_retype and password != password_retype:
            self.add_error('password_retype', "The two passwords do not match.")

        return cleaned_data


class EditInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'gender', 'age', 'phone', 'email', 'occupation', 'education', 'field_of_expertise', 'llm_frequency', 'llm_history']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Age'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'occupation': forms.Select(attrs={'class': 'form-select'}),
            'education': forms.Select(attrs={'class': 'form-select'}),
            'field_of_expertise': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Field of Expertise'}),
            'llm_frequency': forms.Select(attrs={'class': 'form-select'}),
            'llm_history': forms.Select(attrs={'class': 'form-select'}),
        }


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
        if password and password_retype and password != password_retype:
            self.add_error('new_password_retype', "The two passwords do not match.")

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

        if password and password_retype and password != password_retype:
            self.add_error('new_password_retype', "The two passwords do not match.")

        return cleaned_data