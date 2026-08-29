"""
Models for audio tracks, tags, and YouTube imports.
"""
import os
from django.db import models
from django.conf import settings


class Tag(models.Model):
    """Tags for organizing audio tracks."""
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tags'
        ordering = ['name']

    def __str__(self):
        return self.name


class Track(models.Model):
    """
    Core model representing an audio track in the user's library.
    Tracks can originate from uploads, TTS generation, YouTube imports,
    audio editing, or mixing operations.
    """

    class SourceType(models.TextChoices):
        UPLOAD = 'upload', 'Uploaded'
        TTS = 'tts', 'Text-to-Speech'
        LICENSED_IMPORT = 'licensed_import', 'Licensed Import'
        YOUTUBE_AUTHORIZED = 'youtube_authorized', 'YouTube (Authorized)'
        EDITED = 'edited', 'Edited'
        MIXED = 'mixed', 'Mixed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tracks'
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='tracks/%Y/%m/')
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.UPLOAD
    )
    source_url = models.URLField(max_length=500, blank=True, default='')
    duration = models.FloatField(
        help_text='Duration in seconds',
        null=True,
        blank=True
    )
    file_size = models.BigIntegerField(
        help_text='File size in bytes',
        null=True,
        blank=True
    )
    format = models.CharField(max_length=10, blank=True, default='mp3')

    # Rights/consent tracking
    rights_confirmed = models.BooleanField(default=False)
    rights_confirmed_at = models.DateTimeField(null=True, blank=True)
    license_info = models.TextField(blank=True, default='')

    # TTS-specific metadata
    tts_text = models.TextField(
        blank=True, default='',
        help_text='Original text used for TTS generation'
    )
    tts_language = models.CharField(max_length=10, blank=True, default='')

    # Edit history — reference to the parent track this was derived from
    parent_track = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_tracks'
    )

    # Organization
    tags = models.ManyToManyField(Tag, blank=True, related_name='tracks')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tracks'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.source_type})"

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def duration_display(self):
        """Return duration as MM:SS format."""
        if self.duration is None:
            return '--:--'
        minutes = int(self.duration // 60)
        seconds = int(self.duration % 60)
        return f"{minutes:02d}:{seconds:02d}"


class YouTubeImport(models.Model):
    """
    Records metadata for tracks imported from YouTube.
    Stores the user's rights confirmation and video metadata.
    """
    track = models.OneToOneField(
        Track,
        on_delete=models.CASCADE,
        related_name='youtube_import'
    )
    youtube_url = models.URLField(max_length=500)
    video_id = models.CharField(max_length=20)
    title = models.CharField(max_length=500)
    channel_name = models.CharField(max_length=255, blank=True, default='')
    thumbnail_url = models.URLField(max_length=500, blank=True, default='')
    video_duration = models.FloatField(
        help_text='Video duration in seconds',
        null=True,
        blank=True
    )
    rights_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    license_info = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'youtube_imports'
        ordering = ['-created_at']

    def __str__(self):
        return f"YT Import: {self.title} ({self.video_id})"
