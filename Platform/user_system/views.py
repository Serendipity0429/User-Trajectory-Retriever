#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from .forms import (
    CustomAuthenticationForm,
    SignupForm,
    EditInfoForm,
    EditPasswordForm,
    ForgetPasswordForm,
    ResetPasswordForm,
)
from .models import User, ResetPasswordRequest, InformedConsent
from core.utils import print_debug
from user_system.utils import authenticate
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
import logging
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
    get_user_model,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, F
from django.templatetags.static import static
from django.contrib import messages
from django.views import View
from .utils import send_reset_password_email
from .decorators import consent_exempt
import markdown


USER_SEARCH_RESULT_LIMIT = 8


@csrf_exempt
@consent_exempt
def token_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        username = request.POST.get("username")
        password = request.POST.get("password")
        force_login = request.POST.get("force", "false").lower() == "true"

        error_code, user = authenticate(username, password)

        if error_code == 0 and user:
            if user.extension_session_token and not force_login:
                return JsonResponse(
                    {
                        "status": "already_logged_in",
                        "last_login_from": user.last_login_from,
                    }
                )

            # Generate a new session token
            session_token = uuid.uuid4().hex
            user.extension_session_token = session_token

            # Get user's IP address
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0]
            else:
                ip = request.META.get("REMOTE_ADDR")
            user.last_login_from = ip

            user.login_num = F("login_num") + 1
            user.last_login = now()
            user.save()
            user.refresh_from_db()

            refresh = RefreshToken.for_user(user)
            # Add session_token to the token payload
            refresh["extension_session_token"] = session_token

            return JsonResponse(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            )
        else:
            print_debug(
                f"User {username} authentication failed with error code {error_code}"
            )
            error_messages = {
                1: "User does not exist",
                2: "Incorrect password",
                4: "Authentication failed",
            }
            return JsonResponse(
                {
                    "error": error_messages.get(error_code, "Authentication failed"),
                    "error_code": error_code,
                },
                status=401,
            )
    except Exception as e:
        logging.error(f"An unexpected error occurred during token login: {e}")
        return JsonResponse(
            {
                "error": "An unexpected error occurred. Please try again later.",
                "error_code": 3,
            },
            status=500,
        )

def login(request):
    form = CustomAuthenticationForm(request, data=request.POST or None)
    error_message = None

    if request.method == "POST":
        if form.is_valid():
            request.session["login_attempts"] = 0  # Reset attempts on success
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, "Successfully logged in.")
            
            next_url = request.GET.get('next')
            if next_url:
                return HttpResponseRedirect(next_url)
            else:
                if user.is_superuser:
                    return HttpResponseRedirect(reverse("dashboard:index"))
                else:
                    return HttpResponseRedirect(reverse("task_manager:home"))
        else:
            # Increment login attempts
            request.session["login_attempts"] = (
                request.session.get("login_attempts", 0) + 1
            )
            error_message = "Invalid username or password."

            # If we just crossed the threshold, the current 'form' instance doesn't have the captcha field.
            # We need to add it so it renders for the user to fill in next time.
            if request.session["login_attempts"] >= 2 and "captcha" not in form.fields:
                from captcha.fields import CaptchaField

                form.fields["captcha"] = CaptchaField()
                form.fields["captcha"].widget.attrs.update(
                    {"class": "form-control", "placeholder": "Enter captcha"}
                )

            # If captcha error exists, update error message
            if "captcha" in form.errors:
                error_message = "Invalid CAPTCHA. Please try again."

    show_captcha = request.session.get("login_attempts", 0) >= 2

    return render(
        request,
        "login.html",
        {
            "form": form,
            "error_message": error_message,
            "show_captcha": show_captcha,
        },
    )


@consent_exempt
def informed_consent(request):
    latest_consent = InformedConsent.get_latest()

    # latest_consent is guaranteed to be an object (saved or unsaved)
    html_content = markdown.markdown(latest_consent.content)

    if request.method == "POST":
        if "agree" in request.POST:
            if not latest_consent.pk:
                # If it's an unsaved default object, save it now as the first version
                latest_consent.save()

            if request.user.is_authenticated:
                request.user.agreed_consent_version = latest_consent
                request.user.consent_agreed = True
                request.user.save()
                next_url = request.GET.get('next')
                if next_url:
                    return HttpResponseRedirect(next_url)
                return HttpResponseRedirect(reverse("task_manager:home"))
            else:
                request.session["consent_agreed"] = True
                return HttpResponseRedirect(reverse("user_system:signup"))
        else:
            if request.user.is_authenticated:
                auth_logout(request)
            return HttpResponseRedirect(reverse("user_system:login"))

    return render(
        request,
        "informed_consent.html",
        {
            "latest_consent": (
                latest_consent if latest_consent.pk else None
            ),  # Pass None if unsaved so template knows it's default
            "html_content": html_content,
        },
    )


def signup(request):
    if not request.session.get("consent_agreed"):
        return HttpResponseRedirect(reverse("user_system:informed_consent"))

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                email=form.cleaned_data["email"],
            )
            user.consent_agreed = True
            user.agreed_consent_version = InformedConsent.get_latest()
            user.save()

            profile = user.profile
            profile.name = form.cleaned_data["name"]
            profile.gender = form.cleaned_data["gender"]
            profile.age = form.cleaned_data["age"]
            profile.phone = form.cleaned_data["phone"]
            profile.occupation = form.cleaned_data["occupation"]
            profile.education = form.cleaned_data["education"]
            profile.field_of_expertise = form.cleaned_data["field_of_expertise"]
            profile.llm_frequency = form.cleaned_data["llm_frequency"]
            profile.llm_history = form.cleaned_data["llm_history"]
            profile.english_proficiency = form.cleaned_data["english_proficiency"]
            profile.web_search_proficiency = form.cleaned_data["web_search_proficiency"]
            profile.web_agent_familiarity = form.cleaned_data["web_agent_familiarity"]
            profile.web_agent_frequency = form.cleaned_data["web_agent_frequency"]
            profile.save()

            # Clean up the session
            request.session.pop("consent_agreed", None)

            return HttpResponseRedirect(reverse("user_system:login"))
    else:
        form = SignupForm()

    return render(request, "signup.html", {"form": form})


@consent_exempt
def logout(request):
    auth_logout(request)
    return HttpResponseRedirect(reverse("user_system:login"))


def health_check(request):
    return JsonResponse({"status": "ok"})


@login_required
def info(request):
    return render(
        request,
        "info.html",
        {
            "cur_user": request.user,
        },
    )


@login_required
def edit_info(request):
    if request.method == "POST":
        form = EditInfoForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            request.user.email = form.cleaned_data["email"]
            request.user.save()
            form.save()
            return HttpResponseRedirect(reverse("user_system:info"))
    else:
        form = EditInfoForm(
            instance=request.user.profile, initial={"email": request.user.email}
        )

    return render(
        request,
        "edit_info.html",
        {
            "cur_user": request.user,
            "form": form,
        },
    )


@login_required
def edit_password(request):
    form = EditPasswordForm(request.POST or None)
    error_message = None

    if request.method == "POST" and form.is_valid():
        if request.user.check_password(form.cleaned_data["cur_password"]):
            user = request.user
            user.set_password(form.cleaned_data["new_password"])
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was successfully updated!")
            return HttpResponseRedirect(reverse("user_system:info"))
        else:
            error_message = "Incorrect current password."
    elif request.method == "POST":
        error_message = form.errors

    return render(
        request,
        "edit_password.html",
        {
            "cur_user": request.user,
            "form": form,
            "error_message": error_message,
        },
    )


def forget_password(request):
    form = ForgetPasswordForm(request.POST or None)
    error_message = None

    if request.method == "POST" and form.is_valid():
        try:
            user = User.objects.get(email=form.cleaned_data["email"])
            reset_request = ResetPasswordRequest.objects.create(user=user)
            # Assuming send_reset_password_email is a utility function you have defined
            # from .utils import send_reset_password_email
            send_reset_password_email(request.get_host(), reset_request)
            request.session['reset_email'] = form.cleaned_data["email"]
            return HttpResponseRedirect(reverse("user_system:password_reset_sent"))
        except User.DoesNotExist:
            error_message = "Email address not found."
            # Reset form to ensure new captcha is generated
            form = ForgetPasswordForm(initial={"email": form.cleaned_data["email"]})
    elif request.method == "POST":
        error_message = form.errors

    return render(
        request,
        "forget_password.html",
        {
            "form": form,
            "error_message": error_message,
        },
    )


def password_reset_sent(request):
    email = request.session.get('reset_email', 'your email address')
    # Optional: Clear the email from session if you only want to show it once
    # request.session.pop('reset_email', None)
    return render(request, "password_reset_sent.html", {"email": email})


def reset_password(request, token_str):
    token = get_object_or_404(ResetPasswordRequest, token=token_str)

    if token.is_expired:
        return render(
            request,
            "reset_password.html",
            {
                "form": None,
                "error_message": "This token has expired. Please request a new password reset.",
            },
        )

    form = ResetPasswordForm(request.POST or None)
    error_message = None

    if request.method == "POST" and form.is_valid():
        user = token.user
        user.set_password(form.cleaned_data["new_password"])
        user.save()
        token.delete()
        return HttpResponseRedirect(reverse("user_system:login"))
    elif request.method == "POST":
        error_message = form.errors

    return render(
        request,
        "reset_password.html",
        {
            "form": form,
            "error_message": error_message,
            "user": token.user,
        },
    )


class UserSearchView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request):
        term = request.GET.get("term", "")
        User = get_user_model()
        users = (
            User.objects.filter(
                Q(username__icontains=term) | Q(profile__name__icontains=term)
            )
            .exclude(pk=request.user.pk)
            .select_related("profile")[:USER_SEARCH_RESULT_LIMIT]
        )

        results = []
        for user in users:
            # Use default static image if icon is not set
            image_url = (
                user.profile.icon.url
                if user.profile.icon
                else static("img/default.jpg")
            )

            results.append(
                {
                    "id": user.id,
                    "label": user.username,  # Keep for accessibility
                    "value": user.username,
                    "name": user.profile.name or user.username,
                    "username": user.username,
                    "image_url": image_url,
                }
            )
        return JsonResponse(results, safe=False)


def check_web_session(request):
    if request.user.is_authenticated:
        return JsonResponse(
            {"status": "authenticated", "username": request.user.username}
        )
    else:
        return JsonResponse({"status": "anonymous"})