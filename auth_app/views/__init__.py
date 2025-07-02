from .auth_views import (
    RegisterView,
    LoginView,
    GoogleLoginView,
    FirebaseResetPasswordView,
    UserProfileView,
    ProtectedView
)

from .device_views import (
    RegisteredDeviceView,
    DeviceView,
    DeviceCountView
)

from .sensor_views import (
    SensorDataView,
    ActuatorDataView,
    HistoricalSensorDataView
)

from .plant_views import (
    PlantProfileView,
    GrowProfileView,
    GrowView,
    HarvestLogView,
    HarvestReadinessView
)

from .alert_views import (
    AlertView,
    AlertCountView
)

from .analytics_views import (
    TipburnPredictorView,
    ColorIndexPredictorView,
    LeafCountPredictorView,
    CropSuggestionView,
    EnvironmentRecommendationView
)

from .notification_views import (
    FcmTokenView,
    TestFcmNotificationView,
    NotificationPreferencesView
)

from .report_views import (
    MonitoringReportPDFView
)

from .feedback_views import (
    FeedbackView
)

from .dashboard_views import (
    DashboardCountsView,
    GrowCountView,
)

# Define __all__ to explicitly specify which symbols should be exported
__all__ = [
    # Auth views
    'RegisterView',
    'LoginView',
    'GoogleLoginView',
    'FirebaseResetPasswordView',
    'UserProfileView',
    'ProtectedView',
    
    # Device views
    'RegisteredDeviceView',
    'DeviceView',
    'DeviceCountView',
    
    # Sensor views
    'SensorDataView',
    'ActuatorDataView',
    'HistoricalSensorDataView',
    
    # Plant views
    'PlantProfileView',
    'GrowProfileView',
    'GrowView',
    'HarvestLogView',
    'HarvestReadinessView',
    
    # Alert views
    'AlertView',
    'AlertCountView',
    
    # Analytics views
    'TipburnPredictorView',
    'ColorIndexPredictorView',
    'LeafCountPredictorView',
    'CropSuggestionView',
    'EnvironmentRecommendationView',
    
    # Notification views
    'FcmTokenView',
    'TestFcmNotificationView',
    'NotificationPreferencesView',
    
    # Report views
    'MonitoringReportPDFView',
    
    # Feedback views
    'FeedbackView',
    
    # Dashboard views
    'DashboardCountsView',
    'GrowCountView',
] 