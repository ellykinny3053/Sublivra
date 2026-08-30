"""
Sublivra URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from .views import api_root

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='app-home'),
    path('api/', api_root, name='api-root'),
    path('studio-ctrl-9x7k2/', admin.site.urls),  # Obscured admin path (M-5)
    path('api/auth/', include('accounts.urls')),
    path('api/tracks/', include('tracks.urls')),
    path('api/bundles/', include('bundles.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
