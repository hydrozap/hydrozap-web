from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import db
from datetime import datetime, timedelta
import logging
from .plant_views import GrowCountView
from .device_views import DeviceCountView
from .alert_views import AlertCountView

logger = logging.getLogger(__name__)

class DashboardCountsView(APIView):
    def get(self, request):
        """Get all dashboard counts for a user in a single API call"""
        user_id = request.GET.get('user_id')
        
        if not user_id:
            return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get device count
            devices_ref = db.reference('devices')
            devices = devices_ref.order_by_child('user_id').equal_to(user_id).get()
            device_count = len(devices) if devices else 0
            
            # Get alert count
            alerts_ref = db.reference(f'alerts/{user_id}')
            alerts = alerts_ref.get()
            alert_count = len(alerts) if alerts else 0
            
            # Get grow count (only active grows)
            grows_ref = db.reference('grows')
            grows = grows_ref.get()  # Get all grows
            
            if grows:
                # Filter grows by user_id and status 'active'
                filtered_grows = {
                    grow_id: grow_data 
                    for grow_id, grow_data in grows.items() 
                    if grow_data.get('user_id') == user_id and grow_data.get('status') == 'active'
                }
                grow_count = len(filtered_grows)
            else:
                grow_count = 0
            
            return Response({
                "device_count": device_count,
                "alert_count": alert_count,
                "grow_count": grow_count
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
