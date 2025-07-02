from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RegisteredDeviceView(APIView):
    """
    View for managing registered devices in the system.
    Handles validation and management of pre-registered device IDs.
    """
    def get(self, request, device_id=None):
        """Get all registered devices or a specific device by ID"""
        if device_id:
            device_ref = db.reference(f'registered_devices/{device_id}')
            device = device_ref.get()
            if not device:
                return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"device": device}, status=status.HTTP_200_OK)
        
        devices_ref = db.reference('registered_devices')
        devices = devices_ref.get()
        return Response({"devices": devices}, status=status.HTTP_200_OK)

    def post(self, request):
        """Register a new device"""
        data = request.data
        device_id = data.get('device_id')
        model = data.get('model')

        if not device_id:
            return Response({"error": "Device ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not model:
            return Response({"error": "Device model is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if device already exists
        device_ref = db.reference(f'registered_devices/{device_id}')
        if device_ref.get():
            return Response({"error": "Device already registered"}, status=status.HTTP_400_BAD_REQUEST)

        # Create new device entry
        device_data = {
            "model": model,
            "registered": True,
            "status": "available",
            "created_at": datetime.now().isoformat()
        }
        
        device_ref.set(device_data)
        return Response({"message": "Device registered successfully", "device": device_data}, 
                       status=status.HTTP_201_CREATED)

    def put(self, request, device_id):
        """Update device status or details"""
        data = request.data
        device_ref = db.reference(f'registered_devices/{device_id}')
        device = device_ref.get()

        if not device:
            return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)

        # Update only allowed fields
        allowed_fields = ['status', 'model']
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not updates:
            return Response({"error": "No valid fields to update"}, status=status.HTTP_400_BAD_REQUEST)

        device_ref.update(updates)
        return Response({"message": "Device updated successfully"}, status=status.HTTP_200_OK)

    def delete(self, request, device_id):
        """Remove a device from the registered devices list"""
        device_ref = db.reference(f'registered_devices/{device_id}')
        device = device_ref.get()

        if not device:
            return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)

        device_ref.delete()
        return Response({"message": "Device removed successfully"}, status=status.HTTP_200_OK)

    @staticmethod
    def validate_device_id(device_id):
        """Static method to validate if a device ID is registered and available"""
        device_ref = db.reference(f'registered_devices/{device_id}')
        device = device_ref.get()
        
        if not device:
            return False, "Device not registered"
        
        if device.get('status') != 'available':
            return False, "Device is already in use"
            
        return True, "Device is valid"


def notify_device_update(user_id):
    """Notify WebSocket clients about device updates"""
    try:
        # Get the WebSocket reference for this user
        ws_ref = db.reference(f'websocket/{user_id}')
        
        # Update the last_updated timestamp to trigger WebSocket notification
        ws_ref.update({
            'last_updated': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error notifying device update: {e}")

class DeviceView(APIView):
    def get(self, request, device_id=None):
        """Retrieve device(s) by user_id or device_id, or check if device can be deleted"""
        # Check if this is a current_thresholds request
        if device_id and 'current_thresholds' in request.path:
            return self.get_current_thresholds(request, device_id)

        # Check if this is a delete check request
        if device_id and 'check' in request.path:
            # Check if device is assigned to any active grow
            device_ref = db.reference(f'devices/{device_id}')
            device_data = device_ref.get()
            
            if not device_data:
                return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)
                
            # Check if device is assigned to any active grow
            grows_ref = db.reference('grows')
            existing_grows = grows_ref.get() or {}
            
            # Find any grows using this device
            active_grows = []
            for grow_id, grow_data in existing_grows.items():
                if grow_data.get('device_id') == device_id:
                    active_grows.append({
                        "grow_id": grow_id,
                        "grow_name": grow_data.get("grow_name", "Unnamed Grow")
                    })
            
            # If the device is actively used in grows, return conflict
            if active_grows:
                return Response({
                    "error": "Cannot delete device that is assigned to active grows",
                    "message": "This device is currently assigned to one or more grows. Please harvest or deactivate the grows first.",
                    "active_grows": active_grows
                }, status=status.HTTP_409_CONFLICT)
            
            # Device can be deleted
            return Response({"message": "Device can be deleted"}, status=status.HTTP_200_OK)
        
        # Regular get operations below
        user_id = request.query_params.get('user_id')

        # Get all devices for a user if user_id is provided
        if user_id:
            devices_ref = db.reference('devices')
            devices = devices_ref.order_by_child('user_id').equal_to(user_id).get()

            if not devices:
                return Response({"devices": {}, "device_count": 0}, status=status.HTTP_200_OK)
            device_count = len(devices)

            return Response({"devices": devices, "device_count": device_count}, status=status.HTTP_200_OK)

        # Get a specific device by device_id if provided
        elif device_id:
            device_ref = db.reference(f'devices/{device_id}')
            device_data = device_ref.get()

            if not device_data:
                return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)

            return Response({"device_data": device_data}, status=status.HTTP_200_OK)

        # If no parameters provided, return all devices
        else:
            devices_ref = db.reference('devices')
            devices = devices_ref.get()
            
            if not devices:
                return Response({"devices": {}, "device_count": 0}, status=status.HTTP_200_OK)
                
            device_count = len(devices)
            return Response({"devices": devices, "device_count": device_count}, status=status.HTTP_200_OK)

    def post(self, request):
        """Add a new device"""
        data = request.data
        device_id = data.get('device_id')
        user_id = data.get('user_id')
        device_name = data.get('device_name', f"Device {device_id}")
        kit_type = data.get('kit', "standard")
        emergency_stop = data.get('emergency_stop', False)
        sensor_data = data.get('sensors', {})
        actuator_data = data.get('actuators', {})
        device_type = data.get('type', "Arduino")
        water_volume_liters = data.get('water_volume_liters', 0.0)

        if not device_id or not user_id:
            return Response({"error": "Device ID and User ID are required"}, status=400)

        # Validate if the device is registered and available
        is_valid, message = RegisteredDeviceView.validate_device_id(device_id)
        if not is_valid:
            return Response({"error": message}, status=400)

        # Check if device already exists in user's devices
        device_ref = db.reference(f'devices/{device_id}').get()
        if device_ref:
            return Response({"error": "Device already registered to a user"}, status=400)

        # Initialize default actuator structure if not provided
        if not actuator_data:
            actuator_data = {
                "nutrient_pump2": {
                    "status": "off",
                    "duration": 0
                },
                "phDowner_pump": {
                    "status": "off",
                    "duration": 0
                },
                "phUpper_pump": {
                    "status": "off",
                    "duration": 0
                },
                "nutrient_pump1": {
                    "status": "off",
                    "duration": 0
                },
                "flush": {
                    "active": False,
                    "type": "full",
                    "duration": 0
                }
            }

        # Prepare device data
        device_data = {
            "device_name": device_name,
            "kit": kit_type,
            "emergency_stop": emergency_stop,
            "type": device_type,
            "user_id": user_id,
            "status": "off" if emergency_stop else "on",
            "water_volume_liters": water_volume_liters,
            "auto_dose_enabled": data.get('auto_dose_enabled', False),
            "actuators": actuator_data,
            "sensors": {
                "ec": sensor_data.get("ec", 0.0),
                "tds": sensor_data.get("tds", 0.0),
                "humidity": sensor_data.get("humidity", 0),
                "ph": sensor_data.get("ph", 0.0),
                "temperature": sensor_data.get("temperature", 0.0),
                "waterLevel": sensor_data.get("waterLevel", 0.0),  
                "timestamp": datetime.now().isoformat(),
            }
        }

        # Save device data in Firebase
        db.reference(f'devices/{device_id}').set(device_data)

        # Update the registered device status to in_use
        registered_device_ref = db.reference(f'registered_devices/{device_id}')
        registered_device_ref.update({
            "status": "in_use",
            "user_id": user_id,
            "last_updated": datetime.now().isoformat()
        })

        # After creating the device, notify WebSocket clients
        if user_id:
            notify_device_update(user_id)

        return Response({"message": "Device registered successfully", "device_id": device_id}, status=201)

    def put(self, request, device_id):
        """Update device status, emergency stop, or actuator flush"""
        if not device_id:
            return Response({"error": "Device ID is required"}, status=400)

        data = request.data
        emergency_stop = data.get('emergency_stop')
        actuator_flush = data.get('actuator_flush')
        auto_dose_enabled = data.get('auto_dose_enabled')
        
        device_ref = db.reference(f'devices/{device_id}')
        device_data = device_ref.get()

        if not device_data:
            return Response({"error": "Device not found"}, status=404)

        updates = {}
        
        # Handle emergency stop update
        if emergency_stop is not None:
            updates.update({
                "emergency_stop": emergency_stop,
                "status": "off" if emergency_stop else "on"
            })
        
        # Handle auto dose enabled update
        if auto_dose_enabled is not None:
            updates["auto_dose_enabled"] = auto_dose_enabled
        
        # Handle actuator flush update
        if actuator_flush:
            actuator_id = actuator_flush.get('actuator_id')
            duration = actuator_flush.get('duration')
            flush_type = actuator_flush.get('type', 'full')
            
            if actuator_id and duration:
                actuators = device_data.get('actuators', {})
                if actuator_id in actuators:
                    actuators[actuator_id].update({
                        "status": "on",
                        "duration": duration
                    })
                    updates["actuators"] = actuators
                    
                    # If it's a flush operation, update the flush status
                    if actuator_id == "flush":
                        actuators["flush"].update({
                            "active": True,
                            "type": flush_type,
                            "duration": duration
                        })
                        updates["actuators"] = actuators
        
        if updates:
            device_ref.update(updates)

            # Notify WebSocket clients
            user_id = device_data.get('user_id')
            if user_id:
                notify_device_update(user_id)

            return Response({"message": "Device updated successfully"}, status=200)
        
        return Response({"error": "No valid updates provided"}, status=400)

    def delete(self, request, device_id):
        """Delete a device and all associated data"""
        device_ref = db.reference(f'devices/{device_id}')
        device_data = device_ref.get()
        
        if not device_data:
            return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if device is assigned to any active grow
        grows_ref = db.reference('grows')
        existing_grows = grows_ref.get() or {}
        
        # Find any grows using this device
        active_grows = []
        for grow_id, grow_data in existing_grows.items():
            if grow_data.get('device_id') == device_id:
                active_grows.append({
                    "grow_id": grow_id,
                    "grow_name": grow_data.get("grow_name", "Unnamed Grow")
                })
        
        # If the device is actively used in grows, prevent deletion
        if active_grows:
            return Response({
                "error": "Cannot delete device that is assigned to active grows",
                "message": "This device is currently assigned to one or more grows. Please harvest or deactivate the grows first.",
                "active_grows": active_grows
            }, status=status.HTTP_409_CONFLICT)

        # Get user_id before deleting the device
        user_id = device_data.get('user_id')

        # Device is not assigned to any grow, safe to delete
        device_ref.delete()

        # After deleting, notify WebSocket clients
        if user_id:
            notify_device_update(user_id)

        return Response({"message": "Device deleted successfully"}, status=status.HTTP_200_OK)

    def get_current_thresholds(self, request, device_id):
        """Get current environmental thresholds based on growth stage"""
        # Get device data
        device_ref = db.reference(f'devices/{device_id}')
        device_data = device_ref.get()

        if not device_data:
            return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get active grow for this device
        grows_ref = db.reference('grows')
        grows = grows_ref.get() or {}
        
        active_grow = None
        for grow_id, grow_data in grows.items():
            if grow_data.get('device_id') == device_id and grow_data.get('status') == 'active':
                active_grow = grow_data
                active_grow['grow_id'] = grow_id
                break

        if not active_grow:
            return Response({"error": "No active grow found for this device"}, status=status.HTTP_404_NOT_FOUND)

        # Get grow profile
        profile_id = active_grow.get('profile_id')
        if not profile_id:
            return Response({"error": "No grow profile associated with this grow"}, status=status.HTTP_404_NOT_FOUND)

        profile_ref = db.reference(f'grow_profiles/{profile_id}')
        profile_data = profile_ref.get()

        if not profile_data:
            return Response({"error": "Grow profile not found"}, status=status.HTTP_404_NOT_FOUND)

        # Calculate current stage
        start_date = datetime.fromisoformat(active_grow.get('start_date', datetime.now().isoformat()))
        current_date = datetime.now()
        days_passed = (current_date - start_date).days
        total_duration = profile_data.get('grow_duration_days', 60)

        # Determine current stage based on days passed
        if days_passed < total_duration * 0.25:  # First 25% of grow duration
            stage = "transplanting"
        elif days_passed < total_duration * 0.75:  # Next 50% of grow duration
            stage = "vegetative"
        else:
            stage = "maturation"

        # Get thresholds for current stage
        optimal_conditions = profile_data.get('optimal_conditions', {})
        stage_conditions = optimal_conditions.get(stage, {})

        # Format response
        response_data = {
            "ph_range": stage_conditions.get('ph_range', {"min": 5.8, "max": 6.5}),
            "ec_range": stage_conditions.get('ec_range', {"min": 1.2, "max": 1.7}),
            "tds_range": stage_conditions.get('tds_range', {"min": 840, "max": 1120}),
            "temperature_range": stage_conditions.get('temperature_range', {"min": 14, "max": 20}),
            "humidity_range": stage_conditions.get('humidity_range', {"min": 55, "max": 65}),
            "stage": stage,
            "days_passed": days_passed,
            "total_duration": total_duration
        }

        # Store thresholds in device data
        device_ref.update({
            "thresholds": response_data,
            "active_grow_id": active_grow['grow_id'],
            "last_updated": datetime.now().isoformat()
        })

        # Notify WebSocket clients about the update
        user_id = device_data.get('user_id')
        if user_id:
            notify_device_update(user_id)

        return Response(response_data, status=status.HTTP_200_OK)

    def patch(self, request, device_id):
        """Partially update device fields like name, water volume, etc."""
        if not device_id:
            return Response({"error": "Device ID is required"}, status=400)

        data = request.data
        device_ref = db.reference(f'devices/{device_id}')
        device_data = device_ref.get()

        if not device_data:
            return Response({"error": "Device not found"}, status=404)

        allowed_fields = ["device_name", "water_volume_liters", "emergency_stop", "auto_dose_enabled"]
        updates = {k: v for k, v in data.items() if k in allowed_fields}

        if not updates:
            return Response({"error": "No valid fields to update"}, status=400)

        # If emergency_stop is updated, also update status
        if "emergency_stop" in updates:
            current_status = device_data.get('status')
            if current_status == "in_use":
                # Don't overwrite 'in_use'
                pass
            else:
                updates["status"] = "off" if updates["emergency_stop"] else "on"

        device_ref.update(updates)

        # Notify WebSocket clients
        user_id = device_data.get('user_id')
        if user_id:
            notify_device_update(user_id)

        return Response({"message": "Device updated successfully"}, status=200)

class DeviceCountView(APIView):
    def get(self, request):
        """Get count of devices"""
        try:
            devices_ref = db.reference('devices')
            devices = devices_ref.get()
            
            # Count devices
            device_count = len(devices) if devices else 0
            
            return Response({"device_count": device_count}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST) 