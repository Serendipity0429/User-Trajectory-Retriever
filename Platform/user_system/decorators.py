from functools import wraps
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect

from functools import wraps
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import HttpResponseForbidden

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse('user_system:login')
            return redirect(f'{login_url}?next={request.path}')
        if not request.user.is_superuser:
            return render(request, 'error_page.html', status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def consent_exempt(view_func):
    """
    Mark a view function as being exempt from the informed consent enforcement.
    """

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)

    # Set the exempt flag
    wrapped_view.consent_exempt = True
    return wrapped_view
