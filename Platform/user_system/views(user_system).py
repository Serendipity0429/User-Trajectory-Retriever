#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template import RequestContext
from .forms import *
from .models import User, ResetPasswordRequest, TimestampGenerator
from .utils import *
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

__DEBUG__ = True


@csrf_exempt
def check(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        print('username: ', username)
        print('password: ', password)   
        error_code, user = authenticate(username, password)
        if __DEBUG__:
            print('error_code: ', error_code)
        return HttpResponse(error_code)


def token_login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    username = request.POST.get('username')
    password = request.POST.get('password')

    error_code, user = authenticate(username, password)

    if error_code == 0:
        # 认证成功，生成JWT令牌
        refresh = RefreshToken.for_user(user)
        user.login_num += 1
        user.last_login = now()
        user.save()

        return JsonResponse({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    else:
        error_messages = {
            1: 'User does not exist',
            2: 'Incorrect password',
        }
        return JsonResponse({
            'error': error_messages.get(error_code, 'Authentication failed'),
            'error_code': error_code
        }, status=401)

def login(request):
    form = LoginForm()
    error_message = None

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            if not request.session.test_cookie_worked():
                error_message = u'Cookie错误，请再试一次'
            else:
                username = form.cleaned_data['username']
                password = form.cleaned_data['password']
                error_code, user = authenticate(username, password)
                if error_code == 0:
                    user.login_num += 1
                    user.last_login = now()
                    user.save()
                    store_in_session(request, user)
                    return redirect_to_prev_page(request, '/task/home/')
                elif error_code == 1:
                    error_message = u'用户不存在，请检查用户名是否正确'
                elif error_code == 2:
                    error_message = u'密码错误，请重新输入密码'
        else:
            error_message = u'表单输入错误'

    request.session.set_test_cookie()
    return render(
        request,
        'login.html',
        {
            'form': form,
            'error_message': error_message,
        }
    )


def signup(request):
    form = SignupForm()
    error_message = None

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User()
            user.username = form.cleaned_data['username']
            user.password = form.cleaned_data['password']
            user.name = form.cleaned_data['name']
            user.sex = form.cleaned_data['sex']
            user.age = form.cleaned_data['age']
            user.phone = form.cleaned_data['phone']
            user.email = form.cleaned_data['email']
            user.occupation = form.cleaned_data['occupation']
            user.llm_frequency = form.cleaned_data['llm_frequency']
            user.llm_history = form.cleaned_data['llm_history']
            user.signup_time = now()
            user.last_login = now()
            user.login_num = 0
            user.save()
            return HttpResponseRedirect('/user/login/')
        else:
            error_message = form.errors

    return render(
        request,
        'signup.html',
        {'form': form,
         'error_message': error_message,
        }
        )


def logout(request):
    if 'username' in request.session:
        del request.session['username']
    if 'prev_page' in request.session:
        del request.session['prev_page']
    return HttpResponseRedirect('/user/login/')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def info(user, request):
    # user_group_string = get_user_groups_string(user.user_groups)
    llm_frequency_choices = {
        '': u'',
        'frequently': u'每天使用多次',
        'usually': u'平均每天使用一次',
        'sometimes': u'每周偶尔使用两三次',
        'rarely': u'平均每周使用不超过一次'
    }
    llm_history_choices = {
        '': u'',
        'very long': u'5年以上',
        'long': u'3年~5年',
        'short': u'1年~3年',
        'very short': u'1年以内'
    }
    llm_frequency = llm_frequency_choices[user.llm_frequency]
    llm_history = llm_history_choices[user.llm_history]
    return render(
        request,
        'info.html',
        {
            'cur_user': user,
            'llm_frequency': llm_frequency,
            'llm_history': llm_history
            # 'user_group_string': user_group_string
        }
        )


@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def edit_info(user, request):
    form = EditInfoForm(
        {
            'name': user.name,
            'sex': user.sex,
            'age': user.age,
            'phone': user.phone,
            'email': user.email,
            'field': user.field,
            'llm_frequency': user.llm_frequency,
            'llm_history': user.llm_history
        })
    error_message = None

    if request.method == 'POST':
        form = EditInfoForm(request.POST)
        if form.is_valid():
            user.name = form.cleaned_data['name']
            user.sex = form.cleaned_data['sex']
            user.age = form.cleaned_data['age']
            user.phone = form.cleaned_data['phone']
            user.email = form.cleaned_data['email']
            user.field = form.cleaned_data['field']
            user.llm_frequency = form.cleaned_data['llm_frequency']
            user.llm_history = form.cleaned_data['llm_history']
            user.save()
            return HttpResponseRedirect('/user/info/')
        else:
            error_message = form.errors
    else:
        return render(
            request,
            'edit_info.html',
            {
                'cur_user': user,
                'form': form,
                'error_message': error_message,
            }
            )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def edit_password(user, request):
    form = EditPasswordForm()
    error_message = None

    if request.method == 'POST':
        form = EditPasswordForm(request.POST)
        if form.is_valid():
            if user.password == form.cleaned_data['cur_password']:
                user.password = form.cleaned_data['new_password']
                user.save()
                return HttpResponseRedirect('/user/info/')
            else:
                error_message = '原密码错误'
        else:
            error_message = form.errors
    else:
        return render(
            request,
            'edit_password.html',
            {
                'cur_user': user,
                'form': form,
                'error_message': error_message,
            }
            )


def forget_password(request):
    form = ForgetPasswordForm()
    error_message = None

    if request.method == 'POST':
        form = ForgetPasswordForm(request.POST)
        if form.is_valid():
            user = User.objects.filter(email=form.cleaned_data['email'])
            if user is None or len(user) == 0:
                error_message = u'Email地址不存在'
            else:
                user = user[0]
                reset_request = ResetPasswordRequest.objects.create(
                    user=user
                )
                reset_request.save()
                send_reset_password_email(request, reset_request)
                return HttpResponseRedirect('/user/login/')
        else:
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
    form = ResetPasswordForm()
    token = None
    error_message = None

    try:
        token = ResetPasswordRequest.objects.get(token=token_str)
        print (TimestampGenerator(0)())
        print (token.expire)
        if TimestampGenerator(0)() > token.expire:
            error_message = u'Token已失效，请重新找回密码'
    except ResetPasswordRequest.DoesNotExist:
        error_message = u'链接地址错误，请重新找回密码'

    if error_message is not None:
        return render(
            request,
            'reset_password.html',
            {
                'form': None,
                'error_message': error_message
            }
            )

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user = token.user
            user.password = form.cleaned_data['new_password']
            user.save()
            token.delete()
            return HttpResponseRedirect('/user/login/')
        else:
            error_message = form.errors

    return render(
        request,
        'reset_password.html',
        {
            'form': form,
            'error_message': error_message,
        }
        )
