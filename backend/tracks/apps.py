import os
import shutil
from django.apps import AppConfig


class TracksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tracks'
    verbose_name = 'Audio Tracks'

    def ready(self):
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            d = os.path.dirname(exe)
            target = os.path.join(d, 'ffmpeg.exe')
            if not os.path.exists(target):
                shutil.copy(exe, target)
            if d not in os.environ.get('PATH', ''):
                os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
        except Exception:
            pass
