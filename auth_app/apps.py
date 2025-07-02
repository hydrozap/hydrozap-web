from django.apps import AppConfig


class AuthAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auth_app'

    def ready(self):
        """Initialize app when Django starts"""
        try:
            # Import and start the grow monitor
            from .tasks.grow_monitor import start_grow_monitor
            start_grow_monitor()
        except Exception as e:
            # Log error but don't prevent app from starting
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error starting grow monitor: {str(e)}")
