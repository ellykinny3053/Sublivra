"""
Views for bundles and playlists — CRUD, track management, and export.
"""
import os
import zipfile
import tempfile

from django.db import models as db_models

from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import FileResponse
from django.conf import settings

from tracks.models import Track
from tracks.serializers import TrackDetailSerializer
from tracks.services import mixer_service
from tracks.services.track_resolver import resolve_tracks_files

from .models import Bundle, BundleTrack, Playlist, PlaylistTrack
from .serializers import (
    BundleListSerializer, BundleDetailSerializer, BundleCreateSerializer,
    BundleAddTrackSerializer,
    PlaylistListSerializer, PlaylistDetailSerializer, PlaylistCreateSerializer,
    PlaylistAddTrackSerializer, PlaylistReorderSerializer,
)


# ── Bundle Views ─────────────────────────────────────────────────────────────

class BundleListCreateView(generics.ListCreateAPIView):
    """List all bundles or create a new one."""

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BundleCreateSerializer
        return BundleListSerializer

    def get_queryset(self):
        return Bundle.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Return full detail view
        bundle = serializer.instance
        return Response(
            BundleDetailSerializer(bundle).data,
            status=status.HTTP_201_CREATED
        )


class BundleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a bundle."""

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return BundleCreateSerializer
        return BundleDetailSerializer

    def get_queryset(self):
        return Bundle.objects.filter(user=self.request.user)


class BundleAddTrackView(APIView):
    """Add a track to a bundle."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        try:
            bundle = Bundle.objects.get(id=pk, user=request.user)
        except Bundle.DoesNotExist:
            return Response({'error': 'Bundle not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BundleAddTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            track = Track.objects.get(id=data['track_id'], user=request.user)
        except Track.DoesNotExist:
            return Response({'error': 'Track not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check if already added
        if BundleTrack.objects.filter(bundle=bundle, track=track).exists():
            return Response(
                {'error': 'Track is already in this bundle.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Auto-assign order_index if not provided
        order = data.get('order_index', 0)
        if order == 0:
            max_order = bundle.bundle_tracks.aggregate(
                max_order=db_models.Max('order_index')
            )['max_order']
            order = (max_order or 0) + 1

        BundleTrack.objects.create(
            bundle=bundle,
            track=track,
            order_index=order,
            volume=data.get('volume', 0),
        )

        return Response(
            BundleDetailSerializer(bundle).data,
            status=status.HTTP_201_CREATED
        )


class BundleRemoveTrackView(APIView):
    """Remove a track from a bundle."""
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self, request, pk, track_id):
        try:
            bundle = Bundle.objects.get(id=pk, user=request.user)
        except Bundle.DoesNotExist:
            return Response({'error': 'Bundle not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted, _ = BundleTrack.objects.filter(
            bundle=bundle, track_id=track_id
        ).delete()

        if deleted == 0:
            return Response(
                {'error': 'Track not found in this bundle.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            BundleDetailSerializer(bundle).data,
            status=status.HTTP_200_OK
        )


class BundleExportView(APIView):
    """
    Export a subliminal bundle by layering and mixing all tracks simultaneously
    into a single combined audio track (or optional ZIP if format=zip is requested).
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk):
        return self._export(request, pk)

    def post(self, request, pk):
        return self._export(request, pk)

    def _export(self, request, pk):
        try:
            bundle = Bundle.objects.get(id=pk, user=request.user)
        except Bundle.DoesNotExist:
            return Response({'error': 'Bundle not found.'}, status=status.HTTP_404_NOT_FOUND)

        bundle_tracks = bundle.bundle_tracks.select_related('track').all()
        if not bundle_tracks.exists():
            return Response(
                {'error': 'Bundle has no tracks to layer.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        tracks = [bt.track for bt in bundle_tracks if bt.track]
        if not tracks:
            return Response({'error': 'No valid tracks found in bundle.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            valid_items, skipped_tracks = resolve_tracks_files(tracks, auto_heal=True, allow_skip=True)
            path_map = {t.id: p for t, p in valid_items}
        except Exception as e:
            return Response({'error': f"Failed to prepare audio files: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        query_params = getattr(request, 'query_params', request.GET)
        export_format = query_params.get('format', 'audio').lower()

        # If user explicitly wants a raw ZIP package:
        if export_format == 'zip':
            export_dir = os.path.join(settings.MEDIA_ROOT, settings.AUDIO_SETTINGS['EXPORT_OUTPUT_DIR'])
            os.makedirs(export_dir, exist_ok=True)
            zip_filename = f"{bundle.title.replace(' ', '_')}_{bundle.id}.zip"
            zip_path = os.path.join(export_dir, zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for bt in bundle_tracks:
                    full_path = path_map.get(bt.track.id)
                    if full_path and os.path.exists(full_path):
                        ext = os.path.splitext(full_path)[1]
                        arc_name = f"{bt.order_index:02d}_{bt.track.title}{ext}"
                        zf.write(full_path, arc_name)

            response = FileResponse(open(zip_path, 'rb'), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
            return response

        # Default Subliminal Bundle: Layer and play all subliminal tracks simultaneously
        track_configs = []
        for bt in bundle_tracks:
            full_path = path_map.get(bt.track.id)
            if full_path and os.path.exists(full_path):
                track_configs.append({
                    'file_path': full_path,
                    'volume': 0,
                    'offset_ms': 0,
                })

        if not track_configs:
            return Response({'error': 'No valid audio files found in bundle.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            loop_shorter = query_params.get('loop_shorter', 'true').lower() in ('true', '1')
            result = mixer_service.mix_tracks(track_configs, loop_shorter=loop_shorter)
        except (ValueError, FileNotFoundError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Bundle export failed")
            return Response({'error': f"Bundle export failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Create Track record for the layered subliminal bundle
        export_track = Track.objects.create(
            user=request.user,
            title=f"Subliminal Bundle: {bundle.title}",
            file=result['file_path'],
            source_type=Track.SourceType.MIXED,
            duration=result['duration'],
            file_size=result['file_size'],
            format=result['format'],
            rights_confirmed=True,
        )

        return Response(
            TrackDetailSerializer(export_track).data,
            status=status.HTTP_201_CREATED
        )


# ── Playlist Views ───────────────────────────────────────────────────────────

class PlaylistListCreateView(generics.ListCreateAPIView):
    """List all playlists or create a new one."""

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PlaylistCreateSerializer
        return PlaylistListSerializer

    def get_queryset(self):
        return Playlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        playlist = serializer.instance
        return Response(
            PlaylistDetailSerializer(playlist).data,
            status=status.HTTP_201_CREATED
        )


class PlaylistDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a playlist."""

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return PlaylistCreateSerializer
        return PlaylistDetailSerializer

    def get_queryset(self):
        return Playlist.objects.filter(user=self.request.user)


class PlaylistAddTrackView(APIView):
    """Add a track to a playlist."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        try:
            playlist = Playlist.objects.get(id=pk, user=request.user)
        except Playlist.DoesNotExist:
            return Response({'error': 'Playlist not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PlaylistAddTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            track = Track.objects.get(id=data['track_id'], user=request.user)
        except Track.DoesNotExist:
            return Response({'error': 'Track not found.'}, status=status.HTTP_404_NOT_FOUND)

        if PlaylistTrack.objects.filter(playlist=playlist, track=track).exists():
            return Response(
                {'error': 'Track is already in this playlist.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order = data.get('order_index', 0)
        if order == 0:
            from django.db.models import Max
            max_order = playlist.playlist_tracks.aggregate(
                max_order=Max('order_index')
            )['max_order']
            order = (max_order or 0) + 1

        PlaylistTrack.objects.create(
            playlist=playlist,
            track=track,
            order_index=order,
        )

        return Response(
            PlaylistDetailSerializer(playlist).data,
            status=status.HTTP_201_CREATED
        )


class PlaylistRemoveTrackView(APIView):
    """Remove a track from a playlist."""
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self, request, pk, track_id):
        try:
            playlist = Playlist.objects.get(id=pk, user=request.user)
        except Playlist.DoesNotExist:
            return Response({'error': 'Playlist not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted, _ = PlaylistTrack.objects.filter(
            playlist=playlist, track_id=track_id
        ).delete()

        if deleted == 0:
            return Response(
                {'error': 'Track not found in this playlist.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            PlaylistDetailSerializer(playlist).data,
            status=status.HTTP_200_OK
        )


class PlaylistReorderView(APIView):
    """Reorder tracks in a playlist."""
    permission_classes = (permissions.IsAuthenticated,)

    def patch(self, request, pk):
        try:
            playlist = Playlist.objects.get(id=pk, user=request.user)
        except Playlist.DoesNotExist:
            return Response({'error': 'Playlist not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PlaylistReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        track_order = serializer.validated_data['track_order']

        # Update order indices
        for idx, track_id in enumerate(track_order):
            PlaylistTrack.objects.filter(
                playlist=playlist, track_id=track_id
            ).update(order_index=idx + 1)

        return Response(
            PlaylistDetailSerializer(playlist).data,
            status=status.HTTP_200_OK
        )


class PlaylistExportView(APIView):
    """Export a playlist as a single concatenated audio file."""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk):
        return self._export(request, pk)

    def post(self, request, pk):
        return self._export(request, pk)

    def _export(self, request, pk):
        try:
            playlist = Playlist.objects.get(id=pk, user=request.user)
        except Playlist.DoesNotExist:
            return Response({'error': 'Playlist not found.'}, status=status.HTTP_404_NOT_FOUND)

        playlist_tracks = playlist.playlist_tracks.select_related('track').all()
        if not playlist_tracks.exists():
            return Response(
                {'error': 'Playlist has no tracks to export.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        tracks = [pt.track for pt in playlist_tracks if pt.track]
        if not tracks:
            return Response(
                {'error': 'No valid audio tracks found in playlist.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Self-heal and resolve audio files, gracefully skipping any dead/unavailable YouTube videos
        try:
            valid_items, skipped_tracks = resolve_tracks_files(tracks, auto_heal=True, allow_skip=True)
            resolved_paths = [p for _, p in valid_items]
        except Exception as e:
            return Response(
                {'error': f"Failed to prepare audio files: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not resolved_paths:
            return Response(
                {'error': 'None of the tracks in this playlist could be retrieved. The source videos may have been removed or made private on YouTube.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            query_params = getattr(request, 'query_params', request.GET)
            crossfade = int(query_params.get('crossfade_ms', 0))
            result = mixer_service.concatenate_tracks(resolved_paths, crossfade_ms=crossfade)
        except (ValueError, FileNotFoundError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Playlist export failed")
            return Response({'error': f"Playlist export failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Create a Track record for the export
        export_track = Track.objects.create(
            user=request.user,
            title=f"Playlist Export: {playlist.title}",
            file=result['file_path'],
            source_type=Track.SourceType.MIXED,
            duration=result['duration'],
            file_size=result['file_size'],
            format=result['format'],
            rights_confirmed=True,
        )

        response_data = TrackDetailSerializer(export_track).data
        if skipped_tracks:
            response_data['skipped_tracks'] = skipped_tracks
            response_data['notice'] = f"Exported {len(resolved_paths)} tracks. Skipped {len(skipped_tracks)} unavailable track(s): {', '.join(skipped_tracks)}"

        return Response(
            response_data,
            status=status.HTTP_201_CREATED
        )
