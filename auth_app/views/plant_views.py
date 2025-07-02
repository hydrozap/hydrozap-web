from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import db
from datetime import datetime, timedelta
import logging
from .device_views import notify_device_update
from .alert_views import notify_alert_update
import uuid
from .notification_utils import send_fcm_notification

logger = logging.getLogger(__name__)

class PlantProfileView(APIView):
    def get(self, request, identifier=None):
        """Retrieve plant profiles based on user_id and identifier"""
        user_id = request.query_params.get('user_id')
        
        if identifier:
            # Get a specific plant profile by identifier
            plant_profiles_ref = db.reference(f'plant_profiles/{identifier}')
            plant_profile = plant_profiles_ref.get()

            if not plant_profile:
                return Response({"error": "Plant profile not found"}, status=status.HTTP_404_NOT_FOUND)

            # Check if user has access to this profile
            profile_user_id = plant_profile.get('user_id')
            if profile_user_id and profile_user_id != user_id:
                return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

            return Response({"plant_profile": plant_profile}, status=status.HTTP_200_OK)
            
            # Get all plant profiles
        plant_profiles_ref = db.reference('plant_profiles')
        plant_profiles = plant_profiles_ref.get()

        if not plant_profiles:
            return Response({"error": "No plant profiles found"}, status=status.HTTP_404_NOT_FOUND)

        # Filter profiles based on user_id
        filtered_profiles = {}
        for profile_id, profile in plant_profiles.items():
            profile_user_id = profile.get('user_id')
            
            # Include profile if:
            # 1. It belongs to the requesting user, OR
            # 2. It's a public profile (no user_id)
            if (profile_user_id == user_id) or (profile_user_id is None):
                filtered_profiles[profile_id] = profile

        return Response({"plant_profiles": filtered_profiles}, status=status.HTTP_200_OK)

    def post(self, request):
        """Add a new plant profile"""
        data = request.data
        identifier = data.get('identifier')
        user_id = data.get('user_id')

        if not identifier:
            return Response({"error": "Identifier is required"}, status=400)
            
        if not user_id:
            return Response({"error": "User ID is required"}, status=400)

        # Check if the profile already exists
        plant_profiles_ref = db.reference(f'plant_profiles/{identifier}')
        if plant_profiles_ref.get():
            return Response({"error": "Plant profile with this identifier already exists"}, status=400)

        # Save plant profile data with user_id
        data['mode'] = data.get('mode', 'simple')  # Add mode field with default "simple"
        plant_profiles_ref.set(data)

        return Response({"message": "Plant profile added successfully"}, status=status.HTTP_201_CREATED)

    def delete(self, request, identifier):
        """Delete a plant profile by identifier"""
        plant_profiles_ref = db.reference(f'plant_profiles/{identifier}')
        if not plant_profiles_ref.get():
            return Response({"error": "Plant profile not found"}, status=status.HTTP_404_NOT_FOUND)

        plant_profiles_ref.delete()
        return Response({"message": "Plant profile deleted successfully"}, status=status.HTTP_200_OK)

    def patch(self, request, identifier):
        """Partially update a plant profile by identifier"""
        plant_profiles_ref = db.reference(f'plant_profiles/{identifier}')
        existing_profile = plant_profiles_ref.get()
        
        if not existing_profile:
            return Response({"error": "Plant profile not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if user has access to this profile
        user_id = request.query_params.get('user_id')
        profile_user_id = existing_profile.get('user_id')
        if profile_user_id and profile_user_id != user_id:
            return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

        # Prepare update data
        updated_data = {}
        
        # Update fields if provided in request
        for field in ['name', 'description', 'optimal_conditions', 'mode', 'user_id']:
            if field in request.data:
                updated_data[field] = request.data[field]

        # Add timestamp for when profile was updated
        updated_data['updated_at'] = datetime.now().isoformat()

        # Update the profile
        plant_profiles_ref.update(updated_data)

        # Get the updated profile
        updated_profile = plant_profiles_ref.get()

        return Response({
            "message": "Plant profile updated successfully",
            "plant_profile": updated_profile
        }, status=status.HTTP_200_OK)

class GrowProfileView(APIView):
    def get(self, request, *args, **kwargs):
        user_id = request.GET.get('user_id')
        ref = db.reference('grow_profiles')
        grow_profiles = ref.get()

        if not grow_profiles:
            return Response({"grow_profiles": []})

        filtered_profiles = {
            profile_id: profile
            for profile_id, profile in grow_profiles.items()
            if profile.get('user_id') == user_id
        }

        return Response({"grow_profiles": filtered_profiles})

    def post(self, request):
        required_fields = ["user_id", "name", "plant_profile_id"]
        missing_fields = [field for field in required_fields if field not in request.data]

        if missing_fields:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = request.data["user_id"]
        name = request.data["name"]
        plant_profile_id = request.data["plant_profile_id"]

        grow_profile_data = {
            "user_id": user_id,
                "name": name,
            "plant_profile_id": plant_profile_id,
            "grow_duration_days": request.data.get("grow_duration_days", 60),
            "is_active": request.data.get("is_active", False),
            "mode": request.data.get("mode", "simple"),  # Add mode field with default "simple"
            "optimal_conditions": request.data.get("optimal_conditions", {
                "transplanting": {},
                "vegetative": {},
                "maturation": {}
            }),
                "created_at": datetime.now().isoformat()
            }
            
        profile_ref = db.reference("grow_profiles")
        profile_id = profile_ref.push().key
        profile_ref.child(profile_id).set(grow_profile_data)
            
        return Response({
            "message": "Grow profile created successfully",
            "profile_id": profile_id,
            "grow_profile": grow_profile_data,
        }, status=status.HTTP_201_CREATED)

    def put(self, request, profile_id):
        profile_ref = db.reference(f"grow_profiles/{profile_id}")
        existing_profile = profile_ref.get()

        if not existing_profile:
            return Response({"error": "Grow profile not found"}, status=status.HTTP_404_NOT_FOUND)

        updated_data = {}

        if "name" in request.data:
            updated_data["name"] = request.data["name"]
        if "plant_profile_id" in request.data:
            updated_data["plant_profile_id"] = request.data["plant_profile_id"]
        if "grow_duration_days" in request.data:
            updated_data["grow_duration_days"] = request.data["grow_duration_days"]

        # Handle optimal conditions per stage
        if "optimal_conditions" in request.data:
            new_conditions = request.data["optimal_conditions"]
            existing_conditions = existing_profile.get("optimal_conditions", {})

            for stage in ["transplanting", "vegetative", "maturation"]:
                if stage in new_conditions:
                    if stage not in existing_conditions:
                        existing_conditions[stage] = {}
                    for param in ["temperature_range", "humidity_range", "ec_range", "ph_range", "tds_range"]:
                        if param in new_conditions[stage]:
                            existing_conditions[stage][param] = new_conditions[stage][param]

            updated_data["optimal_conditions"] = existing_conditions

        updated_data["updated_at"] = datetime.now().isoformat()
        profile_ref.update(updated_data)

        updated_profile = profile_ref.get()

        return Response({
            "message": "Grow profile updated successfully",
            "profile_id": profile_id,
            "grow_profile": updated_profile,
        }, status=status.HTTP_200_OK)

    def delete(self, request, profile_id):
        profile_ref = db.reference(f"grow_profiles/{profile_id}")
        existing_profile = profile_ref.get()

        if not existing_profile:
            return Response({"error": "Grow profile not found"}, status=status.HTTP_404_NOT_FOUND)

        if existing_profile.get("is_active", False):
            return Response(
                {"error": "Cannot delete an active grow profile"},
                status=status.HTTP_400_BAD_REQUEST,
            )
                
        profile_ref.delete()
        return Response({"message": "Grow profile deleted successfully"}, status=status.HTTP_200_OK)
    def patch(self, request, profile_id):
        profile_ref = db.reference(f"grow_profiles/{profile_id}")
        existing_profile = profile_ref.get()

        if not existing_profile:
            return Response({"error": "Grow profile not found"}, status=status.HTTP_404_NOT_FOUND)

        updated_data = {}

        # Update basic fields if provided
        for field in ["name", "plant_profile_id", "grow_duration_days", "is_active"]:
            if field in request.data:
                updated_data[field] = request.data[field]

        # Merge optimal_conditions
        if "optimal_conditions" in request.data:
            new_conditions = request.data["optimal_conditions"]
            existing_conditions = existing_profile.get("optimal_conditions", {})

            for stage, stage_data in new_conditions.items():
                if stage not in existing_conditions:
                    existing_conditions[stage] = {}
                for param, value in stage_data.items():
                    existing_conditions[stage][param] = value

            updated_data["optimal_conditions"] = existing_conditions

        updated_data["updated_at"] = datetime.now().isoformat()
        profile_ref.update(updated_data)

        updated_profile = profile_ref.get()

        return Response({
            "message": "Grow profile partially updated successfully",
            "profile_id": profile_id,
            "grow_profile": updated_profile,
        }, status=status.HTTP_200_OK)

class GrowView(APIView):
    def post(self, request):
        """Add a new grow record"""
        data = request.data
        grow_id = data.get('grow_id')

        if not grow_id:
            return Response({"error": "Grow ID is required"}, status=400)

        device_id = data.get("device_id")
        if not device_id:
            return Response({"error": "Device ID is required"}, status=400)

        # Check if device is already assigned to an active grow
        grows_ref = db.reference('grows')
        existing_grows = grows_ref.get() or {}
        
        # Check if the device is already assigned to any active grow
        for existing_grow_id, grow_data in existing_grows.items():
            if grow_data.get('device_id') == device_id and grow_data.get('status') == 'active':
                return Response({
                    "error": "Device is already assigned to an active grow",
                    "device_id": device_id,
                    "grow_id": existing_grow_id
                }, status=status.HTTP_409_CONFLICT)  # 409 Conflict is appropriate here

        # Simplify grow data with necessary fields only
            grow_data = {
            "user_id": data.get("user_id"),
            "grow_name": data.get("grow_name"),
                "device_id": device_id,
            "profile_id": data.get("profile_id"),  # Link to grow profile
            "start_date": data.get("start_date", None),  # Optional if you want
            "status": "active"  # Explicitly set status to active
        }

        # Update device status to in_use
        device_ref = db.reference(f'devices/{device_id}')
        device_data = device_ref.get()
        
        if device_data:
            device_ref.update({
                "status": "in_use",
                "last_updated": datetime.now().isoformat()
            })
            
            # Notify WebSocket clients about device update
            user_id = device_data.get('user_id')
            if user_id:
                notify_device_update(user_id)

        # Save the grow record to Firebase
        grow_ref = db.reference(f'grows/{grow_id}')
        grow_ref.set(grow_data)
            
        return Response({"message": "Grow record added successfully"}, status=status.HTTP_201_CREATED)

    def get(self, request, grow_id=None):
        """Retrieve a single grow record or list all grows"""
        if grow_id:
            # Get a specific grow record
            grow_ref = db.reference(f'grows/{grow_id}')
            grow_data = grow_ref.get()

            if not grow_data:
                return Response({"error": "Grow record not found"}, status=404)
            grow_count = len(grow_data)

            return Response(grow_data, grow_count, status=status.HTTP_200_OK)
        else:
            # Get all grow records
            grows_ref = db.reference('grows')
            grows_data = grows_ref.get()
            
            if not grows_data:
                return Response({"message": "No grow records found"}, status=200)
            
            return Response(grows_data, status=status.HTTP_200_OK)

    def put(self, request, grow_id):
        """Update an existing grow record"""
        if not grow_id:
            return Response({"error": "Grow ID is required for update"}, status=400)

        data = request.data
        grow_ref = db.reference(f'grows/{grow_id}')
        existing_data = grow_ref.get()

        if not existing_data:
            return Response({"error": "Grow record not found"}, status=404)

        # Check if trying to update device_id
        new_device_id = data.get("device_id")
        if new_device_id and new_device_id != existing_data.get("device_id"):
            # Check if device is already assigned to another grow
            grows_ref = db.reference('grows')
            all_grows = grows_ref.get() or {}
            
            for existing_grow_id, grow_data in all_grows.items():
                # Skip the current grow being updated
                if existing_grow_id == grow_id:
                    continue
                    
                if grow_data.get('device_id') == new_device_id:
                    return Response({
                        "error": "Device is already assigned to an active grow",
                        "device_id": new_device_id,
                        "grow_id": existing_grow_id
                    }, status=status.HTTP_409_CONFLICT)

        # Update grow data with relevant fields
        updated_data = {
            "user_id": data.get("user_id", existing_data.get("user_id")),
            "grow_name": data.get("grow_name", existing_data.get("grow_name")),
            "device_id": new_device_id or existing_data.get("device_id"),
            "profile_id": data.get("profile_id", existing_data.get("profile_id")),
            "start_date": data.get("start_date", existing_data.get("start_date")),
            "status": data.get("status", existing_data.get("status", "active")),
            "harvest_date": data.get("harvest_date", existing_data.get("harvest_date")),
        }

        # Check if grow is being marked as harvested
        new_status = data.get("status")
        if new_status == "harvested" and existing_data.get("status") != "harvested":
            # Get device ID from the grow data
            device_id = new_device_id or existing_data.get("device_id")
            if device_id:
                # Update device status to available and clear grow-related data
                device_ref = db.reference(f'devices/{device_id}')
                device_data = device_ref.get()
                
                if device_data:
                    device_ref.update({
                        "status": "available",
                        "active_grow_id": None,  # Clear the active grow ID
                        "thresholds": None,      # Clear the thresholds
                        "last_updated": datetime.now().isoformat()
                    })

        # Update the record in Firebase
        grow_ref.update(updated_data)

        # After updating, notify WebSocket clients
        user_id = data.get('user_id')
        if user_id:
            notify_device_update(user_id)

        return Response({"message": "Grow record updated successfully"}, status=status.HTTP_200_OK)

    def delete(self, request, grow_id):
        """Delete a grow record"""
        if not grow_id:
            return Response({"error": "Grow ID is required for deletion"}, status=400)

        grow_ref = db.reference(f'grows/{grow_id}')
        existing_data = grow_ref.get()

        if not existing_data:
            return Response({"error": "Grow record not found"}, status=404)

        # Check if grow has been harvested
        # We'll look for either a specific status field or check if harvest_date exists
        grow_status = existing_data.get('status', 'active')  # Default to 'active' if not specified
        harvest_date = existing_data.get('harvest_date')
        
        # If grow is still active (not harvested), prevent deletion
        if grow_status == 'active' and not harvest_date:
            return Response({
                "error": "Cannot delete an active grow",
                "message": "This grow is still active. Please harvest it first before deletion.",
                "grow_id": grow_id
            }, status=status.HTTP_409_CONFLICT)

        # Get user_id before deleting the record
        user_id = existing_data.get('user_id')

        # Grow is harvested or has a harvest date, safe to delete
        grow_ref.delete()

        # After deleting, notify WebSocket clients
        if user_id:
            notify_device_update(user_id)

        return Response({"message": "Grow record deleted successfully"}, status=status.HTTP_200_OK)

class HarvestLogView(APIView):
    def post(self, request, device_id, grow_id=None):
        try:
            data = request.data
            
            # Handle both camelCase and snake_case formats
            grow_id = data.get('growId') or data.get('grow_id') or grow_id
            crop_name = data.get('cropName') or data.get('crop_name')
            harvest_date = data.get('harvestDate') or data.get('harvest_date')
            yield_amount = data.get('yieldAmount') or data.get('yield_amount')
            rating = data.get('rating')
            performance_metrics = data.get('performanceMetrics') or data.get('performance_metrics', {})

            # Check required fields and print what's missing for debugging
            required_fields = {'crop_name': crop_name, 'harvest_date': harvest_date, 
                              'yield_amount': yield_amount, 'rating': rating}
            missing = [k for k, v in required_fields.items() if not v]
            
            if missing:
                return Response({"error": f"Missing required fields: {', '.join(missing)}"}, status=400)

            log_id = str(uuid.uuid4())

            log_data = {
                "device_id": device_id,
                "grow_id": grow_id,
                "crop_name": crop_name,
                "harvest_date": harvest_date,
                "yield_amount": float(yield_amount) if yield_amount else 0,
                "rating": int(rating) if rating else 0,
                "performance_metrics": performance_metrics
            }

            db.reference(f"harvest_logs/{log_id}").set(log_data)

            # Mark the grow as harvested if grow_id is provided
            if grow_id:
                grow_ref = db.reference(f'grows/{grow_id}')
                grow_data = grow_ref.get()
                
                if grow_data:
                    # Get the profile ID from the grow data
                    profile_id = grow_data.get('profile_id')
                    
                    # Update the grow with harvested status and harvest date
                    grow_ref.update({
                        "status": "harvested",
                        "harvest_date": harvest_date,
                    })
                    
                    # Update the grow profile status if profile_id exists
                    if profile_id:
                        # Check if any other active grows are using this profile
                        grows_ref = db.reference('grows')
                        all_grows = grows_ref.get() or {}
                        
                        # Count active grows using this profile
                        active_grows_count = sum(
                            1 for g in all_grows.values()
                            if g.get('profile_id') == profile_id 
                            and g.get('status') == 'active'
                            and g.get('grow_id') != grow_id  # Exclude current grow
                        )
                        
                        # Update profile status based on active grows count
                        profile_ref = db.reference(f'grow_profiles/{profile_id}')
                        profile_ref.update({
                            "is_active": active_grows_count > 0
                        })
                    
                    # Update device status to available
                    device_ref = db.reference(f'devices/{device_id}')
                    device_data = device_ref.get()
                    
                    if device_data:
                        # Update device status to available and clear grow-related data
                        device_ref.update({
                            "status": "available",
                            "active_grow_id": None,  # Clear the active grow ID
                            "thresholds": None,      # Clear the thresholds
                            "last_updated": datetime.now().isoformat()
                        })
                        
                        # Notify WebSocket clients about device update
                        user_id = device_data.get('user_id')
                        if user_id:
                            notify_device_update(user_id)

            # Format the response to match the expected client model
            response_data = {
                "logId": log_id,
                "deviceId": device_id,
                "growId": grow_id,
                "cropName": crop_name,
                "harvestDate": harvest_date,
                "yieldAmount": float(yield_amount) if yield_amount else 0,
                "rating": int(rating) if rating else 0,
                "performanceMetrics": performance_metrics
            }

            return Response({"message": "Harvest log created", "log_id": log_id, "log": response_data}, status=201)
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def get(self, request, device_id, grow_id=None):
        try:
            ref = db.reference("harvest_logs")
            logs = ref.get()
            
            if not logs:
                return Response({"logs": []}, status=200)

            # Filter logs by device_id and optionally grow_id
            filtered_logs = []
            for log_id, log_data in logs.items():
                if log_data.get("device_id") == device_id:
                    if grow_id is None or log_data.get("grow_id") == grow_id:
                        # Rename fields for client-side compatibility
                        formatted_log = {
                            "logId": log_id,
                            "deviceId": log_data.get("device_id"),
                            "growId": log_data.get("grow_id", ""),
                            "cropName": log_data.get("crop_name", ""),
                            "harvestDate": log_data.get("harvest_date", ""),
                            "yieldAmount": log_data.get("yield_amount", 0),
                            "rating": log_data.get("rating", 0),
                            "performanceMetrics": log_data.get("performance_metrics", {})
                        }
                        filtered_logs.append(formatted_log)

            return Response({"logs": filtered_logs}, status=200)
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class HarvestReadinessView(APIView):
    def get(self, request, grow_id):
        """Verify if a grow is ready for harvest"""
        try:
            # Get grow data
            grow_ref = db.reference(f'grows/{grow_id}')
            grow_data = grow_ref.get()
            
            if not grow_data:
                return Response({"error": "Grow not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # Check if already harvested
            if grow_data.get('status') == 'harvested':
                return Response({
                    "ready": False,
                    "message": "This grow has already been harvested",
                    "harvest_date": grow_data.get('harvest_date')
                }, status=status.HTTP_200_OK)
            
            # Get grow profile for duration
            profile_id = grow_data.get('profile_id')
            profile_ref = db.reference(f'grow_profiles/{profile_id}')
            profile_data = profile_ref.get()
            
            if not profile_data:
                return Response({"error": "Grow profile not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # Calculate progress
            start_date = datetime.fromisoformat(grow_data.get('start_date').replace('Z', '+00:00'))
            current_date = datetime.now()
            days_since_start = (current_date - start_date).days
            
            # Get grow duration from profile
            grow_duration = profile_data.get('grow_duration_days', 60)  # Default to 60 days
            
            # Calculate progress percentage
            progress = min(100, (days_since_start / grow_duration) * 100)
            
            # Determine if ready for harvest
            ready_for_harvest = progress >= 100
            
            # If ready for harvest, send notification
            if ready_for_harvest:
                user_id = grow_data.get('user_id')
                grow_name = grow_data.get('grow_name', 'Your grow')
                device_id = grow_data.get('device_id')
                
                # Send FCM notification
                notification_sent = send_fcm_notification(
                    user_id=user_id,
                    title="Harvest Ready! 🌱",
                    body=f"{grow_name} is ready for harvest!",
                    data={
                        'type': 'harvest',
                        'grow_id': grow_id,
                        'device_id': device_id,
                        'alert_type': 'harvest_reminder',
                        'priority': 'high'
                    }
                )
                
                # Log notification status
                if notification_sent:
                    logger.info(f"Harvest ready notification sent to user {user_id} for grow {grow_id}")
                else:
                    logger.warning(f"Failed to send harvest ready notification to user {user_id} for grow {grow_id}")
            
            return Response({
                "ready": ready_for_harvest,
                "progress": progress,
                "days_since_start": days_since_start,
                "total_duration": grow_duration,
                "message": "Grow is ready for harvest" if ready_for_harvest else "Grow is not yet ready for harvest"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in harvest readiness check: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GrowCountView(APIView):
    def get(self, request, user_id):  # Accept user_id from path
        """Get the count of grows for a user (only active grows)"""
        try:
            grows_ref = db.reference('grows')
            grows = grows_ref.get()

            if grows:
                filtered_grows = {
                    grow_id: grow_data 
                    for grow_id, grow_data in grows.items()
                    if grow_data.get('user_id') == user_id and grow_data.get('status') == 'active'
                }
                grow_count = len(filtered_grows)
            else:
                grow_count = 0

            return Response({"grow_count": grow_count}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)