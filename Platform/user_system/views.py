#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from .forms import *
from .models import User, ResetPasswordRequest
from .utils import *
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
import logging
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta

def is_superuser(user):
    return user.is_superuser

from django.utils import timezone
from datetime import timedelta

from task_manager.models import Task

@login_required
@user_passes_test(is_superuser)
def admin_page(request):
    # User search and sort
    user_search_query = request.GET.get('user_search', '')
    user_sort_by = request.GET.get('user_sort_by', 'id')
    user_sort_dir = request.GET.get('user_sort_dir', 'asc')
    if user_sort_dir not in ['asc', 'desc']:
        user_sort_dir = 'asc'
    user_order = f"{'-' if user_sort_dir == 'desc' else ''}{user_sort_by}"

    if user_search_query:
        users_list = User.objects.filter(
            Q(username__icontains=user_search_query) |
            Q(email__icontains=user_search_query) |
            Q(name__icontains=user_search_query)
        ).order_by(user_order)
    else:
        users_list = User.objects.all().order_by(user_order)

    user_paginator = Paginator(users_list, 10)
    user_page_number = request.GET.get('user_page')
    users = user_paginator.get_page(user_page_number)

    # Task filter and sort
    task_user_filter = request.GET.get('task_user', '')
    task_date_filter = request.GET.get('task_date', '')
    task_sort_by = request.GET.get('task_sort_by', 'id')
    task_sort_dir = request.GET.get('task_sort_dir', 'asc')
    if task_sort_dir not in ['asc', 'desc']:
        task_sort_dir = 'asc'
    task_order = f"{'-' if task_sort_dir == 'desc' else ''}{task_sort_by}"

    tasks_list = Task.objects.all()
    if task_user_filter:
        tasks_list = tasks_list.filter(user__id=task_user_filter)
    if task_date_filter:
        tasks_list = tasks_list.filter(start_timestamp__date=task_date_filter)
    tasks_list = tasks_list.order_by(task_order)

    task_paginator = Paginator(tasks_list, 10)
    task_page_number = request.GET.get('task_page')
    tasks = task_paginator.get_page(task_page_number)

    # Dashboard metrics
    total_users = User.objects.count()
    superusers = User.objects.filter(is_superuser=True).count()
    thirty_days_ago = timezone.now() - timedelta(days=30)
    active_users = User.objects.filter(last_login__gte=thirty_days_ago).count()
    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(cancelled=False, active=False).count()
    cancelled_tasks = Task.objects.filter(cancelled=True).count()
    active_tasks = Task.objects.filter(active=True).count()

    all_users = User.objects.all()

    return render(
        request,
        'admin_page.html',
        {
            'users': users,
            'user_search_query': user_search_query,
            'user_sort_by': user_sort_by,
            'user_sort_dir': user_sort_dir,
            'tasks': tasks,
            'all_users': all_users,
            'task_user_filter': task_user_filter,
            'task_date_filter': task_date_filter,
            'task_sort_by': task_sort_by,
            'task_sort_dir': task_sort_dir,
            'total_users': total_users,
            'superusers': superusers,
            'active_users': active_users,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'cancelled_tasks': cancelled_tasks,
            'active_tasks': active_tasks,
        }
    )


@csrf_exempt
def token_login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    username = request.POST.get('username')
    password = request.POST.get('password')

    # Assuming 'authenticate' is a custom utility function you have defined in utils.py
    # from .utils import authenticate
    error_code, user = authenticate(username, password)

    if error_code == 0 and user:
        # Authentication successful, generate JWT token
        logging.debug(f'User {username} authenticated successfully for token login')
        refresh = RefreshToken.for_user(user)
        user.login_num += 1
        user.last_login = now()
        user.save()

        return JsonResponse({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    else:
        logging.debug(f'User {username} authentication failed with error code {error_code}')
        error_messages = {
            1: 'User does not exist',
            2: 'Incorrect password',
        }
        return JsonResponse({
            'error': error_messages.get(error_code, 'Authentication failed'),
            'error_code': error_code
        }, status=401)


@login_required
@user_passes_test(is_superuser)
def delete_user(request, user_id):
    if request.method == 'POST':
        user_to_delete = get_object_or_404(User, id=user_id)
        if request.user.id == user_to_delete.id:
            # Optionally, add a message to inform the admin they cannot delete themselves
            return HttpResponseRedirect(reverse('user_system:admin_page'))
        user_to_delete.delete()
        return HttpResponseRedirect(reverse('user_system:admin_page'))
    # Redirect if not a POST request
    return HttpResponseRedirect(reverse('user_system:admin_page'))


@login_required
@user_passes_test(is_superuser)
def toggle_superuser(request, user_id):
    if request.method == 'POST' and request.user.is_primary_superuser:
        user_to_toggle = get_object_or_404(User, id=user_id)
        if request.user.id != user_to_toggle.id:
            user_to_toggle.is_superuser = not user_to_toggle.is_superuser
            user_to_toggle.save()
            return JsonResponse({'status': 'success', 'is_superuser': user_to_toggle.is_superuser})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
@user_passes_test(is_superuser)
def login_as_user(request, user_id):
    if request.method == 'POST':
        user_to_login = get_object_or_404(User, id=user_id)
        if not user_to_login.is_primary_superuser and request.user.id != user_to_login.id:
            auth_login(request, user_to_login)
            return HttpResponseRedirect(reverse('task_manager:home'))
    return HttpResponseRedirect(reverse('user_system:admin_page'))


def login(request):
    form = CustomAuthenticationForm(request, data=request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        auth_login(request, user)  # user_logged_in signal will be triggered here
        return redirect_to_prev_page(request, reverse('task_manager:home'))
    elif request.method == 'POST':
        error_message = "Invalid username or password."

    return render(
        request,
        'login.html',
        {
            'form': form,
            'error_message': error_message,
        }
    )


def signup(request):
    error_message = None
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                email=form.cleaned_data['email']
            )
            user.name = form.cleaned_data['name']
            user.gender = form.cleaned_data['gender']
            user.age = form.cleaned_data['age']
            user.phone = form.cleaned_data['phone']
            user.occupation = form.cleaned_data['occupation']
            user.education = form.cleaned_data['education']
            user.field_of_expertise = form.cleaned_data['field_of_expertise']
            user.llm_frequency = form.cleaned_data['llm_frequency']
            user.llm_history = form.cleaned_data['llm_history']
            user.save()
            return HttpResponseRedirect(reverse('user_system:login'))
        else:
            error_fields = ', '.join(form.errors.keys())
            error_message = f"Required field(s) unfilled: {error_fields}"
    else:
        form = SignupForm()

    return render(
        request,
        'signup.html',
        {'form': form,
         'error_message': error_message,
        }
        )


def logout(request):
    auth_logout(request)
    return HttpResponseRedirect(reverse('user_system:login'))


@login_required
def info(request):
    return render(
        request,
        'info.html',
        {
            'cur_user': request.user,
        }
        )


@login_required
@user_passes_test(is_superuser)
def view_user_info(request, user_id):
    user_info = get_object_or_404(User, id=user_id)
    return render(
        request,
        'view_user_info.html',
        {
            'user_info': user_info,
        }
    )


@login_required
def edit_info(request):
    if request.method == 'POST':
        form = EditInfoForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('user_system:info'))
    else:
        form = EditInfoForm(instance=request.user)

    return render(
        request,
        'edit_info.html',
        {
            'cur_user': request.user,
            'form': form,
        }
    )


@login_required
def edit_password(request):
    form = EditPasswordForm(request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        if request.user.check_password(form.cleaned_data['cur_password']):
            request.user.set_password(form.cleaned_data['new_password'])
            request.user.save()
            return HttpResponseRedirect(reverse('user_system:info'))
        else:
            error_message = 'Incorrect current password.'
    elif request.method == 'POST':
        error_message = form.errors


    return render(
        request,
        'edit_password.html',
        {
            'cur_user': request.user,
            'form': form,
            'error_message': error_message,
        }
        )


def forget_password(request):
    form = ForgetPasswordForm(request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        try:
            user = User.objects.get(email=form.cleaned_data['email'])
            reset_request = ResetPasswordRequest.objects.create(user=user)
            # Assuming send_reset_password_email is a utility function you have defined
            # from .utils import send_reset_password_email
            send_reset_password_email(request.get_host(), reset_request)
            return HttpResponseRedirect(reverse('user_system:login'))
        except User.DoesNotExist:
            error_message = 'Email address not found.'
    elif request.method == 'POST':
        error_message = form.errors

    return render(
        request,
        'forget_password.html',
        {
            'form': form,
            'error_message': error_message,
        }
        )


def reset_password(request, token_str):
    token = get_object_or_404(ResetPasswordRequest, token=token_str)
    
    if token.is_expired:
        return render(
            request,
            'reset_password.html',
            {
                'form': None,
                'error_message': 'This token has expired. Please request a new password reset.'
            }
        )

    form = ResetPasswordForm(request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        user = token.user
        user.set_password(form.cleaned_data['new_password'])
        user.save()
        token.delete()
        return HttpResponseRedirect(reverse('user_system:login'))
    elif request.method == 'POST':
        error_message = form.errors

    return render(
        request,
        'reset_password.html',
        {
            'form': form,
            'error_message': error_message,
            'user': token.user,
        }
        )