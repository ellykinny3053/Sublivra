"""
Root API view for Sublivra.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    return Response({
        "name": "Sublivra — Subliminal & Affirmation Audio Studio API",
        "version": "1.0.0",
        "status": "online",
        "endpoints": {
            "auth": {
                "register": "/api/auth/register/",
                "login": "/api/auth/login/",
                "refresh": "/api/auth/refresh/",
                "profile": "/api/auth/me/",
                "change_password": "/api/auth/change-password/",
                "logout": "/api/auth/logout/",
            },
            "tracks": {
                "list_and_filter": "/api/tracks/",
                "upload": "/api/tracks/upload/",
                "track_detail": "/api/tracks/<id>/",
                "track_info": "/api/tracks/<id>/info/",
                "tts_languages": "/api/tracks/tts/languages/",
                "tts_generate": "/api/tracks/tts/generate/",
                "editor_trim": "/api/tracks/editor/trim/",
                "editor_speed": "/api/tracks/editor/speed/",
                "editor_fade": "/api/tracks/editor/fade/",
                "editor_normalize": "/api/tracks/editor/normalize/",
                "mixer_export": "/api/tracks/mixer/export/",
                "youtube_metadata": "/api/tracks/youtube/metadata/",
                "youtube_import": "/api/tracks/youtube/import/",
            },
            "bundles": {
                "bundles_list": "/api/bundles/",
                "bundle_detail": "/api/bundles/<id>/",
                "bundle_add_track": "/api/bundles/<id>/tracks/",
                "bundle_export_zip": "/api/bundles/<id>/export/",
                "playlists_list": "/api/bundles/playlists/",
                "playlist_detail": "/api/bundles/playlists/<id>/",
                "playlist_add_track": "/api/bundles/playlists/<id>/tracks/",
                "playlist_reorder": "/api/bundles/playlists/<id>/reorder/",
                "playlist_export_audio": "/api/bundles/playlists/<id>/export/",
            },
            "admin": "/studio-ctrl-9x7k2/",
        }
    })
