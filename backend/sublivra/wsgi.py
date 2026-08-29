"""
WSGI config for Sublivra project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sublivra.settings')
application = get_wsgi_application()
