"""
Serializers for tracks, TTS, audio editing, mixing, and YouTube import.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import Track, Tag, YouTubeImport


# ── Tag Serializers ──────────────────────────────────────────────────────────

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name')


# ── Track Serializers ────────────────────────────────────────────────────────

class TrackListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing tracks."""
    tags = TagSerializer(many=True, read_only=True)
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = Track
        fields = (
            'id', 'title', 'file', 'source_type', 'duration',
            'duration_display', 'file_size', 'format', 'tags',
            'created_at',
        )


class TrackDetailSerializer(serializers.ModelSerializer):
    """Full serializer for track detail view."""
    tags = TagSerializer(many=True, read_only=True)
    duration_display = serializers.CharField(read_only=True)
    youtube_import = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = (
            'id', 'title', 'file', 'source_type', 'source_url',
            'duration', 'duration_display', 'file_size', 'format',
            'rights_confirmed', 'rights_confirmed_at', 'license_info',
            'tts_text', 'tts_language',
            'parent_track', 'tags', 'youtube_import',
            'created_at', 'updated_at',
        )

    def get_youtube_import(self, obj):
        if hasattr(obj, 'youtube_import'):
            try:
                yt = obj.youtube_import
                return {
                    'video_id': yt.video_id,
                    'title': yt.title,
                    'channel_name': yt.channel_name,
                    'thumbnail_url': yt.thumbnail_url,
                    'youtube_url': yt.youtube_url,
                }
            except YouTubeImport.DoesNotExist:
                pass
        return None


class TrackUploadSerializer(serializers.Serializer):
    """Serializer for audio file upload."""
    title = serializers.CharField(max_length=255)
    file = serializers.FileField()
    rights_confirmed = serializers.BooleanField()
    license_info = serializers.CharField(required=False, default='', allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list
    )

    def validate_rights_confirmed(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must confirm that you own this audio or have the rights to upload it."
            )
        return value

    def validate_file(self, value):
        # Check file size
        max_size = 50 * 1024 * 1024  # 50MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size exceeds maximum of 50MB. Your file is {value.size / (1024*1024):.1f}MB."
            )
        # Check file extension
        ext = value.name.rsplit('.', 1)[-1].lower() if '.' in value.name else ''
        from django.conf import settings
        allowed = settings.AUDIO_SETTINGS['ALLOWED_AUDIO_FORMATS']
        if ext not in allowed:
            raise serializers.ValidationError(
                f"Unsupported file format '{ext}'. Allowed formats: {', '.join(allowed)}"
            )
        return value


class TrackUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating track metadata."""
    tags = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False
    )

    class Meta:
        model = Track
        fields = ('title', 'tags')

    def update(self, instance, validated_data):
        tag_names = validated_data.pop('tags', None)
        instance.title = validated_data.get('title', instance.title)
        instance.save()

        if tag_names is not None:
            tags = []
            for name in tag_names:
                tag, _ = Tag.objects.get_or_create(name=name.strip().lower())
                tags.append(tag)
            instance.tags.set(tags)

        return instance


# ── TTS Serializers ──────────────────────────────────────────────────────────

class TTSGenerateSerializer(serializers.Serializer):
    """Serializer for TTS generation request."""
    text = serializers.CharField(max_length=10000)
    title = serializers.CharField(max_length=255, required=False, default='')
    language = serializers.CharField(max_length=10, default='en')
    voice = serializers.CharField(max_length=100, required=False, default='en-US-JennyNeural')
    slow = serializers.BooleanField(default=False)
    speed = serializers.FloatField(default=1.0, min_value=0.25, max_value=4.0)

    def validate_text(self, value):
        if not value.strip():
            raise serializers.ValidationError("Text cannot be empty.")
        return value.strip()


# ── Audio Editor Serializers ─────────────────────────────────────────────────

class TrimSerializer(serializers.Serializer):
    """Serializer for trim operation."""
    track_id = serializers.IntegerField()
    start_ms = serializers.IntegerField(min_value=0, default=0)
    end_ms = serializers.IntegerField(min_value=0, required=False)
    title = serializers.CharField(max_length=255, required=False, default='')


class SpeedChangeSerializer(serializers.Serializer):
    """Serializer for speed change operation."""
    track_id = serializers.IntegerField()
    speed = serializers.FloatField(min_value=0.25, max_value=4.0)
    title = serializers.CharField(max_length=255, required=False, default='')


class FadeSerializer(serializers.Serializer):
    """Serializer for fade in/out operation."""
    track_id = serializers.IntegerField()
    fade_in_ms = serializers.IntegerField(min_value=0, default=0)
    fade_out_ms = serializers.IntegerField(min_value=0, default=0)
    title = serializers.CharField(max_length=255, required=False, default='')


class NormalizeSerializer(serializers.Serializer):
    """Serializer for volume normalization."""
    track_id = serializers.IntegerField()
    target_dbfs = serializers.FloatField(default=-20.0)
    title = serializers.CharField(max_length=255, required=False, default='')


# ── Mixer Serializers ────────────────────────────────────────────────────────

class MixerTrackConfigSerializer(serializers.Serializer):
    """Serializer for a single track in a mix configuration."""
    track_id = serializers.IntegerField()
    volume = serializers.FloatField(default=0, help_text="Volume adjustment in dB")
    offset_ms = serializers.IntegerField(default=0, min_value=0)


class MixerSerializer(serializers.Serializer):
    """Serializer for mixing multiple tracks."""
    tracks = MixerTrackConfigSerializer(many=True)
    title = serializers.CharField(max_length=255, required=False, default='Mixed Track')
    loop_shorter = serializers.BooleanField(default=False)

    def validate_tracks(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("At least 2 tracks are required for mixing.")
        return value


# ── YouTube Serializers ──────────────────────────────────────────────────────

class YouTubeMetadataSerializer(serializers.Serializer):
    """Serializer for YouTube metadata request."""
    url = serializers.URLField()


class YouTubeImportSerializer(serializers.Serializer):
    """Serializer for YouTube audio import."""
    url = serializers.URLField()
    rights_confirmed = serializers.BooleanField()
    license_info = serializers.CharField(required=False, default='', allow_blank=True)
    title = serializers.CharField(max_length=255, required=False, default='')

    def validate_rights_confirmed(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must confirm that you own this content or have permission "
                "to download and use its audio."
            )
        return value
