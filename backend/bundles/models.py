"""
Models for bundles and playlists.
Bundles group tracks for zip export; playlists order tracks for sequential playback.
"""
from django.db import models
from django.conf import settings

from tracks.models import Track


class Bundle(models.Model):
    """
    A bundle groups multiple tracks together.
    Can be exported as a zip file containing all tracks.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bundles'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bundles'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def track_count(self):
        return self.bundle_tracks.count()


class BundleTrack(models.Model):
    """Junction table linking tracks to bundles with ordering and volume."""
    bundle = models.ForeignKey(
        Bundle,
        on_delete=models.CASCADE,
        related_name='bundle_tracks'
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name='bundle_entries'
    )
    order_index = models.IntegerField(default=0)
    volume = models.FloatField(
        default=0,
        help_text='Volume adjustment in dB for this track in the bundle'
    )

    class Meta:
        db_table = 'bundle_tracks'
        ordering = ['order_index']
        unique_together = ('bundle', 'track')

    def __str__(self):
        return f"{self.bundle.title} - {self.track.title} (#{self.order_index})"


class Playlist(models.Model):
    """
    An ordered playlist of tracks.
    Can be exported as a single concatenated audio file.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='playlists'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'playlists'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def track_count(self):
        return self.playlist_tracks.count()

    @property
    def total_duration(self):
        """Sum of all track durations in seconds."""
        total = sum(
            pt.track.duration or 0
            for pt in self.playlist_tracks.select_related('track').all()
        )
        return round(total, 2)


class PlaylistTrack(models.Model):
    """Junction table linking tracks to playlists with ordering."""
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name='playlist_tracks'
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name='playlist_entries'
    )
    order_index = models.IntegerField(default=0)

    class Meta:
        db_table = 'playlist_tracks'
        ordering = ['order_index']
        unique_together = ('playlist', 'track')

    def __str__(self):
        return f"{self.playlist.title} - {self.track.title} (#{self.order_index})"
