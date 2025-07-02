from firebase_admin import db
from datetime import datetime
import logging
from ..views.notification_utils import send_fcm_notification
from django.conf import settings
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

def check_grow_readiness():
    """Check all active grows for harvest readiness and send notifications"""
    try:
        # Get all grows
        grows_ref = db.reference('grows')
        grows = grows_ref.get()
        
        if not grows:
            return
            
        # Get all grow profiles for reference
        profiles_ref = db.reference('grow_profiles')
        profiles = profiles_ref.get() or {}
        
        for grow_id, grow_data in grows.items():
            try:
                # Skip if already harvested
                if grow_data.get('status') == 'harvested':
                    continue
                    
                # Get grow profile
                profile_id = grow_data.get('profile_id')
                profile_data = profiles.get(profile_id, {})
                
                if not profile_data:
                    continue
                
                # Calculate progress
                start_date = datetime.fromisoformat(grow_data.get('start_date').replace('Z', '+00:00'))
                current_date = datetime.now()
                days_since_start = (current_date - start_date).days
                
                # Get grow duration from profile
                grow_duration = profile_data.get('grow_duration_days', 60)
                
                # Calculate progress percentage
                progress = min(100, (days_since_start / grow_duration) * 100)
                
                # Check if ready for harvest
                if progress >= 100:
                    user_id = grow_data.get('user_id')
                    grow_name = grow_data.get('grow_name', 'Your grow')
                    device_id = grow_data.get('device_id')
                    
                    # Get user's FCM tokens
                    user_ref = db.reference(f'users/{user_id}/fcm_tokens')
                    tokens = user_ref.get()
                    
                    if not tokens:
                        logger.warning(f"No FCM tokens found for user {user_id}")
                        continue
                        
                    # Convert tokens to list of strings
                    token_list = [str(token) for token in tokens.values() if token]
                    
                    if not token_list:
                        logger.warning(f"No valid FCM tokens found for user {user_id}")
                        continue
                    
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
                        
            except Exception as e:
                logger.error(f"Error processing grow {grow_id}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error in check_grow_readiness: {str(e)}")

def start_grow_monitor():
    """Start the background scheduler for grow monitoring"""
    try:
        scheduler = BackgroundScheduler(
            timezone='UTC',
            job_defaults={
                'coalesce': True,  # Only run once if multiple executions are missed
                'max_instances': 1  # Don't allow multiple instances of the same job
            }
        )
        
        # Schedule the check_grow_readiness function to run every hour
        scheduler.add_job(
            check_grow_readiness,
            trigger=IntervalTrigger(hours=1),
            id='grow_monitor',
            replace_existing=True,
            misfire_grace_time=3600  # Allow up to 1 hour of delay before considering it missed
        )
        
        scheduler.start()
        logger.info("Grow monitor scheduler started successfully")
        
    except Exception as e:
        logger.error(f"Error starting grow monitor scheduler: {str(e)}") 