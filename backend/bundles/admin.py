from django.contrib import admin
from .models import Bundle, BundleTrack, Playlist, PlaylistTrack


class BundleTrackInline(admin.TabularInline):
    model = BundleTrack
    extra = 0


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'track_count', 'created_at')
    search_fields = ('title', 'user__email')
    inlines = [BundleTrackInline]


class PlaylistTrackInline(admin.TabularInline):
    model = PlaylistTrack
    extra = 0


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'track_count', 'created_at')
    search_fields = ('title', 'user__email')
    inlines = [PlaylistTrackInline]
