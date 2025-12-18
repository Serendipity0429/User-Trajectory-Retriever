#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django import forms
from .models import User, Profile, InformedConsent
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm as AuthUserCreationForm,
)
from captcha.fields import CaptchaField


class InformedConsentForm(forms.ModelForm):
    class Meta:
        model = InformedConsent
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 15}),
        }


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
                "autofocus": True,
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        )
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        super().__init__(request, *args, **kwargs)
        if self.request and self.request.session.get("login_attempts", 0) >= 2:
            self.fields["captcha"] = CaptchaField()
            # Add order-first class to the input field
            self.fields["captcha"].widget.attrs.update(
                {"class": "form-control order-first", "placeholder": "Enter captcha"}
            )


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Please input the username",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Password",
            }
        )
    )


class UserCreationForm(AuthUserCreationForm):
    class Meta(AuthUserCreationForm.Meta):
        model = User
        fields = ("username",)

    name = forms.CharField(max_length=50)
    gender = forms.ChoiceField(choices=Profile.GENDER_CHOICES)
    age = forms.IntegerField()
    phone = forms.CharField(max_length=50)
    email = forms.EmailField()
    occupation = forms.ChoiceField(choices=Profile.OCCUPATION_CHOICES)
    education = forms.ChoiceField(choices=Profile.EDUCATION_CHOICES)
    field_of_expertise = forms.CharField(max_length=100)
    llm_frequency = forms.ChoiceField(choices=Profile.LLM_FREQUENCY_CHOICES)
    llm_history = forms.ChoiceField(choices=Profile.LLM_HISTORY_CHOICES)


class SignupForm(forms.Form):
    username = forms.CharField(
        required=True,
        min_length=3,
        label="Username",
        widget=forms.TextInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Please input the username",
            }
        ),
    )
    password = forms.CharField(
        required=True,
        min_length=8,
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Password",
            },
            render_value=True,
        ),
    )
    password_retype = forms.CharField(
        required=True,
        min_length=8,
        label="Please input the password again",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Please input the password again",
            },
            render_value=True,
        ),
    )
    name = forms.CharField(
        required=True,
        label="Name",
        widget=forms.TextInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Name",
            }
        ),
    )
    gender = forms.ChoiceField(
        required=True,
        choices=Profile.GENDER_CHOICES,
        label="Gender",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )
    age = forms.IntegerField(
        required=True,
        label="Age",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Age",
            }
        ),
    )
    phone = forms.CharField(
        required=True,
        label="Phone Number",
        widget=forms.TextInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Phone Number",
            }
        ),
    )
    email = forms.EmailField(
        required=True,
        label="E-mail Address",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "E-mail Address",
            }
        ),
    )
    occupation = forms.ChoiceField(
        required=True,
        choices=Profile.OCCUPATION_CHOICES,
        label="Occupation",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )
    education = forms.ChoiceField(
        required=True,
        choices=Profile.EDUCATION_CHOICES,
        label="Education Level",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )
    field_of_expertise = forms.CharField(
        required=True,
        label="Field of Profession / Major",
        widget=forms.TextInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "e.g., Computer Science, History, etc.",
            }
        ),
    )
    llm_frequency = forms.ChoiceField(
        required=True,
        choices=Profile.LLM_FREQUENCY_CHOICES,
        label="How often do you use large language models (LLMs)?",
        help_text="This helps us understand your experience with LLMs.",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )
    llm_history = forms.ChoiceField(
        required=True,
        choices=Profile.LLM_HISTORY_CHOICES,
        label="How long have you been using large language models(LLMs)?",
        help_text="This helps us understand your experience with LLMs.",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )
    english_proficiency = forms.ChoiceField(
        required=True,
        choices=Profile.ENGLISH_PROFICIENCY_CHOICES,
        label="What is your English proficiency level?",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )
    web_search_proficiency = forms.ChoiceField(
        required=True,
        choices=Profile.WEB_SEARCH_PROFICIENCY_CHOICES,
        label="How would you rate your web search proficiency?",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )
    web_agent_familiarity = forms.ChoiceField(
        required=True,
        choices=Profile.WEB_AGENT_FAMILIARITY_CHOICES,
        label="How familiar are you with web agents?",
        help_text="Web agents are AI assistants that can autonomously browse websites and perform tasks for you.",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )
    web_agent_frequency = forms.ChoiceField(
        required=True,
        choices=Profile.WEB_AGENT_FREQUENCY_CHOICES,
        label="How often do you use web agents?",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    captcha = CaptchaField()

    def __init__(self, *args, **kwargs):
        super(SignupForm, self).__init__(*args, **kwargs)
        # Add order-first class to the input field
        self.fields["captcha"].widget.attrs.update(
            {"class": "form-control order-first", "placeholder": "Enter captcha"}
        )

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(
                "This username has already been taken. Please choose a different one."
            )
        return username

    def clean(self):
        cleaned_data = super(SignupForm, self).clean()
        password = cleaned_data.get("password")
        password_retype = cleaned_data.get("password_retype")
        if password and password_retype and password != password_retype:
            self.add_error("password_retype", "The two passwords do not match.")

        return cleaned_data


class EditInfoForm(forms.ModelForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"})
    )
    icon = forms.ImageField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = Profile
        fields = [
            "name",
            "gender",
            "age",
            "phone",
            "occupation",
            "education",
            "field_of_expertise",
            "llm_frequency",
            "llm_history",
            "icon",
            "english_proficiency",
            "web_search_proficiency",
            "web_agent_familiarity",
            "web_agent_frequency",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Name"}
            ),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "age": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Age"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone"}
            ),
            "occupation": forms.Select(attrs={"class": "form-select"}),
            "education": forms.Select(attrs={"class": "form-select"}),
            "field_of_expertise": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Field of Profession / Major"}
            ),
            "llm_frequency": forms.Select(attrs={"class": "form-select"}),
            "llm_history": forms.Select(attrs={"class": "form-select"}),
            "english_proficiency": forms.Select(attrs={"class": "form-select"}),
            "web_search_proficiency": forms.Select(attrs={"class": "form-select"}),
            "web_agent_familiarity": forms.Select(attrs={"class": "form-select"}),
            "web_agent_frequency": forms.Select(attrs={"class": "form-select"}),
        }


class EditPasswordForm(forms.Form):

    cur_password = forms.CharField(
        required=True,
        min_length=8,
        label="Current password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "password",
            }
        ),
    )
    new_password = forms.CharField(
        required=True,
        min_length=8,
        label="New password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "password",
            }
        ),
    )
    new_password_retype = forms.CharField(
        required=True,
        min_length=8,
        label="Please input the new password again",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Please input the new password again",
            }
        ),
    )

    def clean(self):
        cleaned_data = super(EditPasswordForm, self).clean()
        password = cleaned_data.get("new_password")
        password_retype = cleaned_data.get("new_password_retype")
        if password and password_retype and password != password_retype:
            self.add_error("new_password_retype", "The two passwords do not match.")

        return cleaned_data


class ForgetPasswordForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label="E-mail Address",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Input E-mail address",
            }
        ),
    )
    captcha = CaptchaField()

    def __init__(self, *args, **kwargs):
        super(ForgetPasswordForm, self).__init__(*args, **kwargs)
        # Add order-first class to the input field
        self.fields["captcha"].widget.attrs.update(
            {"class": "form-control order-first", "placeholder": "Enter captcha"}
        )


class ResetPasswordForm(forms.Form):

    new_password = forms.CharField(
        required=True,
        min_length=8,
        label="New password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "password",
            }
        ),
    )
    new_password_retype = forms.CharField(
        required=True,
        min_length=8,
        label="Please input the new password again",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control login-field",
                "placeholder": "Please input the new password again",
            }
        ),
    )

    def clean(self):
        cleaned_data = super(ResetPasswordForm, self).clean()
        password = cleaned_data.get("new_password")
        password_retype = cleaned_data.get("new_password_retype")

        if password and password_retype and password != password_retype:
            self.add_error("new_password_retype", "The two passwords do not match.")

        return cleaned_data
