"""
Views for tracks, TTS, audio editing, mixing, and YouTube import.
All views are scoped to the authenticated user's own tracks.
"""
import os

from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone

from .models import Track, Tag, YouTubeImport
from .serializers import (
    TrackListSerializer, TrackDetailSerializer,
    TrackUploadSerializer, TrackUpdateSerializer,
    TTSGenerateSerializer,
    TrimSerializer, SpeedChangeSerializer, FadeSerializer, NormalizeSerializer,
    MixerSerializer,
    YouTubeMetadataSerializer, YouTubeImportSerializer,
)
from .services import tts_service, audio_editor, mixer_service, youtube_service


# ── Track CRUD Views ─────────────────────────────────────────────────────────

class TrackListView(generics.ListAPIView):
    """List all tracks for the authenticated user."""
    serializer_class = TrackListSerializer

    def get_queryset(self):
        queryset = Track.objects.filter(user=self.request.user)
        # Optional filters
        source_type = self.request.query_params.get('source_type')
        search = self.request.query_params.get('search')
        tag = self.request.query_params.get('tag')

        if source_type:
            queryset = queryset.filter(source_type=source_type)
        if search:
            queryset = queryset.filter(title__icontains=search)
        if tag:
            queryset = queryset.filter(tags__name=tag)
        return queryset


class TrackDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a specific track."""

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return TrackUpdateSerializer
        return TrackDetailSerializer

    def get_queryset(self):
        return Track.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        # Delete the associated file from disk
        if instance.file and os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
        instance.delete()


class TrackUploadView(APIView):
    """Upload an audio file to the user's library."""
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = TrackUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        file = data['file']

        # Save the uploaded file
        track = Track(
            user=request.user,
            title=data['title'],
            file=file,
            source_type=Track.SourceType.UPLOAD,
            rights_confirmed=True,
            rights_confirmed_at=timezone.now(),
            license_info=data.get('license_info', ''),
        )
        track.save()

        # Extract audio duration using pydub
        try:
            info = audio_editor.get_audio_info(track.file.name)
            track.duration = info['duration']
            track.file_size = info['file_size']
            track.format = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else 'mp3'
            track.save()
        except Exception:
            track.file_size = file.size
            track.format = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else 'unknown'
            track.save()

        # Handle tags
        for tag_name in data.get('tags', []):
            tag, _ = Tag.objects.get_or_create(name=tag_name.strip().lower())
            track.tags.add(tag)

        return Response(
            TrackDetailSerializer(track).data,
            status=status.HTTP_201_CREATED
        )


# ── TTS Views ────────────────────────────────────────────────────────────────

class TTSLanguagesView(APIView):
    """List available TTS neural voices and languages."""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        voices = tts_service.get_available_voices()
        languages = tts_service.get_available_languages()
        language_list = [
            {'code': code, 'name': name}
            for code, name in sorted(languages.items(), key=lambda x: x[1])
        ]
        return Response({
            'voices': voices,
            'languages': language_list
        })


class TTSGenerateView(APIView):
    """Generate a TTS audio clip from text using Neural voices or gTTS."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = TTSGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = tts_service.generate_tts_audio(
                text=data['text'],
                language=data.get('language', 'en'),
                voice=data.get('voice', 'en-US-JennyNeural'),
                slow=data.get('slow', False),
                speed=data.get('speed', 1.0),
            )
        except (ValueError, RuntimeError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create Track record
        title = data.get('title') or f"Affirmation: {data['text'][:40]}..."
        track = Track.objects.create(
            user=request.user,
            title=title,
            file=result['file_path'],
            source_type=Track.SourceType.TTS,
            duration=result['duration'],
            file_size=result['file_size'],
            format=result['format'],
            tts_text=data['text'],
            tts_language=data.get('language', 'en'),
        )

        return Response(
            TrackDetailSerializer(track).data,
            status=status.HTTP_201_CREATED
        )


# ── Audio Editor Views ───────────────────────────────────────────────────────

class _BaseEditorView(APIView):
    """Base class for audio editing operations."""
    permission_classes = (permissions.IsAuthenticated,)

    def _get_track(self, request, track_id):
        """Get track owned by the current user."""
        try:
            return Track.objects.get(id=track_id, user=request.user)
        except Track.DoesNotExist:
            return None

    def _create_edited_track(self, request, source_track, result, title_prefix, title_override=''):
        """Create a new Track from an editing operation."""
        title = title_override or f"{title_prefix}: {source_track.title}"
        return Track.objects.create(
            user=request.user,
            title=title,
            file=result['file_path'],
            source_type=Track.SourceType.EDITED,
            duration=result['duration'],
            file_size=result['file_size'],
            format=result['format'],
            parent_track=source_track,
        )


class TrimView(_BaseEditorView):
    """Trim audio to a specified time range."""

    def post(self, request):
        serializer = TrimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        track = self._get_track(request, data['track_id'])
        if not track:
            return Response({'error': 'Track not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = audio_editor.trim_audio(
                file_path=track.file.name,
                start_ms=data['start_ms'],
                end_ms=data.get('end_ms'),
            )
        except (ValueError, FileNotFoundError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        new_track = self._create_edited_track(
            request, track, result, 'Trimmed', data.get('title', '')
        )
        return Response(TrackDetailSerializer(new_track).data, status=status.HTTP_201_CREATED)


class SpeedChangeView(_BaseEditorView):
    """Change audio playback speed."""

    def post(self, request):
        serializer = SpeedChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        track = self._get_track(request, data['track_id'])
        if not track:
            return Response({'error': 'Track not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = audio_editor.change_speed(
                file_path=track.file.name,
                speed=data['speed'],
            )
        except (ValueError, FileNotFoundError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        title = data.get('title', '') or f"{data['speed']}x: {track.title}"
        new_track = self._create_edited_track(
            request, track, result, f"{data['speed']}x", title
        )
        return Response(TrackDetailSerializer(new_track).data, status=status.HTTP_201_CREATED)


class FadeView(_BaseEditorView):
    """Apply fade in/out to audio."""

    def post(self, request):
        serializer = FadeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        track = self._get_track(request, data['track_id'])
        if not track:
            return Response({'error': 'Track not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = audio_editor.apply_fade(
                file_path=track.file.name,
                fade_in_ms=data['fade_in_ms'],
                fade_out_ms=data['fade_out_ms'],
            )
        except (ValueError, FileNotFoundError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        new_track = self._create_edited_track(
            request, track, result, 'Faded', data.get('title', '')
        )
        return Response(TrackDetailSerializer(new_track).data, status=status.HTTP_201_CREATED)


class NormalizeView(_BaseEditorView):
    """Normalize audio volume."""

    def post(self, request):
        serializer = NormalizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        track = self._get_track(request, data['track_id'])
        if not track:
            return Response({'error': 'Track not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = audio_editor.normalize_volume(
                file_path=track.file.name,
                target_dbfs=data['target_dbfs'],
            )
        except (ValueError, FileNotFoundError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        new_track = self._create_edited_track(
            request, track, result, 'Normalized', data.get('title', '')
        )
        return Response(TrackDetailSerializer(new_track).data, status=status.HTTP_201_CREATED)


class AudioInfoView(APIView):
    """Get detailed info about a track's audio file."""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk):
        try:
            track = Track.objects.get(id=pk, user=request.user)
        except Track.DoesNotExist:
            return Response({'error': 'Track not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            info = audio_editor.get_audio_info(track.file.name)
            return Response(info)
        except FileNotFoundError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)


# ── Mixer Views ──────────────────────────────────────────────────────────────

class MixerExportView(APIView):
    """Mix multiple tracks and export as a new track."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = MixerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Resolve track IDs to file paths
        track_configs = []
        for cfg in data['tracks']:
            try:
                track = Track.objects.get(id=cfg['track_id'], user=request.user)
            except Track.DoesNotExist:
                return Response(
                    {'error': f"Track {cfg['track_id']} not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
            track_configs.append({
                'file_path': track.file.name,
                'volume': cfg.get('volume', 0),
                'offset_ms': cfg.get('offset_ms', 0),
            })

        try:
            result = mixer_service.mix_tracks(
                track_configs,
                loop_shorter=data.get('loop_shorter', False)
            )
        except (ValueError, FileNotFoundError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Create mixed track
        track = Track.objects.create(
            user=request.user,
            title=data.get('title', 'Mixed Track'),
            file=result['file_path'],
            source_type=Track.SourceType.MIXED,
            duration=result['duration'],
            file_size=result['file_size'],
            format=result['format'],
        )

        return Response(
            TrackDetailSerializer(track).data,
            status=status.HTTP_201_CREATED
        )


# ── YouTube Import Views ─────────────────────────────────────────────────────

class YouTubeMetadataView(APIView):
    """Fetch metadata for a YouTube video URL."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = YouTubeMetadataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            metadata = youtube_service.get_video_metadata(serializer.validated_data['url'])
            return Response(metadata)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class YouTubeImportView(APIView):
    """Import audio from a YouTube video after rights confirmation."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = YouTubeImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        url = data['url']

        # Get video metadata first
        try:
            metadata = youtube_service.get_video_metadata(url)
        except (ValueError, RuntimeError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"Failed to retrieve video metadata: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Download audio
        try:
            result = youtube_service.download_audio(url)
        except (ValueError, RuntimeError) as e:
            return Response(
                {
                    'error': str(e),
                    'suggestion': 'You can upload the audio file directly if you own it or have permission to use it.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({'error': f"Audio download failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Create Track record
            raw_title = data.get('title') or metadata.get('title') or 'YouTube Import'
            title = str(raw_title)[:250]
            
            # Normalize file path with forward slashes for cross-platform FileField compatibility
            file_path = str(result['file_path']).replace('\\', '/')
            
            track = Track.objects.create(
                user=request.user,
                title=title,
                file=file_path,
                source_type=Track.SourceType.YOUTUBE_AUTHORIZED,
                source_url=str(url)[:500],
                duration=result.get('duration'),
                file_size=result.get('file_size'),
                format=result.get('format', 'mp3'),
                rights_confirmed=True,
                rights_confirmed_at=timezone.now(),
                license_info=str(data.get('license_info', ''))[:1000],
            )

            # Create YouTubeImport record
            YouTubeImport.objects.create(
                track=track,
                youtube_url=str(url)[:500],
                video_id=str(metadata.get('video_id', ''))[:20],
                title=str(metadata.get('title', title))[:490],
                channel_name=str(metadata.get('channel_name', ''))[:250],
                thumbnail_url=str(metadata.get('thumbnail_url', ''))[:490],
                video_duration=metadata.get('duration'),
                rights_confirmed=True,
                confirmed_at=timezone.now(),
                license_info=str(data.get('license_info', ''))[:1000],
            )

            return Response(
                TrackDetailSerializer(track).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Failed to save imported YouTube track record")
            return Response(
                {'error': f"Database save failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
