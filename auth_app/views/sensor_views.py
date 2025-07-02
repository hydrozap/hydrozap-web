from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import db
from datetime import datetime
from .device_views import DeviceView
from .notification_utils import send_fcm_notification, should_send_notification, notify_alert_update
from .alert_views import get_suggested_action
import os
import random
from datetime import timedelta
import logging
import json
import requests
from django.conf import settings
import jwt
from django.core.cache import cache
from firebase_admin import messaging
from ..firebase import initialize_firebase, is_fcm_available

logger = logging.getLogger(__name__)

class SensorDataView(APIView):
    def post(self, request):
        data = request.data
        required_fields = ['device_id', 'temperature', 'humidity', 'ph', 'ec', 'tds', 'waterLevel']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return Response({"error": f"Missing fields: {', '.join(missing_fields)}"}, status=400)

        device_id = data['device_id']
        sensor_data = {
            'temperature': data['temperature'],
            'humidity': data['humidity'],
            'ph': data['ph'],
            'ec': data['ec'],
            'tds': data['tds'],
            'waterLevel': data['waterLevel'],
            'timestamp': datetime.now().isoformat()
        }

        # 🔍 Check if device exists
        device_ref = db.reference(f'devices/{device_id}')
        if not device_ref.get():
            return Response({"error": "Add the device first before the sensor sends data."}, status=404)

        # ✅ Save new sensor data under unique key
        sensors_ref = device_ref.child('sensors')
        sensors_ref.push(sensor_data)

        # 🔄 Update top-level sensor values (for easy access)
        sensors_ref.update(sensor_data)

        # 🚨 Check for alerts
        triggered_alerts = self.check_conditions(device_id, data['ph'], data['ec'])

        response_data = {
            "message": "Sensor data updated successfully",
        }

        if triggered_alerts:
            response_data["alerts_triggered"] = len(triggered_alerts)
            response_data["alerts"] = triggered_alerts

        return Response(response_data, status=200)

    def check_conditions(self, device_id, ph, ec):
        """Check grow conditions and trigger alerts if necessary"""
        grows_ref = db.reference('grows')
        grows = grows_ref.order_by_child('device_id').equal_to(device_id).get()
        
        triggered_alerts = []  # Track triggered alerts for response

        if grows:
            for grow_id, grow in grows.items():
                controls = grow.get('controls', {}).get('condition', [])
                user_id = grow.get('user_id')

                for condition in controls:
                    sensor_type = condition['sensor']
                    value = condition['value']
                    operator = condition['operator']
                    action = condition['action']
                    actuator = condition['actuator']

                    # Set specific alert type based on sensor type and condition
                    specific_alert_type = "sensor"  # Default
                    if sensor_type == "pH":
                        if operator == "<":
                            specific_alert_type = "ph_low"
                        elif operator == ">":
                            specific_alert_type = "ph_high"
                        else:
                            specific_alert_type = "ph"
                    elif sensor_type == "EC":
                        if operator == "<":
                            specific_alert_type = "ec_low"
                        elif operator == ">":
                            specific_alert_type = "ec_high"
                        else:
                            specific_alert_type = "ec"
                    # You can add more sensor types here (e.g., tds_high/low, temp_high/low, etc.)

                    if (sensor_type == "pH" and self.evaluate_condition(ph, operator, value)) or (
                            sensor_type == "EC" and self.evaluate_condition(ec, operator, value)):
                        message = f"{sensor_type} {operator} {value}: {action} {actuator}"
                        alert_id, alert_data = self.create_alert(user_id, device_id, message, specific_alert_type)
                        
                        # Add to triggered alerts
                        triggered_alerts.append({
                            "alert_id": alert_id,
                            "alert_data": alert_data,
                            "grow_id": grow_id
                        })
        
        return triggered_alerts

    def evaluate_condition(self, sensor_value, operator, threshold):
        """Evaluate sensor value based on operator"""
        if operator == "<":
            return sensor_value < threshold
        elif operator == ">":
            return sensor_value > threshold
        elif operator == "==":
            return sensor_value == threshold
        return False

    def create_alert(self, user_id, device_id, message, alert_type):
        """Create and store alert for user, with a 10-minute interval check"""
        # Check for recent alert of the same type for this device/user
        alerts_ref = db.reference(f'alerts/{user_id}')
        alerts = alerts_ref.order_by_child('device_id').equal_to(device_id).get()
        now = datetime.now()
        latest_time = None
        for alert in (alerts or {}).values():
            if alert.get('alert_type') == alert_type:
                ts = alert.get('timestamp')
                if ts:
                    try:
                        alert_time = datetime.fromisoformat(ts)
                        if not latest_time or alert_time > latest_time:
                            latest_time = alert_time
                    except Exception:
                        continue
        # 10-minute interval check
        if latest_time and now - latest_time < timedelta(minutes=10):
            return None, None  # Skip creating alert/notification
        
        alert_ref = db.reference(f'alerts/{user_id}')
        alert_id = f"alert_{int(datetime.now().timestamp())}"
        
        # Use the provided alert_type directly (already includes high/low if set above)
        alert_data = {
            "device_id": device_id,
            "message": message,
            "alert_type": alert_type,  # Now includes high/low if appropriate
            "status": "unread",
            "timestamp": datetime.now().isoformat(),
            "suggested_action": get_suggested_action(alert_type, message)
        }
        
        # Verify the alert can be written to Firebase
        try:
            alert_ref.child(alert_id).set(alert_data)
            
            # Send push notification for the alert
            # Extract sensor type from message (e.g., "pH > 7.5: Add acid to nutrient tank")
            if "pH" in message:
                title = "⚠️ pH Alert"
                notification_data = {
                    "alert_id": alert_id,
                    "device_id": device_id,
                    "type": alert_type,  # Use the specific alert type
                    "click_action": "OPEN_ALERTS_SCREEN"
                }
                fcm_result = send_fcm_notification(user_id, title, message, notification_data)
            elif "EC" in message:
                title = "⚠️ EC/TDS Alert"
                notification_data = {
                    "alert_id": alert_id,
                    "device_id": device_id,
                    "type": alert_type,  # Use the specific alert type
                    "click_action": "OPEN_ALERTS_SCREEN"
                }
                fcm_result = send_fcm_notification(user_id, title, message, notification_data)
        except Exception as e:
            pass
        
        # Notify WebSocket clients about the new alert
        notify_alert_update(user_id, alert_id, message, alert_type)
        
        return alert_id, alert_data

def send_fcm_via_http(token, title, body, data=None):
    """
    Fallback method to send FCM via HTTP v1 API directly
    
    Args:
        token: FCM token
        title: Notification title
        body: Notification body text
        data: Optional data payload
    
    Returns:
        Success status and message
    """
    try:
        # Get the service account credentials from environment variables
        firebase_config = getattr(settings, 'FIREBASE_CONFIG', {})
        if not firebase_config:
            return False, "Firebase configuration not found in environment variables"
        
        # Get project ID from configuration
        project_id = firebase_config.get('project_id')
        if not project_id:
            return False, "Project ID not found in configuration"
        
        # Get access token for authentication
        auth_url = "https://oauth2.googleapis.com/token"
        auth_data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": _create_jwt(firebase_config)
        }
        auth_headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        auth_response = requests.post(auth_url, data=auth_data, headers=auth_headers)
        if auth_response.status_code != 200:
            return False, f"Failed to get access token: {auth_response.text}"
        
        access_token = auth_response.json().get('access_token')
        
        # Prepare FCM message
        fcm_url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        fcm_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Ensure data values are strings
        string_data = {}
        if data:
            for key, value in data.items():
                string_data[key] = str(value)
        
        fcm_payload = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body
                },
                "data": string_data,
                "android": {
                    "priority": "high",
                    "notification": {
                        "sound": "default"
                    }
                },
                "apns": {
                    "payload": {
                        "aps": {
                            "sound": "default",
                            "badge": 1,
                            "content-available": 1
                        }
                    }
                }
            }
        }
        
        # Send FCM message
        fcm_response = requests.post(fcm_url, json=fcm_payload, headers=fcm_headers)
        if fcm_response.status_code == 200:
            return True, fcm_response.json()
        else:
            return False, f"FCM HTTP API error: {fcm_response.text}"
    
    except Exception as e:
        return False, f"Error in FCM HTTP API: {str(e)}"

def _create_jwt(service_account):
    """Create a JWT for Google API authentication"""
    import time
    import jwt  # pip install PyJWT
    
    # Get required fields from service account
    private_key = service_account.get('private_key')
    client_email = service_account.get('client_email')
    
    if not private_key or not client_email:
        raise ValueError("Missing required fields in service account")
    
    # Create JWT claims
    now = int(time.time())
    payload = {
        "iss": client_email,
        "scope": "https://www.googleapis.com/auth/firebase.messaging",
        "aud": "https://oauth2.googleapis.com/token",
        "exp": now + 3600,
        "iat": now
    }
    
    # Sign JWT
    return jwt.encode(payload, private_key, algorithm="RS256")

class ActuatorDataView(APIView):
    def post(self, request):
        data = request.data
        device_id = data.get('device_id')
        pump_status = data.get('pump_status')
        light_status = data.get('light_status')

        if not device_id:
            return Response({"error": "Device ID is required"}, status=400)

        # Create a reference to actuators under the device
        actuator_ref = db.reference(f'devices/{device_id}/actuators')

        # Save actuator data with a timestamp
        actuator_ref.push({
            'pump_status': pump_status,
            'light_status': light_status,
            'timestamp': datetime.now().isoformat()
        })

        return Response({"message": "Actuator data updated successfully"}, status=200)

class HistoricalSensorDataView(APIView):
    def get(self, request, device_id):
        """
        Retrieve historical sensor data for a specific device with filtering
        
        URL Parameters:
        - start_date: ISO format datetime string (e.g., 2024-01-01T00:00:00.000)
        - end_date: ISO format datetime string
        - sensor_type: Type of sensor data to retrieve (temperature, humidity, ph, ec, tds, all)
        
        Returns:
        - Dictionary of sensor data points structured by sensor type
        """
        try:
            # Get query parameters
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            sensor_type = request.query_params.get('sensor_type', 'all').lower()
            
            # Validate required parameters
            if not start_date_str or not end_date_str:
                return Response(
                    {"error": "Both start_date and end_date are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Parse date strings
            try:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS.sss)"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get device data
            device_ref = db.reference(f'devices/{device_id}')
            device_data = device_ref.get()
            
            if not device_data:
                return Response(
                    {"error": f"Device with ID {device_id} not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if device has sensors data
            device_sensors = device_data.get('sensors')
            if not device_sensors:
                return Response(
                    {"error": "No sensor data available for this device"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Filter sensor readings by date range and organize by sensor type
            filtered_data = {}
            result = {"sensor_data": {}}
            
            # Initialize data structure for each requested sensor type
            if sensor_type == 'all':
                sensor_types = ['temperature', 'humidity', 'ph', 'ec', 'tds', 'waterLevel']
            else:
                sensor_types = [sensor_type]
                
            # Two possible structures:
            # 1. Sensors as a dict directly in device data with timestamp (simpler format)
            # 2. Sensors as a collection of readings with timestamps (more complex, historical format)
            
            # Case 1: Sensors stored directly in device data
            if isinstance(device_sensors, dict) and not any(isinstance(v, dict) for v in device_sensors.values()):
                # Check if there's a timestamp in the sensors dict
                sensor_timestamp = device_sensors.get('timestamp')
                if sensor_timestamp:
                    try:
                        reading_time = datetime.fromisoformat(sensor_timestamp.replace('Z', '+00:00'))
                        # Only include if within date range
                        if start_date <= reading_time <= end_date:
                            timestamp_key = reading_time.isoformat()
                            filtered_data[timestamp_key] = {'timestamp': timestamp_key}
                            
                            # Add each requested sensor type if present
                            for s_type in sensor_types:
                                if s_type in device_sensors:
                                    filtered_data[timestamp_key][s_type] = device_sensors[s_type]
                    except (ValueError, TypeError):
                        # If timestamp parsing fails, add current data anyway with current timestamp
                        timestamp_key = datetime.now().isoformat()
                        filtered_data[timestamp_key] = {'timestamp': timestamp_key}
                        
                        for s_type in sensor_types:
                            if s_type in device_sensors:
                                filtered_data[timestamp_key][s_type] = device_sensors[s_type]
                else:
                    # No timestamp, use current time
                    timestamp_key = datetime.now().isoformat()
                    filtered_data[timestamp_key] = {'timestamp': timestamp_key}
                    
                    for s_type in sensor_types:
                        if s_type in device_sensors:
                            filtered_data[timestamp_key][s_type] = device_sensors[s_type]
            
            # Case 2: Try getting data from sensor readings collection
            else:
                # Get the sensors reference to look for historical readings
                sensors_ref = db.reference(f'devices/{device_id}/sensors')
                all_sensor_data = sensors_ref.get() or {}
                
                # Check if it's a dictionary of readings
                if isinstance(all_sensor_data, dict):
                    for reading_id, reading in all_sensor_data.items():
                        # Skip entries that aren't dictionaries
                        if not isinstance(reading, dict):
                            continue
                            
                        # Skip entries without timestamp
                        if 'timestamp' not in reading:
                            continue
                        
                        # Parse reading timestamp
                        try:
                            reading_time = datetime.fromisoformat(reading['timestamp'].replace('Z', '+00:00'))
                        except (ValueError, TypeError):
                            continue
                        
                        # Check if reading is within date range
                        if start_date <= reading_time <= end_date:
                            # Add to filtered data with timestamp as key for sorting
                            timestamp_key = reading_time.isoformat()
                            if timestamp_key not in filtered_data:
                                filtered_data[timestamp_key] = {}
                            
                            # Add each requested sensor value if present
                            for s_type in sensor_types:
                                if s_type in reading:
                                    filtered_data[timestamp_key][s_type] = reading[s_type]
                            
                            # Always include timestamp
                            filtered_data[timestamp_key]['timestamp'] = timestamp_key
            
            # If no data found, generate mock data for testing
            if not filtered_data and os.environ.get('GENERATE_MOCK_DATA', 'False').lower() == 'true':
                # Generate mock data with timestamps within the range
                days_range = (end_date - start_date).days + 1
                for i in range(days_range):
                    # Create a timestamp for each day
                    mock_date = start_date + timedelta(days=i)
                    timestamp_key = mock_date.isoformat()
                    
                    # Create mock data for each sensor type
                    filtered_data[timestamp_key] = {'timestamp': timestamp_key}
                    for s_type in sensor_types:
                        if s_type == 'temperature':
                            filtered_data[timestamp_key][s_type] = round(20 + (random.random() * 10), 1)  # 20-30°C
                        elif s_type == 'humidity':
                            filtered_data[timestamp_key][s_type] = round(40 + (random.random() * 40), 1)  # 40-80%
                        elif s_type == 'ph':
                            filtered_data[timestamp_key][s_type] = round(5.5 + (random.random() * 2), 1)  # 5.5-7.5
                        elif s_type == 'ec':
                            filtered_data[timestamp_key][s_type] = round(1 + (random.random() * 2), 2)  # 1-3 mS/cm
                        elif s_type == 'tds':
                            filtered_data[timestamp_key][s_type] = int(500 + (random.random() * 1000))  # 500-1500 ppm
                        elif s_type == 'waterLevel':
                            filtered_data[timestamp_key][s_type] = round(50 + (random.random() * 50), 1)  # 50-100%
            
            # Convert filtered data to the desired response format
            result["sensor_data"] = filtered_data
            
            # Return the filtered sensor data
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error retrieving historical sensor data: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve sensor data: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
