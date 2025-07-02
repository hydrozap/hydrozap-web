from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from weasyprint import HTML
from firebase_admin import db
from datetime import datetime, timedelta
import uuid
import os
from urllib.request import pathname2url
from django.conf import settings
import logging
import json
from django.http import JsonResponse

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class MonitoringReportPDFView(View):
    def post(self, request, *args, **kwargs):
        import logging
        import uuid
        
        
        accept_header = request.META.get('HTTP_ACCEPT', '')
        if 'application/pdf' not in accept_header and '*/*' not in accept_header:
            return JsonResponse(
                {'error': 'Client must accept application/pdf'},
                status=406
            )

        # Parse identifiers from request (e.g., user_id, device_id)
        try:
            body = json.loads(request.body)
            user_id = body.get('user_id')
            device_id = body.get('device_id')
        except Exception:
            body = {}
            user_id = None
            device_id = None

        # Fetch user info
        user_data = {}
        if user_id:
            user_ref = db.reference(f'users/{user_id}')
            user_data = user_ref.get() or {}
        user_name = user_data.get('name', 'Current User')

        # Fetch device info
        device_data = {}
        if device_id:
            device_ref = db.reference(f'devices/{device_id}')
            device_data = device_ref.get() or {}

        # --- Fetch grow and grow profile for crop and stage info ---
        grow_data = None
        grow_profile_data = None
        crop_name = 'Not Specified'
        grow_start_date = None

        # 1. Find the active grow for this device
        grows_ref = db.reference('grows')
        grows = grows_ref.get() or {}
        for grow_id, grow in grows.items():
            if grow.get('device_id') == device_id and str(grow.get('status', '')).lower() == 'active':
                grow_data = grow
                break

        # --- Determine current stage ---
        current_stage = (grow_data.get('stage') if grow_data and grow_data.get('stage') else 'vegetative')

        # --- Get grow profile and optimal conditions for the current stage ---
        target_ph_range = '-'
        target_ec_range = '-'
        target_temp_range = '-'
        if grow_data:
            profile_id = grow_data.get('profile_id')
            grow_start_date = grow_data.get('start_date')
            if profile_id:
                grow_profile_ref = db.reference(f'grow_profiles/{profile_id}')
                grow_profile_data = grow_profile_ref.get() or {}
                crop_name = grow_profile_data.get('name', 'Not Specified')
                optimal = grow_profile_data.get('optimal_conditions', {})
                # Try both lower and original case for stage key
                stage_opt = optimal.get(str(current_stage).lower(), {}) or optimal.get(str(current_stage), {})
                def format_range(val):
                    if isinstance(val, dict) and 'min' in val and 'max' in val:
                        return f"{val['min']} - {val['max']}"
                    return '-'
                # Try both ph_range and pH_range, ec_range and EC_range, etc.
                target_ph_range = format_range(stage_opt.get('ph_range')) if stage_opt.get('ph_range') else format_range(stage_opt.get('pH_range'))
                target_ec_range = format_range(stage_opt.get('ec_range')) if stage_opt.get('ec_range') else format_range(stage_opt.get('EC_range'))
                target_temp_range = format_range(stage_opt.get('temperature_range'))

        # Fallbacks
        if not crop_name or crop_name == 'Not Specified':
            crop_name = device_data.get('plantProfile') or device_data.get('plant_profile', 'Not Specified')
        if not grow_start_date:
            grow_start_date = datetime.now().isoformat()

        # Calculate duration
        try:
            start_date = datetime.fromisoformat(grow_start_date)
        except Exception:
            start_date = datetime.now()
        duration = datetime.now() - start_date
        duration_string = f"{duration.days} days, {duration.seconds // 3600} hours"

        # --- Prepare stage info for the PDF ---
        stage_info = {
            'Crop_Name': crop_name,
            'Current_Stage': current_stage,
            'Start_Date': start_date.strftime('%Y-%m-%d %H:%M:%S'),
            'Duration': duration_string,
            'Target_pH_Range': target_ph_range,
            'Target_EC_Range': target_ec_range,
            'Target_Temperature_Range': target_temp_range,
        }

        # --- Prepare parameters from latest sensor readings ---
        parameters = []
        sensors = device_data.get('sensors', {})

        # If sensors is a dict of readings (from .push()), get the latest one
        if isinstance(sensors, dict) and any(isinstance(v, dict) for v in sensors.values()):
            latest = None
            for reading in sensors.values():
                if isinstance(reading, dict) and 'timestamp' in reading:
                    if not latest or reading['timestamp'] > latest['timestamp']:
                        latest = reading
            sensors = latest or {}

        if sensors:
            parameters = [
                ["Temperature", str(sensors.get('temperature', '0.0')), "°C"],
                ["pH Level", str(sensors.get('ph', '0.0')), "pH"],
                ["EC Level", str(sensors.get('ec', '0.0')), "mS/cm"],
                ["TDS Level", str(sensors.get('tds', '0.0')), "ppm"],
            ]

        # --- Fetch historical sensor readings ---
        historical_readings = []
        try:
            # Get all sensor readings from the device
            all_sensors = device_data.get('sensors', {})
            
            if isinstance(all_sensors, dict):
                # Convert sensor readings to list format for sorting
                readings_list = []
                for reading_id, reading_data in all_sensors.items():
                    if isinstance(reading_data, dict) and 'timestamp' in reading_data:
                        readings_list.append(reading_data)
                
                # Sort by timestamp (newest first) and take the last 20 readings
                readings_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                recent_readings = readings_list[:20]  # Get last 20 readings
                
                # Format readings for the template
                for reading in recent_readings:
                    timestamp = reading.get('timestamp', '')
                    # Format timestamp for display
                    try:
                        if timestamp:
                            # Handle different timestamp formats
                            if isinstance(timestamp, str):
                                if 'T' in timestamp:
                                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                else:
                                    dt = datetime.fromisoformat(timestamp)
                            else:
                                dt = datetime.fromtimestamp(timestamp)
                            formatted_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            formatted_timestamp = 'N/A'
                    except Exception:
                        formatted_timestamp = str(timestamp) if timestamp else 'N/A'
                    
                    historical_readings.append({
                        'timestamp': formatted_timestamp,
                        'temperature': f"{reading.get('temperature', 0.0):.1f}",
                        'ph': f"{reading.get('ph', 0.0):.2f}",
                        'ec': f"{reading.get('ec', 0.0):.2f}",
                        'tds': f"{reading.get('tds', 0.0):.0f}"
                    })
                
                # Reverse to show oldest first in the table
                historical_readings.reverse()
                
        except Exception as e:
            logger.error(f"Error fetching historical readings: {e}")
            historical_readings = []

        report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report_id = str(uuid.uuid4())[:8]
        logo_path = os.path.join(settings.BASE_DIR, 'auth_app', 'static', 'images', 'logo.png')
        logo_uri = 'file://' + pathname2url(os.path.abspath(logo_path))

        # Prepare context for template
        context = {
            'report_date': report_date,
            'report_id': report_id,
            'stage_info': stage_info,
            'parameters': parameters,
            'historical_readings': historical_readings,
            'charts': [],  # Placeholder for future chart implementation
            'user_name': user_name,
            'device_name': device_data.get('device_name', 'N/A'),
            'device_id': device_id,
            'logo_path': logo_uri,  # Adjust path as needed for WeasyPrint
        }

        # Render template to HTML
        html_string = render_to_string('report.html', context)
        
        # Generate PDF using WeasyPrint
        pdf = HTML(string=html_string).write_pdf()
        
        # Send PDF response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="hydrozap_report_{report_id}.pdf"'
        return response