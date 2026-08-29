import os
import uuid
import mutagen

from pydub import AudioSegment
from pydub.effects import normalize as pydub_normalize
from django.conf import settings

try:
    import imageio_ffmpeg
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    AudioSegment.converter = ffmpeg_bin
    AudioSegment.ffmpeg = ffmpeg_bin
except Exception:
    pass


def _get_output_path(prefix='edited'):
    """Generate a unique output file path in the edited directory."""
    output_dir = os.path.join(settings.MEDIA_ROOT, settings.AUDIO_SETTINGS['EDITED_OUTPUT_DIR'])
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.mp3"
    full_path = os.path.join(output_dir, filename)
    relative_path = os.path.join(settings.AUDIO_SETTINGS['EDITED_OUTPUT_DIR'], filename)
    return full_path, relative_path


def _load_audio(file_path):
    """Load an audio file into a pydub AudioSegment."""
    full_path = os.path.join(settings.MEDIA_ROOT, file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Audio file not found: {full_path}")
    ext = os.path.splitext(full_path)[1].replace('.', '').lower() or 'mp3'
    return AudioSegment.from_file(full_path, format=ext)


def _export_and_get_metadata(audio, full_path, relative_path):
    """Export audio segment and return metadata dict."""
    audio.export(full_path, format='mp3', bitrate=settings.AUDIO_SETTINGS['DEFAULT_EXPORT_BITRATE'])
    duration = len(audio) / 1000.0
    file_size = os.path.getsize(full_path)
    return {
        'file_path': relative_path,
        'duration': round(duration, 2),
        'file_size': file_size,
        'format': 'mp3',
    }


def trim_audio(file_path, start_ms=0, end_ms=None):
    """
    Trim audio to a specified time range.

    Args:
        file_path: Relative path to the source audio file.
        start_ms: Start time in milliseconds (default 0).
        end_ms: End time in milliseconds (default: end of file).

    Returns:
        dict with 'file_path', 'duration', 'file_size'.
    """
    audio = _load_audio(file_path)
    total_duration_ms = len(audio)

    if start_ms < 0:
        start_ms = 0
    if end_ms is None or end_ms > total_duration_ms:
        end_ms = total_duration_ms
    if start_ms >= end_ms:
        raise ValueError(f"start_ms ({start_ms}) must be less than end_ms ({end_ms})")

    trimmed = audio[start_ms:end_ms]
    full_path, relative_path = _get_output_path('trimmed')
    return _export_and_get_metadata(trimmed, full_path, relative_path)


def change_speed(file_path, speed=1.0):
    """
    Change audio playback speed.

    Args:
        file_path: Relative path to the source audio file.
        speed: Speed multiplier (0.5 = half speed, 2.0 = double speed).

    Returns:
        dict with 'file_path', 'duration', 'file_size'.
    """
    if not 0.25 <= speed <= 4.0:
        raise ValueError(f"Speed must be between 0.25 and 4.0, got {speed}")

    audio = _load_audio(file_path)

    # Change speed by modifying frame rate
    new_frame_rate = int(audio.frame_rate * speed)
    modified = audio._spawn(audio.raw_data, overrides={
        'frame_rate': new_frame_rate
    }).set_frame_rate(audio.frame_rate)

    full_path, relative_path = _get_output_path('speed')
    return _export_and_get_metadata(modified, full_path, relative_path)


def apply_fade(file_path, fade_in_ms=0, fade_out_ms=0):
    """
    Apply fade in and/or fade out to audio.

    Args:
        file_path: Relative path to the source audio file.
        fade_in_ms: Fade-in duration in milliseconds.
        fade_out_ms: Fade-out duration in milliseconds.

    Returns:
        dict with 'file_path', 'duration', 'file_size'.
    """
    audio = _load_audio(file_path)
    total_duration = len(audio)

    if fade_in_ms < 0 or fade_out_ms < 0:
        raise ValueError("Fade durations cannot be negative")
    if fade_in_ms + fade_out_ms > total_duration:
        raise ValueError("Combined fade durations exceed audio length")

    if fade_in_ms > 0:
        audio = audio.fade_in(fade_in_ms)
    if fade_out_ms > 0:
        audio = audio.fade_out(fade_out_ms)

    full_path, relative_path = _get_output_path('faded')
    return _export_and_get_metadata(audio, full_path, relative_path)


def normalize_volume(file_path, target_dbfs=-20.0):
    """
    Normalize audio volume to a target dBFS level.

    Args:
        file_path: Relative path to the source audio file.
        target_dbfs: Target volume in dBFS (default -20.0).

    Returns:
        dict with 'file_path', 'duration', 'file_size'.
    """
    audio = _load_audio(file_path)

    # Use pydub's normalize (normalizes to 0 dBFS peak)
    # Then adjust to target level
    normalized = pydub_normalize(audio)

    # Adjust to target dBFS
    current_dbfs = normalized.dBFS
    if current_dbfs != float('-inf'):
        change_in_dbfs = target_dbfs - current_dbfs
        normalized = normalized + change_in_dbfs

    full_path, relative_path = _get_output_path('normalized')
    return _export_and_get_metadata(normalized, full_path, relative_path)


def get_audio_info(file_path):
    """
    Get metadata about an audio file.

    Returns:
        dict with 'duration', 'file_size', 'channels', 'sample_rate', 'dbfs'.
    """
    audio = _load_audio(file_path)
    full_path = os.path.join(settings.MEDIA_ROOT, file_path) if not os.path.isabs(file_path) else file_path

    return {
        'duration': round(len(audio) / 1000.0, 2),
        'file_size': os.path.getsize(full_path),
        'channels': audio.channels,
        'sample_rate': audio.frame_rate,
        'dbfs': round(audio.dBFS, 2) if audio.dBFS != float('-inf') else None,
        'duration_ms': len(audio),
    }
