from firebase_admin import messaging
from firebase_admin import db
import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import datetime

logger = logging.getLogger(__name__)

def send_fcm_notification(user_id, title, body, data=None):
    """Send FCM notification to a user's devices"""
    try:
        # Get user's FCM tokens
        user_ref = db.reference(f'users/{user_id}/fcm_tokens')
        tokens = user_ref.get()
        
        if not tokens:
            logger.warning(f"No FCM tokens found for user {user_id}")
            return False
            
        # Convert tokens to list of strings and filter out invalid ones
        token_list = [str(token) for token in tokens.values() if token]
        
        if not token_list:
            logger.warning(f"No valid FCM tokens found for user {user_id}")
            return False
        
        # Create message
        message = messaging.MulticastMessage(
            data=data or {},
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            tokens=token_list
        )
        
        # Send message
        response = messaging.send_multicast(message)
        
        # Log results
        if response.failure_count > 0:
            logger.warning(f"Some notifications failed to send: {response.failure_count} failures")
            
        return response.success_count > 0
        
    except Exception as e:
        logger.error(f"Error sending FCM notification: {str(e)}")
        return False

def should_send_notification(alert_type, current_value, threshold_value):
    """Determine if a notification should be sent based on alert type and values"""
    try:
        if alert_type == 'high':
            return float(current_value) > float(threshold_value)
        elif alert_type == 'low':
            return float(current_value) < float(threshold_value)
        return False
    except (ValueError, TypeError):
        return False

def notify_alert_update(user_id, alert_id, message, alert_type):
    """Notify WebSocket clients about alert updates"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                "type": "alert.update",
                "message": {
                    "alert_id": alert_id,
                    "message": message,
                    "alert_type": alert_type,
                    "timestamp": datetime.now().isoformat()
                }
            }
        )
    except Exception as e:
        logger.error(f"Error sending WebSocket notification: {str(e)}") 