from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import auth, db
import requests
from datetime import datetime
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

class RegisterView(APIView):
    def post(self, request):
        data = request.data
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        username = data.get('username')
        phone = data.get('phone')

        try:
            # Create user with email and password
            user = auth.create_user(
                email=email,
                password=password,
                display_name=name
            )

            # Format phone number for PH (+63)
            formatted_phone = f"+63{phone}" if phone else ""

            # Save user details in Realtime Database
            user_data = {
                "name": name,
                "email": email,
                "username": username,
                "phone": formatted_phone
            }

            # Store data under the user's UID
            db.reference(f'users/{user.uid}').set(user_data)

            # ✅ Initialize onboarding status
            initialize_onboarding_status(user.uid)

            return Response({
                "message": "User registered successfully",
                "uid": user.uid
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# 🔧 Helper method to initialize onboarding state
def initialize_onboarding_status(user_uid):
    onboarding_ref = db.reference(f'users/{user_uid}/onboardingStatus')
    onboarding_ref.set({
        'deviceAdded': False,
        'profileCreated': False,
        'growAdded': False
    })

class LoginView(APIView):
    def post(self, request):
        data = request.data
        identifier = data.get('identifier')  # Can be email or username
        password = data.get('password')

        try:
            # Check if identifier is an email or username
            if "@" in identifier:
                # Login using email
                email = identifier
            else:
                # Search for user by username in the database
                users_ref = db.reference('users').get()
                email = None
                for uid, user_data in users_ref.items():
                    if user_data.get('username') == identifier:
                        email = user_data.get('email')
                        break

                if not email:
                    return Response({"error": "Invalid username"}, status=status.HTTP_400_BAD_REQUEST)

            # Authenticate user using Firebase REST API
            api_key = settings.FIREBASE_API_KEY
            if not api_key:
                return Response({"error": "Firebase API key not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
            
            payload = {"email": email, "password": password, "returnSecureToken": True}
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                uid = auth.get_user_by_email(email).uid

                # Get user data from database
                user_data = db.reference(f'users/{uid}').get()
                
                return Response({
                    "token": data['idToken'],  # Firebase token
                    "user": {
                    "uid": uid,  
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                    "username": user_data.get("username"),
                    "phone": user_data.get("phone")
                }
            }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(APIView):
    def post(self, request):
        id_token = request.data.get("idToken")
        if not id_token:
            return Response({"error": "ID token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Verify token
            decoded_token = auth.verify_id_token(id_token)
            uid = decoded_token['uid']
            email = decoded_token.get('email')
            name = decoded_token.get('name')

            # 2. Check Realtime DB if user exists
            user_ref = db.reference(f'users/{uid}')
            user_data = user_ref.get()

            if not user_data:
                # Save if new
                user_data = {
                    "name": name,
                    "email": email,
                    "username": email.split("@")[0],
                    "phone": ""
                }
                user_ref.set(user_data)

            return Response({
                "message": "Google login success",
                "token": id_token,
                "user": {
                    "uid": uid,
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                    "username": user_data.get("username"),
                    "phone": user_data.get("phone")
                }
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class FirebaseResetPasswordView(APIView):
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Generate Firebase password reset link
            reset_link = auth.generate_password_reset_link(email)

            # Compose the plain-text content
            text_content = f"""
Hello,

We received a request to reset your password. Click the link below to choose a new password:

{reset_link}

If you didn't request a password reset, you can ignore this email.

Thanks,
HydroZap Team
            """

            # Compose the HTML content using Django template
            html_content = render_to_string('emails/password_reset.html', {'reset_link': reset_link})

            # Send the email via Django's email backend
            subject = "Reset Your Password"
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [email]

            # Create the email object with both plain text and HTML content
            msg = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
            msg.attach_alternative(html_content, "text/html")

            # Send the email
            msg.send()

            return Response({'message': 'Reset link sent to email.'}, status=status.HTTP_200_OK)

        except auth.UserNotFoundError:
            return Response({'error': 'No user with that email found.'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserProfileView(APIView):
    def get(self, request):
        uid = request.query_params.get("uid")  # Get user UID from query params

        if not uid:
            return Response({"error": "UID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_data = db.reference(f'users/{uid}').get()

            if not user_data:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            return Response({
                "uid": uid,
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "username": user_data.get("username"),
                "phone": user_data.get("phone")
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        data = request.data
        uid = data.get('uid')

        if not uid:
            return Response({"error": "UID is required"}, status=status.HTTP_400_BAD_REQUEST)

        updates = {}
        auth_updates = {}

        # Acceptable fields to update in Realtime Database
        for field in ['name', 'username', 'phone']:
            if field in data:
                updates[field] = data[field]

        # Password change
        if 'password' in data:
            new_password = data['password']
            if not new_password or len(new_password) < 6:
                return Response({"error": "Password must be at least 6 characters long"},
                                status=status.HTTP_400_BAD_REQUEST)
            auth_updates['password'] = new_password

        # Display name update in Firebase Auth if needed
        if 'name' in updates:
            auth_updates['display_name'] = updates['name']

        if not updates and not auth_updates:
            return Response({"error": "No valid fields to update"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Update Firebase Auth user fields
            if auth_updates:
                auth.update_user(uid, **auth_updates)

            # Update Realtime Database user fields
            if updates:
                db.reference(f'users/{uid}').update(updates)

            return Response({"message": "User profile updated successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
                      
class ProtectedView(APIView):
    def get(self, request):
        if not request.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({"message": "Welcome to HYDROZAP Secure Zone!"}, status=status.HTTP_200_OK)
  