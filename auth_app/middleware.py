# auth_app/middleware.py
from firebase_admin import auth
from rest_framework.exceptions import AuthenticationFailed
from .firebase import initialize_firebase

class FirebaseAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        initialize_firebase()  # Initialize Firebase when middleware is loaded

    def __call__(self, request):
        token = request.headers.get('Authorization')

        if token:
            try:
                # Remove 'Bearer ' if present
                token = token.replace('Bearer ', '')
                decoded_token = auth.verify_id_token(token)
                request.user = decoded_token
            except Exception as e:
                raise AuthenticationFailed(f"Invalid Token: {str(e)}")

        return self.get_response(request)
