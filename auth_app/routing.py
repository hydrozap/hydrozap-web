from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/devices/(?P<user_id>\w+)/$', consumers.DeviceConsumer.as_asgi()),
    re_path(r'ws/dashboard/(?P<user_id>\w+)/$', consumers.DashboardConsumer.as_asgi()),
] 