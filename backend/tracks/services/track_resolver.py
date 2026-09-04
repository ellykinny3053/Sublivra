"""
Service for resolving and self-healing track audio file paths across environments.
Handles cross-platform paths, Railway ephemeral storage recovery, and graceful skipping of dead/unavailable tracks.
"""
import os
import time
import logging
from django.conf import settings
from tracks.models import Track

logger = logging.getLogger(__name__)


def resolve_track_file_path(track, auto_heal=True):
    """
    Given a Track instance, resolve its physical file path on disk.
    If the file is missing (e.g. wiped due to Railway container restart/redeploy),
    automatically self-heal by re-downloading from YouTube or re-generating TTS if possible.

    Returns:
        str: Absolute path to the valid audio file on disk.

    Raises:
        FileNotFoundError: If the audio file cannot be found or reconstructed.
    """
    if not track:
        raise ValueError("Track cannot be None")

    file_name = track.file.name if hasattr(track.file, 'name') else str(track.file or '')
    clean_name = file_name.replace('\\', '/').lstrip('/')

    candidates = []
    if clean_name:
        candidates.append(os.path.join(settings.MEDIA_ROOT, clean_name))
        candidates.append(os.path.join(settings.MEDIA_ROOT, file_name))
        base = os.path.basename(clean_name)
        candidates.extend([
            os.path.join(settings.MEDIA_ROOT, 'audio', 'youtube', base),
            os.path.join(settings.MEDIA_ROOT, 'tracks', base),
            os.path.join(settings.MEDIA_ROOT, 'audio', 'tts', base),
            os.path.join(settings.MEDIA_ROOT, 'audio', 'mixed', base),
            os.path.join(settings.MEDIA_ROOT, 'audio', 'exports', base),
        ])
        if os.path.isabs(clean_name):
            candidates.append(clean_name)

    # Check candidate paths on disk
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate

    # Self-healing if missing on disk
    if auto_heal:
        if track.source_url and track.source_type == Track.SourceType.YOUTUBE_AUTHORIZED:
            logger.info(f"Self-healing: Re-downloading missing YouTube audio for track '{track.title}' (ID {track.id})")
            try:
                from tracks.services import youtube_service
                res = youtube_service.download_audio(track.source_url)
                new_file = str(res['file_path']).replace('\\', '/')
                track.file = new_file
                track.save(update_fields=['file'])

                check_paths = [
                    os.path.join(settings.MEDIA_ROOT, new_file),
                    os.path.join(settings.MEDIA_ROOT, 'audio', 'youtube', os.path.basename(new_file))
                ]
                for cp in check_paths:
                    if os.path.isfile(cp):
                        return cp
            except Exception as e:
                logger.warning(f"Failed to auto-heal YouTube track '{track.title}' (ID {track.id}): {e}")
                raise FileNotFoundError(f"Missing audio for track '{track.title}' and could not re-download: {str(e)}")

        elif track.source_type == Track.SourceType.TTS and track.tts_text:
            logger.info(f"Self-healing: Re-generating missing TTS audio for track '{track.title}' (ID {track.id})")
            try:
                from tracks.services import tts_service
                res = tts_service.generate_tts_audio(
                    text=track.tts_text,
                    language=track.tts_language or 'en'
                )
                new_file = str(res['file_path']).replace('\\', '/')
                track.file = new_file
                track.save(update_fields=['file'])

                check_path = os.path.join(settings.MEDIA_ROOT, new_file)
                if os.path.isfile(check_path):
                    return check_path
            except Exception as e:
                logger.warning(f"Failed to auto-heal TTS track '{track.title}' (ID {track.id}): {e}")
                raise FileNotFoundError(f"Missing audio for track '{track.title}' and could not re-generate: {str(e)}")

    raise FileNotFoundError(f"Audio file for track '{track.title}' (ID {track.id}) not found on server.")


def resolve_tracks_files(tracks, auto_heal=True, allow_skip=True):
    """
    Resolve and self-heal a list of tracks in sequence.
    If an individual track cannot be recovered (e.g. YouTube video was removed/private),
    allow_skip=True records it in skipped_tracks rather than aborting the entire export.

    Args:
        tracks: List of Track model instances.
        auto_heal: Whether to re-download missing files.
        allow_skip: Whether to skip dead/unavailable tracks gracefully.

    Returns:
        tuple[list[tuple[Track, str]], list[str]]:
            - valid_items: list of (track, absolute_file_path)
            - skipped_tracks: list of track title strings that were unrecoverable
    """
    if not tracks:
        return [], []

    valid_items = []
    skipped_tracks = []

    for t in tracks:
        # 1. Fast check: is file already on disk?
        try:
            path = resolve_track_file_path(t, auto_heal=False)
            if path and os.path.isfile(path):
                valid_items.append((t, path))
                continue
        except FileNotFoundError:
            pass

        # 2. Re-download / regenerate if auto_heal enabled
        if auto_heal:
            try:
                path = resolve_track_file_path(t, auto_heal=True)
                if path and os.path.isfile(path):
                    valid_items.append((t, path))
                    # Brief pause between YouTube downloads to avoid cloud IP rate limiting
                    if t.source_type == Track.SourceType.YOUTUBE_AUTHORIZED:
                        time.sleep(0.3)
                    continue
            except Exception as e:
                logger.warning(f"Track '{t.title}' could not be resolved: {e}")

        # 3. Track could not be found or downloaded
        title = t.title or f"Track {t.id}"
        if allow_skip:
            skipped_tracks.append(title)
            logger.info(f"Skipping unrecoverable track '{title}' for export.")
        else:
            raise FileNotFoundError(f"Missing audio for track '{title}' and could not be recovered.")

    return valid_items, skipped_tracks
