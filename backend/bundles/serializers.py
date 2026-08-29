"""
Serializers for bundles and playlists with nested track relationships.
"""
from rest_framework import serializers
from .models import Bundle, BundleTrack, Playlist, PlaylistTrack
from tracks.serializers import TrackListSerializer


# ── Bundle Serializers ───────────────────────────────────────────────────────

class BundleTrackSerializer(serializers.ModelSerializer):
    """Nested serializer for tracks within a bundle."""
    track = TrackListSerializer(read_only=True)

    class Meta:
        model = BundleTrack
        fields = ('id', 'track', 'order_index', 'volume')


class BundleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing bundles."""
    track_count = serializers.IntegerField(read_only=True, source='bundle_tracks.count')

    class Meta:
        model = Bundle
        fields = ('id', 'title', 'description', 'track_count', 'created_at')


class BundleDetailSerializer(serializers.ModelSerializer):
    """Full serializer for bundle detail with all tracks."""
    tracks = BundleTrackSerializer(many=True, read_only=True, source='bundle_tracks')
    track_count = serializers.IntegerField(read_only=True, source='bundle_tracks.count')

    class Meta:
        model = Bundle
        fields = ('id', 'title', 'description', 'tracks', 'track_count', 'created_at', 'updated_at')


class BundleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating bundles."""

    class Meta:
        model = Bundle
        fields = ('title', 'description')


class BundleAddTrackSerializer(serializers.Serializer):
    """Serializer for adding a track to a bundle."""
    track_id = serializers.IntegerField()
    order_index = serializers.IntegerField(default=0)
    volume = serializers.FloatField(default=0)


class PlaylistTrackSerializer(serializers.ModelSerializer):
    """Nested serializer for tracks within a playlist."""
    id = serializers.IntegerField(source='track.id', read_only=True)
    title = serializers.CharField(source='track.title', read_only=True)
    duration = serializers.FloatField(source='track.duration', read_only=True)
    duration_display = serializers.CharField(source='track.duration_display', read_only=True)
    source_type = serializers.CharField(source='track.source_type', read_only=True)
    audio_file = serializers.SerializerMethodField()
    playlist_track_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = PlaylistTrack
        fields = ('id', 'playlist_track_id', 'title', 'duration', 'duration_display', 'source_type', 'audio_file', 'order_index')

    def get_audio_file(self, obj):
        if obj.track and obj.track.file:
            return obj.track.file.url
        return None


class PlaylistListSerializer(serializers.ModelSerializer):
    """Serializer for listing playlists with ordered tracks."""
    tracks = PlaylistTrackSerializer(many=True, read_only=True, source='playlist_tracks')
    track_count = serializers.IntegerField(read_only=True, source='playlist_tracks.count')
    total_duration = serializers.FloatField(read_only=True)

    class Meta:
        model = Playlist
        fields = ('id', 'title', 'description', 'tracks', 'track_count', 'total_duration', 'created_at')


class PlaylistDetailSerializer(serializers.ModelSerializer):
    """Full serializer for playlist detail with all tracks."""
    tracks = PlaylistTrackSerializer(many=True, read_only=True, source='playlist_tracks')
    track_count = serializers.IntegerField(read_only=True, source='playlist_tracks.count')
    total_duration = serializers.FloatField(read_only=True)

    class Meta:
        model = Playlist
        fields = ('id', 'title', 'description', 'tracks', 'track_count', 'total_duration', 'created_at', 'updated_at')


class PlaylistCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating playlists."""

    class Meta:
        model = Playlist
        fields = ('title', 'description')


class PlaylistAddTrackSerializer(serializers.Serializer):
    """Serializer for adding a track to a playlist."""
    track_id = serializers.IntegerField()
    order_index = serializers.IntegerField(default=0)


class PlaylistReorderSerializer(serializers.Serializer):
    """Serializer for reordering tracks in a playlist."""
    track_order = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Ordered list of track IDs"
    )
