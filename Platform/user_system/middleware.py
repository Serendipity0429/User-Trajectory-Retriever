from django.contrib.auth import logout
from django.urls import reverse
from django.shortcuts import redirect
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

class ExtensionSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and 'extension_session_token' in request.session:
            if request.user.extension_session_token != request.session['extension_session_token']:
                logout(request)
        
        response = self.get_response(request)
        return response

class EnforceConsentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.urls import reverse
        from django.shortcuts import redirect
        from .models import InformedConsent

        if hasattr(request, 'user') and request.user.is_authenticated and not request.user.is_superuser:
            latest_consent = InformedConsent.get_latest()
            if latest_consent:
                if request.user.agreed_consent_version != latest_consent or not request.user.consent_agreed:
                    # Add exceptions for logout and consent pages
                    if request.path not in [reverse('user_system:logout'), reverse('user_system:informed_consent')]:
                        # Redirect the user to the consent page
                        return redirect('user_system:informed_consent')

        response = self.get_response(request)
        return response