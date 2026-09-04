import os
import time
import shutil
import logging
from django.conf import settings
from tracks.models import Track

logger = logging.getLogger(__name__)


def resolve_track_file_path(track, auto_heal=True):
    """
    Given a Track instance, resolve its physical file path on disk.
    Supports local storage, S3/R2 remote storage, and auto-healing from YouTube / TTS.

    Returns:
        str: Absolute path to the valid audio file on disk.

    Raises:
        FileNotFoundError: If the audio file cannot be found or reconstructed.
    """
    if not track:
        raise ValueError("Track cannot be None")

    file_name = track.file.name if hasattr(track.file, 'name') else str(track.file or '')
    clean_name = file_name.replace('\\', '/').lstrip('/')

    # 1. Check local candidates on disk
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

    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
            return candidate

    # 2. Check remote storage (S3 / R2 / Cloud Storage)
    if hasattr(track, 'file') and track.file:
        try:
            if hasattr(track.file, 'storage') and track.file.name:
                if track.file.storage.exists(track.file.name):
                    local_dest = os.path.join(settings.MEDIA_ROOT, clean_name)
                    os.makedirs(os.path.dirname(local_dest), exist_ok=True)
                    if not os.path.isfile(local_dest) or os.path.getsize(local_dest) == 0:
                        logger.info(f"Caching track {track.id} from remote storage to {local_dest}")
                        with track.file.open('rb') as src, open(local_dest, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                    if os.path.isfile(local_dest) and os.path.getsize(local_dest) > 0:
                        return local_dest
        except Exception as e:
            logger.debug(f"Storage backend check for track {track.id}: {e}")

    # 3. Self-healing if missing on disk
    if auto_heal:
        source_url = getattr(track, 'source_url', '') or ''
        if not source_url:
            try:
                from tracks.models import YouTubeImport
                yt_imp = YouTubeImport.objects.filter(track_id=track.id).first()
                if yt_imp:
                    source_url = yt_imp.youtube_url or (f"https://www.youtube.com/watch?v={yt_imp.video_id}" if yt_imp.video_id else '')
            except Exception as e:
                logger.warning(f"YouTubeImport lookup failed for track {track.id}: {e}")

        if source_url and not source_url.startswith('http'):
            source_url = f"https://www.youtube.com/watch?v={source_url.strip()}"

        is_youtube = (
            track.source_type == Track.SourceType.YOUTUBE_AUTHORIZED
            or (source_url and ('youtube.com' in source_url or 'youtu.be' in source_url))
        )

        if source_url and is_youtube:
            logger.info(f"Self-healing: Re-downloading missing YouTube audio for track '{track.title}' (ID {track.id}) from {source_url}")
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
                    if os.path.isfile(cp) and os.path.getsize(cp) > 0:
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
                if os.path.isfile(check_path) and os.path.getsize(check_path) > 0:
                    return check_path
            except Exception as e:
                logger.warning(f"Failed to auto-heal TTS track '{track.title}' (ID {track.id}): {e}")
                raise FileNotFoundError(f"Missing audio for track '{track.title}' and could not re-generate: {str(e)}")

    raise FileNotFoundError(f"Audio file for track '{track.title}' (ID {track.id}) not found on server.")


def resolve_tracks_files(tracks, auto_heal=True, allow_skip=True, max_workers=5):
    """
    Resolve and self-heal a list of tracks in sequence.
    Uses concurrent ThreadPoolExecutor for missing files so multiple tracks heal in parallel
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
            if path and os.path.isfile(path) and os.path.getsize(path) > 0:
                path_map[t.id] = path
                continue
        except FileNotFoundError:
            pass
        missing_tracks.append(t)

    # Phase 2: Concurrent auto-heal for any tracks not already on disk
    if auto_heal and missing_tracks:
        logger.info(f"Auto-healing {len(missing_tracks)} missing audio tracks concurrently (workers={max_workers})...")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def heal_single_track(track_id):
            from django.db import close_old_connections
            close_old_connections()
            try:
                from tracks.models import Track
                t = Track.objects.get(id=track_id)
                path = resolve_track_file_path(t, auto_heal=True)
                if path and os.path.isfile(path) and os.path.getsize(path) > 0:
                    return track_id, path, None
                return track_id, None, "File not found after healing"
            except Exception as e:
                logger.warning(f"Auto-heal failed for track ID {track_id}: {e}")
                return track_id, None, str(e)
            finally:
                close_old_connections()

        workers = min(len(missing_tracks), max_workers)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_track = {executor.submit(heal_single_track, t.id): t for t in missing_tracks}
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


