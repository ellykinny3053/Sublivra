import os
import uuid
import shutil
import tempfile
import subprocess
import logging

from pydub import AudioSegment
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_ffmpeg_path():
    """Find the best available ffmpeg binary across Docker/Linux/Windows."""
    sys_ffmpeg = shutil.which('ffmpeg')
    if sys_ffmpeg and os.path.exists(sys_ffmpeg):
        return sys_ffmpeg
    for p in ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/bin/ffmpeg']:
        if os.path.exists(p):
            return p
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    return None


ffmpeg_bin = _get_ffmpeg_path()
if ffmpeg_bin:
    AudioSegment.converter = ffmpeg_bin
    AudioSegment.ffmpeg = ffmpeg_bin


def _get_audio_duration(file_path):
    """Accurately extract duration in seconds from audio file without decoding into RAM."""
    try:
        import mutagen
        f = mutagen.File(file_path)
        if f and f.info and hasattr(f.info, 'length'):
            return float(f.info.length)
    except Exception:
        pass

    try:
        from pydub.utils import mediainfo
        info = mediainfo(file_path)
        if 'duration' in info:
            return float(info['duration'])
    except Exception:
        pass

    return 0.0


def mix_tracks(track_configs, loop_shorter=False):
    """
    Mix multiple audio tracks together (overlay).

    Args:
        track_configs: List of dicts, each with:
            - 'file_path': Path to audio file (absolute or relative)
            - 'volume': Volume adjustment in dB (e.g., 0 = unchanged, -5 = quieter, +3 = louder)
            - 'offset_ms': Start offset in milliseconds (default 0)
        loop_shorter: If True, loop shorter tracks to match the longest one.

    Returns:
        dict with 'file_path', 'duration', 'file_size', 'format'.
    """
    if not track_configs or len(track_configs) < 2:
        raise ValueError("At least 2 tracks are required for mixing.")

    # Load all tracks and apply volume adjustments
    loaded_tracks = []
    max_duration = 0

    for config in track_configs:
        file_path = config['file_path']
        volume_db = config.get('volume', 0)
        offset_ms = config.get('offset_ms', 0)

        full_path = file_path if os.path.isabs(file_path) else os.path.join(settings.MEDIA_ROOT, file_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Audio file not found: {full_path}")

        ext = os.path.splitext(full_path)[1].replace('.', '').lower() or 'mp3'
        audio = AudioSegment.from_file(full_path, format=ext)

        # Apply volume adjustment
        if volume_db != 0:
            audio = audio + volume_db

        total_len = len(audio) + offset_ms
        if total_len > max_duration:
            max_duration = total_len

        loaded_tracks.append({
            'audio': audio,
            'offset_ms': offset_ms,
        })

    # Create a silent base track of the maximum duration
    mixed = AudioSegment.silent(duration=max_duration)

    # Overlay each track
    for track_info in loaded_tracks:
        audio = track_info['audio']
        offset = track_info['offset_ms']

        if loop_shorter and len(audio) + offset < max_duration:
            needed_duration = max_duration - offset
            loops_needed = (needed_duration // len(audio)) + 1
            audio = audio * loops_needed
            audio = audio[:needed_duration]

        mixed = mixed.overlay(audio, position=offset)

    # Export
    output_dir = os.path.join(settings.MEDIA_ROOT, settings.AUDIO_SETTINGS['MIXED_OUTPUT_DIR'])
    os.makedirs(output_dir, exist_ok=True)

    filename = f"mixed_{uuid.uuid4().hex[:12]}.mp3"
    full_path = os.path.join(output_dir, filename)
    relative_path = os.path.join(settings.AUDIO_SETTINGS['MIXED_OUTPUT_DIR'], filename).replace('\\', '/')

    bitrate = settings.AUDIO_SETTINGS.get('DEFAULT_EXPORT_BITRATE', '192k')
    mixed.export(full_path, format='mp3', bitrate=bitrate)

    duration = len(mixed) / 1000.0
    file_size = os.path.getsize(full_path)

    return {
        'file_path': relative_path,
        'duration': round(duration, 2),
        'file_size': file_size,
        'format': 'mp3',
    }


def concatenate_tracks(file_paths, crossfade_ms=0):
    """
    Concatenate multiple audio tracks sequentially into a single file.
    Used for playlist export.

    Args:
        file_paths: List of file paths (absolute or relative to MEDIA_ROOT) in order.
        crossfade_ms: Optional crossfade duration between tracks (ms).

    Returns:
        dict with 'file_path', 'duration', 'file_size', 'format'.
    """
    if not file_paths:
        raise ValueError("At least one track is required.")

    valid_paths = []
    for fp in file_paths:
        full_path = fp if os.path.isabs(fp) else os.path.join(settings.MEDIA_ROOT, fp)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Audio file not found: {full_path}")
        valid_paths.append(full_path)

    output_dir = os.path.join(settings.MEDIA_ROOT, settings.AUDIO_SETTINGS['EXPORT_OUTPUT_DIR'])
    os.makedirs(output_dir, exist_ok=True)

    filename = f"concat_{uuid.uuid4().hex[:12]}.mp3"
    full_path = os.path.join(output_dir, filename)
    relative_path = os.path.join(settings.AUDIO_SETTINGS['EXPORT_OUTPUT_DIR'], filename).replace('\\', '/')
    bitrate = settings.AUDIO_SETTINGS.get('DEFAULT_EXPORT_BITRATE', '192k')

    # Single track: directly export/copy
    if len(valid_paths) == 1:
        ext = os.path.splitext(valid_paths[0])[1].replace('.', '').lower() or 'mp3'
        audio = AudioSegment.from_file(valid_paths[0], format=ext)
        audio.export(full_path, format='mp3', bitrate=bitrate)
        duration = len(audio) / 1000.0
        file_size = os.path.getsize(full_path)
        return {
            'file_path': relative_path,
            'duration': round(duration, 2),
            'file_size': file_size,
            'format': 'mp3',
        }

    # High-Performance FFmpeg Concat Demuxer Path (when crossfade_ms == 0):
    # Extremely fast (seconds vs minutes) and doesn't exhaust RAM on long playlists (e.g. 19 tracks / 48 mins)
    ffmpeg_exe = _get_ffmpeg_path()
    if crossfade_ms == 0 and ffmpeg_exe:
        concat_list_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                for vp in valid_paths:
                    escaped_path = os.path.abspath(vp).replace('\\', '/').replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
                concat_list_path = f.name

            cmd = [
                ffmpeg_exe,
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list_path,
                '-c:a', 'libmp3lame',
                '-b:a', bitrate,
                '-ar', '44100',
                '-ac', '2',
                full_path
            ]
            logger.info(f"Running high-performance FFmpeg concat for {len(valid_paths)} tracks...")
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

            if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                file_size = os.path.getsize(full_path)
                duration = _get_audio_duration(full_path)
                return {
                    'file_path': relative_path,
                    'duration': round(duration, 2),
                    'file_size': file_size,
                    'format': 'mp3',
                }
        except Exception as e:
            logger.warning(f"FFmpeg concat demuxer failed, falling back to pydub concat: {e}")
        finally:
            if concat_list_path and os.path.exists(concat_list_path):
                try:
                    os.remove(concat_list_path)
                except Exception:
                    pass

    # Fallback / Crossfade Pydub Path
    logger.info(f"Concatenating {len(valid_paths)} tracks with pydub (crossfade={crossfade_ms}ms)...")
    segments = []
    for vp in valid_paths:
        ext = os.path.splitext(vp)[1].replace('.', '').lower() or 'mp3'
        segments.append(AudioSegment.from_file(vp, format=ext))

    result = segments[0]
    for seg in segments[1:]:
        if crossfade_ms > 0 and crossfade_ms < min(len(result), len(seg)):
            result = result.append(seg, crossfade=crossfade_ms)
        else:
            result = result + seg

    result.export(full_path, format='mp3', bitrate=bitrate)
    duration = len(result) / 1000.0
    file_size = os.path.getsize(full_path)

    return {
        'file_path': relative_path,
        'duration': round(duration, 2),
        'file_size': file_size,
        'format': 'mp3',
    }
