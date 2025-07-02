from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import db, messaging
from datetime import datetime
import hashlib
import logging
from .sensor_views import send_fcm_notification

logger = logging.getLogger(__name__)

class FcmTokenView(APIView):
    def post(self, request):
        """Register a FCM token for a user"""
        data = request.data
        user_id = data.get('user_id')
        token = data.get('fcm_token')
        
        if not user_id or not token:
            return Response({"error": "User ID and FCM token are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Save token to user's FCM tokens collection
            tokens_ref = db.reference(f'users/{user_id}/fcm_tokens')
            
            # Use a hash of the token as a key to avoid duplicates
            import hashlib
            token_hash = hashlib.md5(token.encode()).hexdigest()
            
            token_data = {
                "token": token,
                "created_at": datetime.now().isoformat(),
                "last_used": datetime.now().isoformat(),
                "is_active": True
            }
            
            tokens_ref.child(token_hash).set(token_data)
            
            return Response({
                "message": "FCM token registered successfully",
                "user_id": user_id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"Error registering FCM token: {str(e)}")
            return Response({
                "error": f"Failed to register FCM token: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request):
        """Unregister a FCM token"""
        data = request.data
        user_id = data.get('user_id')
        token = data.get('fcm_token')
        
        if not user_id or not token:
            return Response({"error": "User ID and FCM token are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Calculate token hash
            import hashlib
            token_hash = hashlib.md5(token.encode()).hexdigest()
            
            # Get reference to the specific token
            token_ref = db.reference(f'users/{user_id}/fcm_tokens/{token_hash}')
            
            # Check if token exists
            if not token_ref.get():
                return Response({"error": "Token not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # Delete the token
            token_ref.delete()
            
            return Response({
                "message": "FCM token unregistered successfully",
                "user_id": user_id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error unregistering FCM token: {str(e)}")
            return Response({
                "error": f"Failed to unregister FCM token: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TestFcmNotificationView(APIView):
    """Test endpoint for sending FCM notifications directly"""
    def post(self, request):
        data = request.data
        user_id = data.get('user_id')
        title = data.get('title', 'Test Notification')
        body = data.get('body', 'This is a test notification from HydroZap')
        payload = data.get('data', {})
        
        if not user_id:
            return Response({"error": "user_id is required"}, 
                          status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # Send test notification
            result = send_fcm_notification(user_id, title, body, payload)
            
            return Response({
                "message": "Test notification sent",
                "result": result
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error": f"Failed to send test notification: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationPreferencesView(APIView):
    """API endpoint for managing notification preferences"""
    
    def get(self, request, user_id):
        """Get notification preferences for a user"""
        try:
            # Get preferences from Firebase
            prefs_ref = db.reference(f'users/{user_id}/notification_preferences')
            preferences = prefs_ref.get()
            
            if not preferences:
                return Response({"message": "No preferences found"}, status=status.HTTP_200_OK)
                
            return Response({"preferences": preferences}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def patch(self, request):
        """Update notification preferences for a user"""
        try:
            data = request.data
            user_id = data.get('user_id')
            preferences = data.get('preferences')
            
            if not user_id:
                return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)
                
            if not preferences:
                return Response({"error": "Preferences data is required"}, status=status.HTTP_400_BAD_REQUEST)
                
            # Update preferences in Firebase
            prefs_ref = db.reference(f'users/{user_id}/notification_preferences')
            prefs_ref.update(preferences)
            
            return Response({
                "message": "Notification preferences updated successfully",
                "user_id": user_id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def send_fcm_notification(user_id, title, body, data=None):
    """Send FCM notification to a user"""
    try:
        # Get user's FCM tokens
        tokens_ref = db.reference(f'users/{user_id}/fcm_tokens')
        tokens = tokens_ref.get()
        
        if not tokens:
            return {"error": "No FCM tokens found for user"}
        
        # Get active tokens
        active_tokens = [
            token_data['token'] 
            for token_data in tokens.values() 
            if token_data.get('is_active', False)
        ]
        
        if not active_tokens:
            return {"error": "No active FCM tokens found for user"}
        
        # Prepare message
        message = messaging.MulticastMessage(
            data=data or {},
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            tokens=active_tokens
        )
        
        # Send message
        response = messaging.send_multicast(message)
        
        # Update token status based on response
        for idx, result in enumerate(response.responses):
            token = active_tokens[idx]
            token_hash = hashlib.md5(token.encode()).hexdigest()
            
            if result.success:
                # Update last used timestamp
                tokens_ref.child(token_hash).update({
                    "last_used": datetime.now().isoformat()
                })
            else:
                # Mark token as inactive if it failed
                tokens_ref.child(token_hash).update({
                    "is_active": False,
                    "error": str(result.error)
                })
        
        return {
            "success_count": response.success_count,
            "failure_count": response.failure_count
        }
        
    except Exception as e:
        print(f"Error sending FCM notification: {str(e)}")
        return {"error": str(e)} 