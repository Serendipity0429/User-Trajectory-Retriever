import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

class ExtensionSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only apply middleware to API paths
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return self.get_response(request)

        token = auth_header.split(' ')[1]
        session_token_header = request.headers.get('X-Extension-Session-Token')

        try:
            # Decode the token to get user_id without full validation yet
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')
            
            if user_id is None:
                raise TokenError('Token contains no user ID')

            user = User.objects.get(id=user_id)

            # Compare session tokens
            if user.extension_session_token != session_token_header:
                return JsonResponse({'error': 'Invalid session. Please log in again.', 'error_code': 'INVALID_SESSION'}, status=401)

        except (InvalidToken, TokenError, User.DoesNotExist) as e:
            # This will be caught by the standard JWT authentication, 
            # but we can return a specific error if we want.
            return JsonResponse({'error': str(e)}, status=401)

        response = self.get_response(request)
        return response
