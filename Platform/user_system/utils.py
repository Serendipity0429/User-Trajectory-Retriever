#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .models import User, user_group_list
from django.http import HttpResponseRedirect
from django.http import HttpRequest
from django.core.mail import EmailMultiAlternatives
import smtplib
from django.conf import settings
import logging
import re

logger = logging.getLogger(__name__)


def check_password_strength(password):
    """
    Check if the password meets the complexity requirements.
    Requirements:
    1. Length >= 8
    2. Contains uppercase letters
    3. Contains lowercase letters
    4. Contains numbers
    5. Contains special characters (but safe ones)
    """
    if ' ' in password:
        return False, "Password must not contain spaces."

    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."

    # Allowed special characters: !@#$%^&*()_+-=[]{}|;:,.<>?
    # This regex checks if there is at least one character from the allowed set.
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
        return False, "Password must contain at least one special character."

    # Check for invalid characters (potential injection attack vectors or just unsupported)
    # We want to allow ONLY alphanumeric and the specific special chars.
    if not re.match(r"^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]+$", password):
        return False, "Password contains invalid characters."

    return True, None


def authenticate(username, password):
    """
    :param username: username
    :param password: password
    :return: error_code and authenticated User object
    error_code:
    0   success
    1   no such user
    2   password is wrong
    """
    try:
        user = User.objects.get(username=username)
        if user.check_password(password):
            return 0, user
        else:
            return 2, None
    except User.DoesNotExist:
        return 1, None


def store_in_session(request, user):
    request.session.delete_test_cookie()
    request.session["username"] = user.username
    request.session.set_expiry(0)


def redirect_to_prev_page(request, default_url):
    if "prev_page" not in request.session:
        return HttpResponseRedirect(default_url)
    else:
        prev_page = request.session["prev_page"]
        del request.session["prev_page"]
        return HttpResponseRedirect(prev_page)


def login_redirect(request, login_url="/user/login/"):
    request.session["prev_page"] = request.get_full_path()
    request.session.set_expiry(0)
    return HttpResponseRedirect(login_url)


def auth_failed_redirect(request, missing_group):
    return HttpResponseRedirect("/user/auth_failed/%s/" % missing_group)


def require_login(func):
    def ret(*args):
        req = args[0]
        # print the request value
        assert isinstance(req, HttpRequest)
        if "username" not in req.session:
            print(req.session.keys())
            return login_redirect(req)
        try:
            user = User.objects.get(username=req.session["username"])
            args = [user] + list(args)
            return func(*args)
        except User.DoesNotExist:
            return login_redirect(req)

    return ret


def require_auth(user_groups):

    def require_login_with_auth(func):

        def ret(*args):
            req = args[0]
            assert isinstance(req, HttpRequest)
            if "username" not in req.session:
                return login_redirect(req)
            try:
                user = User.objects.get(username=req.session["username"])
                # check if all the user group requirements are satisfied
                # if no, show auth failed page
                for g in user_groups:
                    if g not in list(user.user_groups):
                        return auth_failed_redirect(req, g)

                # if yes, pass the user as first parm
                args = [user] + list(args)
                return func(*args)
            except User.DoesNotExist:
                return login_redirect(req)

        return ret

    return require_login_with_auth


def get_user_groups_string(user_groups):
    return " | ".join([val for key, val in user_group_list if key in user_groups])


def send_reset_password_email(domain, reset_req):
    """
    Sends a password reset email to the user with a professional and informative message.
    """
    subject = "Password Reset Request for THUIR Annotation Platform"
    user = reset_req.user
    host = "http://" + domain
    reset_url = host + "/user/reset_password/%s/" % reset_req.token

    # Plain text message
    text_content = f"""
Hello {user.username},

You are receiving this email because you requested a password reset for your account on the THU-IR Annotation Platform.

Account details:
Username: {user.username}
Email: {user.email}

Please click the link below to reset your password:
{reset_url}

If you did not request a password reset, please ignore this email. This link will expire in 24 hours.

Thank you,
The THU-IR Annotation Platform Team
"""

    # HTML message
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset</title>
    <style>
        @import url('https://fonts.googleapis.cn/css2?family=Roboto:wght@400;700&display=swap');
        body {{
            font-family: 'Roboto', Arial, sans-serif;
            background-color: #f4f4f4;
            color: #333;
            margin: 0;
            padding: 0;
            font-size: 16px; /* Base font size */
        }}
        .email-container {{
            max-width: 600px;
            margin: 40px auto;
            background-color: #ffffff;
            border: 1px solid #dddddd;
            border-radius: 8px;
            overflow: hidden;
        }}
        .email-header {{
            background-color: #007bff;
            color: #ffffff;
            padding: 20px;
            text-align: center;
        }}
        .email-header h1 {{
            font-size: 28px;
        }}
        .email-body {{
            padding: 30px;
            line-height: 1.6;
            font-size: 18px; /* Larger body text */
        }}
        .email-body h3 {{
            font-size: 22px;
        }}
        .account-details {{
            background-color: #f9f9f9;
            border-left: 4px solid #007bff;
            padding: 15px;
            margin: 20px 0;
        }}
        .email-footer {{
            background-color: #f4f4f4;
            color: #777777;
            padding: 20px;
            text-align: center;
            font-size: 1em; /* Larger footer text */
        }}
        .button {{
            display: inline-block;
            background-color: #007bff;
            color: #ffffff;
            padding: 15px 25px;
            text-align: center;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            margin: 20px 0;
            font-size: 18px;
        }}
        .button:hover {{
            background-color: #0056b3;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="email-header">
            <h1>Password Reset Request</h1>
        </div>
        <div class="email-body">
            <h3>Hello {user.username},</h3>
            <p>We received a request to reset the password for the following account on the <strong>THUIR Annotation Platform</strong>:</p>
            <div class="account-details">
                <strong>Username:</strong> {user.username}<br>
                <strong>Email:</strong> {user.email}
            </div>
            <p>To proceed, please click the button below. This link will be valid for the next 24 hours.</p>
            <a href="{reset_url}" class="button">Reset Your Password</a>
            <p>If you are unable to click the button, please copy and paste the following URL into your web browser:</p>
            <p><a href="{reset_url}">{reset_url}</a></p>
            <p>If you did not request a password reset, please ignore this email. Your account remains secure.</p>
        </div>
        <div class="email-footer">
            <p>&copy; 2025 THUIR Annotation Platform. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    target_email = reset_req.user.email
    msg = EmailMultiAlternatives(subject, text_content, to=[target_email])
    msg.attach_alternative(html_content, "text/html")

    try:
        msg.send()
    except smtplib.SMTPException as e:
        print(f"Failed to send email: {e}")