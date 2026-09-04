"""
Service for resolving and self-healing track audio file paths across environments.
Handles cross-platform paths, Railway ephemeral storage recovery, and parallel resolution.
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    # Check candidates
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
                logger.error(f"Failed to auto-heal YouTube track '{track.title}': {e}")
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
                logger.error(f"Failed to auto-heal TTS track '{track.title}': {e}")
                raise FileNotFoundError(f"Missing audio for track '{track.title}' and could not re-generate: {str(e)}")

    raise FileNotFoundError(f"Audio file for track '{track.title}' (ID {track.id}) not found on server.")


def resolve_tracks_files(tracks, max_workers=4, auto_heal=True):
    """
    Resolve and self-heal a list of tracks in order, downloading missing tracks in parallel.
    Maintains the exact original track sequence ordering in the returned list of file paths.

    Args:
        tracks: List of Track model instances.
        max_workers: Maximum threads for concurrent downloads.
        auto_heal: Whether to re-download/re-generate missing files.

    Returns:
        list[str]: Absolute file paths in the exact order of `tracks`.
    """
    if not tracks:
        return []

    results = {}
    missing_items = []

    # First pass: check what's already on disk synchronously (fast, 0ms)
    for idx, t in enumerate(tracks):
        try:
            path = resolve_track_file_path(t, auto_heal=False)
            results[idx] = path
        except FileNotFoundError:
            missing_items.append((idx, t))

    # Second pass: download missing tracks concurrently
    if missing_items and auto_heal:
        logger.info(f"Resolving {len(missing_items)} missing track files concurrently (workers={max_workers})...")
        worker_count = min(max_workers, len(missing_items))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_idx = {
                executor.submit(resolve_track_file_path, t, True): idx
                for idx, t in missing_items
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                path = future.result()  # Will raise if download failed
                results[idx] = path

    return [results[i] for i in range(len(tracks))]
