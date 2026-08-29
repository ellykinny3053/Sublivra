"""
URL patterns for authentication endpoints.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegisterView, ProfileView, ChangePasswordView

app_name = 'accounts'

urlpatterns = [
    # Registration
    path('register/', RegisterView.as_view(), name='register'),

    # JWT Token endpoints
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # Profile
    path('me/', ProfileView.as_view(), name='profile'),

    # Password
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]
