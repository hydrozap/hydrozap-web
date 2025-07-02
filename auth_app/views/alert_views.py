from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import db
from datetime import datetime
import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .notification_utils import send_fcm_notification, should_send_notification, notify_alert_update

logger = logging.getLogger(__name__)

def get_suggested_action(alert_type, message=None):
    """Return a suggested action string for the given alert type."""
    if alert_type == 'ph_low':
        return 'Add pH Up solution to your reservoir. Check system for pH Down overdosing.'
    elif alert_type == 'ph_high':
        return 'Add pH Down solution to your reservoir. Check system for pH Up overdosing.'
    elif alert_type == 'ec_low':
        return 'Add nutrients to your reservoir according to your feeding schedule.'
    elif alert_type == 'ec_high':
        return 'Dilute your reservoir with fresh water. Consider replacing with fresh nutrient solution if extremely high.'
    elif alert_type == 'temp_low':
        return 'Increase environmental temperature or add a water heater to your reservoir.'
    elif alert_type == 'temp_high':
        return 'Decrease environmental temperature or add cooling to your reservoir. Consider adding shade if outdoors.'
    elif alert_type == 'water_low':
        return 'Refill your reservoir with water and nutrients as needed.'
    elif alert_type == 'device_offline':
        return 'Check your device power and internet connection. Ensure the device is plugged in and properly connected.'
    else:
        return 'Check your system and address the issue according to the alert message.'

class AlertView(APIView):
    def get(self, request, user_id=None, alert_id=None):
        """Retrieve alerts based on the URL pattern"""
        if user_id and alert_id:
            # Get a specific alert
            alert_ref = db.reference(f'alerts/{user_id}/{alert_id}')
            alert = alert_ref.get()

            if not alert:
                return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)
            # Add suggested action to the alert response
            alert_type = alert.get('alert_type', 'sensor')
            message = alert.get('message', '')
            alert['suggested_action'] = get_suggested_action(alert_type, message)
            return Response({"alert": alert}, status=status.HTTP_200_OK)
            
        elif user_id:
            # Get all alerts for a user
            alerts_ref = db.reference(f'alerts/{user_id}')
            alerts = alerts_ref.get()

            if not alerts:
                return Response({"alerts": []}, status=status.HTTP_200_OK)
            # Add suggested action to each alert
            for alert in alerts.values():
                alert_type = alert.get('alert_type', 'sensor')
                message = alert.get('message', '')
                alert['suggested_action'] = get_suggested_action(alert_type, message)
            return Response({"alerts": alerts}, status=status.HTTP_200_OK)
            
        else:
            # Invalid URL pattern
            return Response({"error": "Invalid URL pattern"}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        """Trigger a new alert"""
        data = request.data
        user_id = data.get('user_id')
        device_id = data.get('device_id')
        message = data.get('message')
        alert_type = data.get('alert_type', 'sensor')  # Default to sensor alert
        priority = data.get('priority', 'normal')  # Support for priority field

        if not user_id or not device_id or not message:
            return Response({"error": "user_id, device_id, and message are required"}, status=400)

        # Fetch the latest sensor data for the device
        latest_sensor_data = None
        try:
            sensors_ref = db.reference(f'devices/{device_id}/sensors')
            sensors = sensors_ref.get()
            if sensors and isinstance(sensors, dict):
                # Find the latest reading by timestamp
                latest = None
                for reading in sensors.values():
                    if isinstance(reading, dict) and 'timestamp' in reading:
                        if not latest or reading['timestamp'] > latest['timestamp']:
                            latest = reading
                latest_sensor_data = latest
        except Exception:
            latest_sensor_data = None

        # Create a unique alert ID
        alert_id = f"alert_{int(datetime.now().timestamp())}"
        alert_data = {
            "device_id": device_id,
            "message": message,
            "alert_type": alert_type,
            "status": "unread",
            "timestamp": datetime.now().isoformat(),
            "priority": priority,
            "sensor_data": latest_sensor_data  # Include the latest sensor data
        }
        
        try:
            # Always create the alert in the database regardless of notification preferences
            # This ensures the alert history is complete even if notifications are disabled
            db.reference(f'alerts/{user_id}/{alert_id}').set(alert_data)
            
            # Determine notification title based on alert type
            title = "\ud83c\udf31 HydroZap Alert"
            
            # Map alert types to consistent naming conventions
            # This ensures the notification preferences check uses the same keys 
            # as the ones stored in the user preferences
            specific_alert_type = alert_type
            
            # Use appropriate emoji for different alert types
            if "pH" in message.upper() or alert_type.startswith('ph'):
                title = "\u26a0\ufe0f pH Alert"
                # Keep the original alert type if it's already a specific pH type (ph_high, ph_low)
                if alert_type.startswith('ph_'):
                    specific_alert_type = alert_type  # Keep ph_high or ph_low as is
                else:
                    specific_alert_type = 'ph'  # Use generic 'ph' for unspecified pH alerts
                # Get user preferences to check pH setting
                try:
                    user_prefs_ref = db.reference(f'users/{user_id}/notification_preferences')
                    user_prefs = user_prefs_ref.get() or {}
                    ph_enabled = user_prefs.get('ph_level_alerts_enabled')
                except Exception:
                    pass
            elif "EC" in message.upper() or alert_type == 'ec':
                title = "\u26a0\ufe0f EC/TDS Alert"
                specific_alert_type = 'ec'
            elif "temperature" in message.lower() or alert_type == 'temperature':
                title = "\ud83c\udf21\ufe0f Temperature Alert"
                specific_alert_type = 'temperature'
            elif "humidity" in message.lower() or alert_type == 'humidity':
                title = "\ud83d\udca7 Humidity Alert"
                specific_alert_type = 'humidity'
            elif "water" in message.lower() or alert_type == 'water_level':
                title = "\ud83d\udeb0 Water Level Alert"
                specific_alert_type = 'water_level'
            elif alert_type == 'critical':
                title = "\ud83d\udea8 CRITICAL ALERT"
                specific_alert_type = 'critical'
            
            # Get device name to include in notification data
            device_name = None
            try:
                device_ref = db.reference(f'devices/{device_id}')
                device_data = device_ref.get()
                if device_data:
                    device_name = device_data.get('device_name', f"Device {device_id}")
            except Exception:
                pass
            
            # Prepare notification data
            notification_data = {
                "alert_id": alert_id,
                "device_id": device_id,
                "device_name": device_name,
                "type": specific_alert_type,
                "priority": priority,
                "click_action": "OPEN_ALERTS_SCREEN"
            }
            
            # Update the alert in the database with the specific alert type if it was changed
            if specific_alert_type != alert_type:
                db.reference(f'alerts/{user_id}/{alert_id}').update({"alert_type": specific_alert_type})
                # Also update our local copy
                alert_data["alert_type"] = specific_alert_type
            
            # Check if we should send FCM notification based on user preferences
            if priority == 'high' or should_send_notification(user_id, 'push', specific_alert_type):
                # Send FCM notification (high priority alerts bypass user preferences)
                fcm_result = send_fcm_notification(user_id, title, message, notification_data)
            else:
                fcm_result = {
                    "success": 0, 
                    "failure": 0, 
                    "blocked_by_preferences": True,
                    "message": f"Notification blocked by user preferences for alert type: {specific_alert_type}"
                }
            
        except Exception as e:
            return Response({"error": f"Failed to save alert: {str(e)}"}, status=500)

        # Always notify WebSocket clients about the new alert
        # This ensures the alert appears in the UI even if push notification is disabled
        notify_alert_update(user_id, alert_id, message, specific_alert_type)

        return Response({
            "message": "Alert triggered successfully", 
            "alert_id": alert_id,
            "alert": alert_data,
            "fcm_result": fcm_result if 'fcm_result' in locals() else None,
            "suggested_action": get_suggested_action(alert_data.get('alert_type', 'sensor'), alert_data.get('message', ''))
        }, status=status.HTTP_201_CREATED)

    def put(self, request, user_id, alert_id):
        """Update a specific alert (e.g., mark as read)"""
        # Check if alert exists
        alert_ref = db.reference(f'alerts/{user_id}/{alert_id}')
        alert = alert_ref.get()
        
        if not alert:
            return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Get update data
        data = request.data
        status_value = data.get('status')
        
        # Only update allowed fields
        updates = {}
        if status_value:
            updates['status'] = status_value
        
        # If no updates provided
        if not updates:
            return Response({"error": "No valid update fields provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update the alert
        alert_ref.update(updates)
        
        # Get the updated alert
        updated_alert = alert_ref.get()
        
        return Response({
            "message": "Alert updated successfully",
            "alert": updated_alert
        }, status=status.HTTP_200_OK)

    def delete(self, request, user_id, alert_id):
        """Delete a specific alert"""
        alert_ref = db.reference(f'alerts/{user_id}/{alert_id}')
        if not alert_ref.get():
            return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)

        alert_ref.delete()
        return Response({"message": "Alert deleted successfully"}, status=status.HTTP_200_OK)

class AlertCountView(APIView):
    def get(self, request, user_id):
        """Get count of alerts for a user"""
        try:
            # Get alerts for the user
            alerts_ref = db.reference(f'alerts/{user_id}')
            alerts = alerts_ref.get()
            
            # Count alerts
            alert_count = len(alerts) if alerts else 0
            
            return Response({"alert_count": alert_count}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)