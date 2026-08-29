from django.contrib import admin
from .models import Track, Tag, YouTubeImport


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'source_type', 'duration', 'format', 'created_at')
    list_filter = ('source_type', 'format', 'rights_confirmed')
    search_fields = ('title', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(YouTubeImport)
class YouTubeImportAdmin(admin.ModelAdmin):
    list_display = ('title', 'video_id', 'channel_name', 'rights_confirmed', 'created_at')
    list_filter = ('rights_confirmed',)
    search_fields = ('title', 'video_id', 'channel_name')
