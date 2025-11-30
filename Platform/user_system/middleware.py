from django.contrib.auth import logout


class ExtensionSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and "extension_session_token" in request.session
        ):
            if (
                request.user.extension_session_token
                != request.session["extension_session_token"]
            ):
                logout(request)

        response = self.get_response(request)
        return response


class EnforceConsentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        from django.shortcuts import redirect
        from .models import InformedConsent

        if getattr(view_func, "consent_exempt", False):
            return None

        if (
            hasattr(request, "user")
            and request.user.is_authenticated
            and not request.user.is_superuser
        ):
            latest_consent = InformedConsent.get_latest()
            if latest_consent:
                if (
                    request.user.agreed_consent_version != latest_consent
                    or not request.user.consent_agreed
                ):
                    # Store the current path to redirect back after consent
                    request.session["prev_page"] = request.get_full_path()
                    # Redirect the user to the consent page
                    return redirect("user_system:informed_consent")
        return None
