from django.urls import path
from .views import (
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
    # Auth endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('reset-password/', FirebaseResetPasswordView.as_view(), name='reset-password'),
    path("google-login/", GoogleLoginView.as_view(), name='google-login'),
    path("user-profile/", UserProfileView.as_view(), name='user-profile'),
    path('protected/', ProtectedView.as_view(), name='protected'),
    
    # Device endpoints
    path('devices/', DeviceView.as_view(), name='device-list'),  
    path('devices/<str:device_id>/', DeviceView.as_view(), name='device-detail'),  
    path('device-count/', DeviceCountView.as_view(), name='device-count'),
    path('devices/<str:device_id>/check/', DeviceView.as_view()),
    
    # Sensor and actuator endpoints
    path('sensors/', SensorDataView.as_view(), name='sensors'),
    path('actuators/', ActuatorDataView.as_view(), name='actuators'),
    
    # Plant profile endpoints
    path('plant-profiles/', PlantProfileView.as_view(), name='plant-profiles'),
    path('plant-profiles/<str:identifier>/', PlantProfileView.as_view(), name='plant-profile-detail'),
    
    # Alert endpoints
    path('alerts/count/<str:user_id>/', AlertCountView.as_view(), name='alert-count'),
    path('alerts/<str:user_id>/<str:alert_id>/', AlertView.as_view(), name='alert-detail'),
    path('alerts/<str:user_id>/', AlertView.as_view(), name='alert-list'),
    path('alerts/', AlertView.as_view(), name='trigger-alert'),
    
    # Grow endpoints
    path('grows/', GrowView.as_view(), name='grow-list'),
    path('grows/<str:grow_id>/', GrowView.as_view(), name='grow-detail'),
    path('grows/count/<str:user_id>/', GrowCountView.as_view(), name='grow-count'),
    
    # Grow profile endpoints
    path('grow-profiles/', GrowProfileView.as_view(), name='grow-profile-list'), 
    path('grow-profiles/<str:profile_id>/', GrowProfileView.as_view(), name='grow-profile-detail'),
    
    # Harvest log endpoints
    path("harvest-logs/<str:device_id>/", HarvestLogView.as_view(), name='harvest-logs'),
    
    # Dashboard counts endpoint
    path('dashboard/counts/', DashboardCountsView.as_view(), name='dashboard_counts'),

    # Predictive model endpoints
    path('predict/tipburn/', TipburnPredictorView.as_view(), name='predict-tipburn'),
    path('predict/color-index/', ColorIndexPredictorView.as_view(), name='predict-color'),
    path('predict/leaf-count/', LeafCountPredictorView.as_view(), name='predict-count'),
    path('predict/crop-suggestion/', CropSuggestionView.as_view(), name='predict-crop'),
    path('predict/environment-recommendation/', EnvironmentRecommendationView.as_view(), name='predict-environment'),
    
    # FCM endpoints
    path('fcm-token/', FcmTokenView.as_view(), name='fcm-token'),
    path('test-fcm/', TestFcmNotificationView.as_view(), name='test-fcm'),

    # Harvest readiness endpoint
    path('harvest-readiness/<str:grow_id>/', HarvestReadinessView.as_view(), name='harvest-readiness'),

    # Notification preferences endpoints
    path('notification-preferences/<str:user_id>/', NotificationPreferencesView.as_view(), name='get_notification_preferences'),
    path('update-notification-preferences/', NotificationPreferencesView.as_view(), name='update_notification_preferences'),
    
    # Feedback endpoint
    path('feedback/', FeedbackView.as_view(), name='feedback'),
    
    # Reports and analytics
    path('generate-report/', MonitoringReportPDFView.as_view(), name='generate_report_cbv'),

    # Registered devices endpoints
    path('registered-devices/', RegisteredDeviceView.as_view(), name='registered-devices'),
    path('registered-devices/<str:device_id>/', RegisteredDeviceView.as_view(), name='registered-device-detail'),
]
