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
import json
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.templatetags.static import static
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.views import View
from django.core.signing import Signer, BadSignature
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from task_manager.models import Task, ExtensionVersion
from task_manager.forms import ExtensionVersionForm
from task_manager.views import get_pending_annotation
from rest_framework_simplejwt.tokens import RefreshToken
from .forms import EditInfoForm, ForgetPasswordForm, ResetPasswordForm
from .utils import send_reset_password_email
from discussion.models import Bulletin, Post, Comment

USER_SEARCH_RESULT_LIMIT = 8

def is_superuser(user):
    return user.is_superuser

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
            Q(profile__name__icontains=user_search_query)
        ).order_by(user_order)
    else:
        users_list = User.objects.all().order_by(user_order)

    user_paginator = Paginator(users_list, 10)
    user_page_number = request.GET.get('user_page')
    users = user_paginator.get_page(user_page_number)

    # Task filter and sort
    task_user_filter = request.GET.get('task_user', '')
    task_date_start_filter = request.GET.get('task_date_start', '')
    task_date_end_filter = request.GET.get('task_date_end', '')
    task_sort_by = request.GET.get('task_sort_by', 'start_timestamp')
    task_sort_dir = request.GET.get('task_sort_dir', 'desc')
    if task_sort_dir not in ['asc', 'desc']:
        task_sort_dir = 'asc'
    task_order = f"{'-' if task_sort_dir == 'desc' else ''}{task_sort_by}"

    tasks_list = Task.objects.all()
    if task_user_filter:
        tasks_list = tasks_list.filter(user__id=task_user_filter)
    if task_date_start_filter:
        tasks_list = tasks_list.filter(start_timestamp__date__gte=task_date_start_filter)
    if task_date_end_filter:
        tasks_list = tasks_list.filter(start_timestamp__date__lte=task_date_end_filter)
    tasks_list = tasks_list.order_by(task_order)

    task_paginator = Paginator(tasks_list, 10)
    task_page_number = request.GET.get('task_page')
    tasks = task_paginator.get_page(task_page_number)

    if request.GET.get('ajax'):
        tasks_data = []
        for task in tasks:
            status_badge = ''
            if task.cancelled:
                status_badge = '<span class="badge bg-danger">Cancelled</span>'
            elif not task.active:
                status_badge = '<span class="badge bg-success">Completed</span>'
            else:
                status_badge = '<span class="badge bg-warning">Active</span>'
            
            tasks_data.append({
                'id': task.id,
                'user': task.user.username,
                'start_timestamp': task.start_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                'status_badge': status_badge,
            })
        return JsonResponse({'tasks': tasks_data})

    # Dashboard metrics
    total_users = User.objects.count()
    superusers = User.objects.filter(is_superuser=True).count()
    thirty_days_ago = timezone.now() - timedelta(days=30)
    active_users = User.objects.filter(last_login__gte=thirty_days_ago).count()
    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(cancelled=False, active=False).count()
    cancelled_tasks = Task.objects.filter(cancelled=True).count()
    active_tasks = Task.objects.filter(active=True).count()
    total_bulletins = Bulletin.objects.count()
    total_posts = Post.objects.count()
    total_comments = Comment.objects.count()

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
            'task_date_start_filter': task_date_start_filter,
            'task_date_end_filter': task_date_end_filter,
            'task_sort_by': task_sort_by,
            'task_sort_dir': task_sort_dir,
            'total_users': total_users,
            'superusers': superusers,
            'active_users': active_users,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'cancelled_tasks': cancelled_tasks,
            'active_tasks': active_tasks,
            'total_bulletins': total_bulletins,
            'total_posts': total_posts,
            'total_comments': total_comments,
        }
    )


@csrf_exempt
def token_login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        print_debug(request.POST)
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Assuming 'authenticate' is a custom utility function you have defined in utils.py
        # from .utils import authenticate
        error_code, user = authenticate(username, password)

        if error_code == 0 and user:
            # Authentication successful, generate JWT token
            print_debug(f'User {username} authenticated successfully for token login')
            refresh = RefreshToken.for_user(user)
            user.login_num += 1
            user.last_login = now()
            user.save()

            return JsonResponse({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        else:
            print_debug(f'User {username} authentication failed with error code {error_code}')
            error_messages = {
                1: 'User does not exist',
                2: 'Incorrect password',
                4: 'Authentication failed',
            }
            return JsonResponse({
                'error': error_messages.get(error_code, 'Authentication failed'),
                'error_code': error_code
            }, status=401)
    except Exception as e:
        logging.error(f"An unexpected error occurred during token login: {e}")
        return JsonResponse({
            'error': 'An unexpected error occurred. Please try again later.',
            'error_code': 3
        }, status=500)


@login_required
@user_passes_test(is_superuser)
def delete_user(request, user_id):
    if request.method == 'POST':
        user_to_delete = get_object_or_404(User, id=user_id)
        if request.user.id == user_to_delete.id:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'You cannot delete yourself.'}, status=400)
            else:
                return HttpResponseRedirect(reverse('user_system:admin_page'))
        
        user_to_delete.delete()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'User deleted successfully.'})
        else:
            return HttpResponseRedirect(reverse('user_system:admin_page'))
    
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
            original_admin_id = request.user.id
            
            # Log in as the new user first, as this may flush the session
            auth_login(request, user_to_login)
            
            # Now, set the token in the new session
            signer = Signer()
            request.session['original_user_token'] = signer.sign(original_admin_id)
            
            return HttpResponseRedirect(reverse('task_manager:home'))
    return HttpResponseRedirect(reverse('user_system:admin_page'))


@login_required
@require_POST
def return_to_admin(request):
    signed_token = request.session.pop('original_user_token', None)
    if signed_token:
        signer = Signer()
        try:
            admin_id = signer.unsign(signed_token)
            admin_user = get_object_or_404(User, id=admin_id)
            auth_login(request, admin_user)
        except (BadSignature, User.DoesNotExist):
            # The invalid token has already been removed.
            # We can simply redirect without any further action.
            pass
    return HttpResponseRedirect(reverse('user_system:admin_page'))


def login(request):
    form = CustomAuthenticationForm(request, data=request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        auth_login(request, user)  # user_logged_in signal will be triggered here
        messages.success(request, 'Successfully logged in.')
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
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                email=form.cleaned_data['email']
            )
            profile = user.profile
            profile.name = form.cleaned_data['name']
            profile.gender = form.cleaned_data['gender']
            profile.age = form.cleaned_data['age']
            profile.phone = form.cleaned_data['phone']
            profile.occupation = form.cleaned_data['occupation']
            profile.education = form.cleaned_data['education']
            profile.field_of_expertise = form.cleaned_data['field_of_expertise']
            profile.llm_frequency = form.cleaned_data['llm_frequency']
            profile.llm_history = form.cleaned_data['llm_history']
            profile.save()
            return HttpResponseRedirect(reverse('user_system:login'))
        else:
            # Store form data and errors in session, then redirect
            request.session['signup_form_data'] = request.POST
            request.session['signup_form_errors'] = form.errors.as_json()
            return HttpResponseRedirect(reverse('user_system:signup'))
    else:
        # On GET, check for session data from a failed POST
        form_data = request.session.pop('signup_form_data', None)
        # Clear any lingering error session data, as it's not needed
        request.session.pop('signup_form_errors', None)

        if form_data:
            # Recreate the form with the user's data.
            # Validation errors will be regenerated when the template accesses them.
            form = SignupForm(form_data)
        else:
            # This is a fresh GET, create an empty form
            form = SignupForm()

    return render(
        request,
        'signup.html',
        {'form': form}
    )


def logout(request):
    auth_logout(request)
    return HttpResponseRedirect(reverse('user_system:login'))

def health_check(request):
    return JsonResponse({'status': 'ok'})

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
        form = EditInfoForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            request.user.email = form.cleaned_data['email']
            request.user.save()
            form.save()
            return HttpResponseRedirect(reverse('user_system:info'))
    else:
        form = EditInfoForm(instance=request.user.profile, initial={'email': request.user.email})

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

@login_required
@user_passes_test(is_superuser)
def manage_extension_versions(request):
    if request.method == 'POST':
        form = ExtensionVersionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'New extension version added successfully.')
            return HttpResponseRedirect(reverse('user_system:manage_extension_versions'))
    else:
        form = ExtensionVersionForm()

    versions = ExtensionVersion.objects.all().order_by('-id')
    return render(request, 'manage_extension_versions.html', {'form': form, 'versions': versions})


@login_required
@user_passes_test(is_superuser)
@require_POST
def revert_latest_extension_version(request):
    latest_version = ExtensionVersion.objects.order_by('-id').first()
    if latest_version:
        version_number = latest_version.version
        latest_version.delete()
        messages.success(request, f'Successfully reverted version {version_number}.')
    else:
        messages.warning(request, 'No extension versions to revert.')
    return HttpResponseRedirect(reverse('user_system:manage_extension_versions'))


class UserSearchView(LoginRequiredMixin, View):
    def get(self, request):
        term = request.GET.get('term', '')
        User = get_user_model()
        users = User.objects.filter(
            Q(username__icontains=term) | Q(profile__name__icontains=term)
        ).exclude(pk=request.user.pk).select_related('profile')[:USER_SEARCH_RESULT_LIMIT]
        
        results = []
        for user in users:
            # Use default static image if icon is not set
            image_url = user.profile.icon.url if user.profile.icon else static('img/default.jpg')
            
            results.append({
                'id': user.id,
                'label': user.username, # Keep for accessibility
                'value': user.username,
                'name': user.profile.name or user.username,
                'username': user.username,
                'image_url': image_url
            })
        return JsonResponse(results, safe=False)

