"""
URL configuration for hydrozap project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from auth_app.views import (
    # Auth views
    RegisterView,
    LoginView,
    GoogleLoginView,
    FirebaseResetPasswordView,
    UserProfileView,
    ProtectedView,
    
    # Device views
    RegisteredDeviceView,
    DeviceView,
    DeviceCountView,
    
    # Sensor views
    SensorDataView,
    ActuatorDataView,
    HistoricalSensorDataView,
    
    # Plant views
    PlantProfileView,
    GrowProfileView,
    GrowView,
    HarvestLogView,
    HarvestReadinessView,
    
    # Alert views
    AlertView,
    AlertCountView,
    
    # Analytics views
    TipburnPredictorView,
    ColorIndexPredictorView,
    LeafCountPredictorView,
    CropSuggestionView,
    EnvironmentRecommendationView,
    
    # Notification views
    FcmTokenView,
    TestFcmNotificationView,
    NotificationPreferencesView,
    
    # Report views
    MonitoringReportPDFView,
    
    # Feedback views
    FeedbackView,
    
    # Dashboard views
    DashboardCountsView,
    GrowCountView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth endpoints
    path('api/register/', RegisterView.as_view()),
    path('api/login/', LoginView.as_view()),
    path('api/google-login/', GoogleLoginView.as_view()),
    path('api/reset-password/', FirebaseResetPasswordView.as_view()),
    path('api/user-profile/', UserProfileView.as_view()),
    
    # Protected endpoint example
    path('api/protected/', ProtectedView.as_view()),
    
    # Sensor data endpoints
    path('api/sensor-data/', SensorDataView.as_view()),
    path('api/sensor-data/<str:device_id>/', HistoricalSensorDataView.as_view()),
    
    # Actuator data endpoint
    path('api/actuator-data/', ActuatorDataView.as_view()),
    
    # Device endpoints
    path('api/devices/', DeviceView.as_view()),
    path('api/devices/<str:device_id>/', DeviceView.as_view()),
    path('api/devices/<str:device_id>/check-delete/', DeviceView.as_view()),
    path('api/devices/<str:device_id>/current_thresholds/', DeviceView.as_view()),
    path('api/device-count/', DeviceCountView.as_view()),
    
    # Plant profile endpoints
    path('api/plant-profiles/', PlantProfileView.as_view()),
    path('api/plant-profiles/<str:identifier>/', PlantProfileView.as_view()),
    
    # Grow profile endpoints
    path('api/grow-profiles/', GrowProfileView.as_view()),
    path('api/grow-profiles/<str:profile_id>/', GrowProfileView.as_view()),
    
    # Grow endpoints
    path('api/grows/', GrowView.as_view()),
    path('api/grows/<str:grow_id>/', GrowView.as_view()),
    path('api/grow-count/<str:user_id>/', GrowCountView.as_view()),
    
    # Alert endpoints
    path('api/alerts/<str:user_id>/', AlertView.as_view()),
    path('api/alerts/<str:user_id>/<str:alert_id>/', AlertView.as_view()),
    path('api/alerts/', AlertView.as_view()),
    path('api/alert-count/<str:user_id>/', AlertCountView.as_view()),
    
    # Dashboard counts
    path('api/dashboard-counts/', DashboardCountsView.as_view()),
    
    # Harvest logs
    path('api/harvest-logs/<str:device_id>/', HarvestLogView.as_view()),
    path('api/harvest-logs/<str:device_id>/<str:grow_id>/', HarvestLogView.as_view()),
    
    # Machine learning prediction endpoints
    path('api/predict/tipburn/', TipburnPredictorView.as_view()),
    path('api/predict/color-index/', ColorIndexPredictorView.as_view()),
    path('api/predict/leaf-count/', LeafCountPredictorView.as_view()),
    path('api/predict/crop-suggestion/', CropSuggestionView.as_view()),
    path('api/predict/environment-recommendation/', EnvironmentRecommendationView.as_view()),
    
    # FCM token endpoint
    path('api/fcm-token/', FcmTokenView.as_view()),
    
    # FCM test notification endpoint
    path('api/test-notification/', TestFcmNotificationView.as_view()),

    # Harvest readiness endpoint
    path('api/harvest-readiness/<str:grow_id>/', HarvestReadinessView.as_view(), name='harvest-readiness'),

    # Notification preferences endpoints
    path('api/notification-preferences/<str:user_id>/', NotificationPreferencesView.as_view(), name='get_notification_preferences'),
    path('api/update-notification-preferences/', NotificationPreferencesView.as_view(), name='update_notification_preferences'),

    # Feedback endpoint
    path('api/feedback/', FeedbackView.as_view(), name='feedback'),
    
    # Reports and analytics
    path('api/generate-report/', MonitoringReportPDFView.as_view(), name='generate_report_cbv'),
    
    # Registered devices endpoints
    path('api/registered-devices/', RegisteredDeviceView.as_view(), name='registered-devices'),
    path('api/registered-devices/<str:device_id>/', RegisteredDeviceView.as_view(), name='registered-device-detail'),
]
