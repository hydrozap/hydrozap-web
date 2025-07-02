"""
ASGI config for hydrozap project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import auth_app.routing  # We'll create this routing file

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hydrozap.settings')
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            auth_app.routing.websocket_urlpatterns
        )
    ),
})
