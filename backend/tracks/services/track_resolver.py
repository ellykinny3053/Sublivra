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
        if clean_name.startswith('media/'):
            candidates.append(os.path.join(settings.MEDIA_ROOT, clean_name[6:]))
        candidates.append(os.path.join(str(settings.BASE_DIR), clean_name))
        base = os.path.basename(clean_name)
        candidates.extend([
            os.path.join(settings.MEDIA_ROOT, 'audio', 'youtube', base),
            os.path.join(settings.MEDIA_ROOT, 'tracks', base),
            os.path.join(settings.MEDIA_ROOT, 'audio', 'tts', base),
            os.path.join(settings.MEDIA_ROOT, 'audio', 'mixed', base),
            os.path.join(settings.MEDIA_ROOT, 'audio', 'exports', base),
            os.path.join(settings.MEDIA_ROOT, 'audio', 'edited', base),
        ])
        if os.path.isabs(clean_name):
            candidates.append(clean_name)

    # Check candidate paths on disk
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate

    # Self-healing if missing on disk
    if auto_heal:
        source_url = track.source_url
        if not source_url:
            yt_imp = getattr(track, 'youtube_import', None)
            if yt_imp and hasattr(yt_imp, 'youtube_url'):
                source_url = yt_imp.youtube_url

        is_youtube = (
            track.source_type == Track.SourceType.YOUTUBE_AUTHORIZED
            or (source_url and ('youtube.com' in source_url or 'youtu.be' in source_url))
        )

        if source_url and is_youtube:
            logger.info(f"Self-healing: Re-downloading missing YouTube audio for track '{track.title}' (ID {track.id})")
            try:
                from tracks.services import youtube_service
                res = youtube_service.download_audio(source_url)
                new_file = str(res['file_path']).replace('\\', '/')
                track.file = new_file
                if not track.source_url:
                    track.source_url = source_url
                track.save(update_fields=['file', 'source_url'])

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


def resolve_tracks_files(tracks, auto_heal=True, allow_skip=True, max_workers=5):
    """
    Resolve and self-heal a list of tracks in sequence.
    Uses concurrent ThreadPoolExecutor for missing files so 10+ tracks heal in parallel
    (30-45s) instead of sequentially blocking for minutes and timing out.

    Args:
        tracks: List of Track model instances.
        auto_heal: Whether to re-download missing files.
        allow_skip: Whether to skip dead/unavailable tracks gracefully.
        max_workers: Number of concurrent download workers (default 5).

    Returns:
        tuple[list[tuple[Track, str]], list[str]]:
            - valid_items: list of (track, absolute_file_path) in original sequence order
            - skipped_tracks: list of track title strings that were unrecoverable
    """
    if not tracks:
        return [], []

    path_map = {}
    missing_tracks = []

    # Phase 1: Instant local disk check for all tracks
    for t in tracks:
        try:
            path = resolve_track_file_path(t, auto_heal=False)
            if path and os.path.isfile(path):
                path_map[t.id] = path
                continue
        except FileNotFoundError:
            pass
        missing_tracks.append(t)

    # Phase 2: Concurrent auto-heal for any tracks not already on disk
    if auto_heal and missing_tracks:
        logger.info(f"Auto-healing {len(missing_tracks)} missing audio tracks concurrently (workers={max_workers})...")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def heal_single_track(track):
            try:
                path = resolve_track_file_path(track, auto_heal=True)
                if path and os.path.isfile(path):
                    return track.id, path, None
                return track.id, None, "File not found after healing"
            except Exception as e:
                return track.id, None, str(e)

        workers = min(len(missing_tracks), max_workers)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_track = {executor.submit(heal_single_track, t): t for t in missing_tracks}
            for future in as_completed(future_to_track):
                t = future_to_track[future]
                try:
                    tid, path, err = future.result()
                    if path:
                        path_map[tid] = path
                    else:
                        logger.warning(f"Auto-heal failed for track '{t.title}': {err}")
                except Exception as exc:
                    logger.warning(f"Auto-heal raised unexpected error for '{t.title}': {exc}")

    # Phase 3: Construct valid_items preserving EXACT original playlist sequence
    valid_items = []
    skipped_tracks = []
    for t in tracks:
        if t.id in path_map:
            valid_items.append((t, path_map[t.id]))
        else:
            title = t.title or f"Track {t.id}"
            if allow_skip:
                skipped_tracks.append(title)
                logger.info(f"Skipping unrecoverable track '{title}' for export.")
            else:
                raise FileNotFoundError(f"Missing audio for track '{title}' and could not be recovered.")

    return valid_items, skipped_tracks

