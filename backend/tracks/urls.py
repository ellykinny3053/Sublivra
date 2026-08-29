"""
URL patterns for tracks, TTS, audio editing, mixing, and YouTube import.
"""
from django.urls import path
from .views import (
    TrackListView, TrackDetailView, TrackUploadView,
    TTSLanguagesView, TTSGenerateView,
    TrimView, SpeedChangeView, FadeView, NormalizeView, AudioInfoView,
    MixerExportView,
    YouTubeMetadataView, YouTubeImportView,
)

app_name = 'tracks'

urlpatterns = [
    # Track CRUD
    path('', TrackListView.as_view(), name='track-list'),
    path('upload/', TrackUploadView.as_view(), name='track-upload'),
    path('<int:pk>/', TrackDetailView.as_view(), name='track-detail'),
    path('<int:pk>/info/', AudioInfoView.as_view(), name='track-info'),

    # TTS
    path('tts/languages/', TTSLanguagesView.as_view(), name='tts-languages'),
    path('tts/generate/', TTSGenerateView.as_view(), name='tts-generate'),

    # Audio Editor
    path('editor/trim/', TrimView.as_view(), name='editor-trim'),
    path('editor/speed/', SpeedChangeView.as_view(), name='editor-speed'),
    path('editor/fade/', FadeView.as_view(), name='editor-fade'),
    path('editor/normalize/', NormalizeView.as_view(), name='editor-normalize'),

    # Mixer
    path('mixer/export/', MixerExportView.as_view(), name='mixer-export'),

    # YouTube
    path('youtube/metadata/', YouTubeMetadataView.as_view(), name='youtube-metadata'),
    path('youtube/import/', YouTubeImportView.as_view(), name='youtube-import'),
]
