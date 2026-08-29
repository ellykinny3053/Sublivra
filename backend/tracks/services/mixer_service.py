import os
import uuid

from pydub import AudioSegment
from django.conf import settings

try:
    import imageio_ffmpeg
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    AudioSegment.converter = ffmpeg_bin
    AudioSegment.ffmpeg = ffmpeg_bin
except Exception:
    pass


def mix_tracks(track_configs, loop_shorter=False):
    """
    Mix multiple audio tracks together (overlay).

    Args:
        track_configs: List of dicts, each with:
            - 'file_path': Relative path to audio file
            - 'volume': Volume adjustment in dB (e.g., 0 = unchanged, -5 = quieter, +3 = louder)
            - 'offset_ms': Start offset in milliseconds (default 0)
        loop_shorter: If True, loop shorter tracks to match the longest one.

    Returns:
        dict with 'file_path', 'duration', 'file_size'.
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

        full_path = os.path.join(settings.MEDIA_ROOT, file_path) if not os.path.isabs(file_path) else file_path
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
            # Loop the shorter track to fill the gap
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
    relative_path = os.path.join(settings.AUDIO_SETTINGS['MIXED_OUTPUT_DIR'], filename)

    mixed.export(full_path, format='mp3', bitrate=settings.AUDIO_SETTINGS['DEFAULT_EXPORT_BITRATE'])

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
        file_paths: List of relative file paths in order.
        crossfade_ms: Optional crossfade duration between tracks (ms).

    Returns:
        dict with 'file_path', 'duration', 'file_size'.
    """
    if not file_paths:
        raise ValueError("At least one track is required.")

    segments = []
    for fp in file_paths:
        full_path = os.path.join(settings.MEDIA_ROOT, fp) if not os.path.isabs(fp) else fp
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Audio file not found: {full_path}")
        ext = os.path.splitext(full_path)[1].replace('.', '').lower() or 'mp3'
        segments.append(AudioSegment.from_file(full_path, format=ext))

    # Concatenate with optional crossfade
    result = segments[0]
    for seg in segments[1:]:
        if crossfade_ms > 0 and crossfade_ms < min(len(result), len(seg)):
            result = result.append(seg, crossfade=crossfade_ms)
        else:
            result = result + seg

    # Export
    output_dir = os.path.join(settings.MEDIA_ROOT, settings.AUDIO_SETTINGS['EXPORT_OUTPUT_DIR'])
    os.makedirs(output_dir, exist_ok=True)

    filename = f"concat_{uuid.uuid4().hex[:12]}.mp3"
    full_path = os.path.join(output_dir, filename)
    relative_path = os.path.join(settings.AUDIO_SETTINGS['EXPORT_OUTPUT_DIR'], filename)

    result.export(full_path, format='mp3', bitrate=settings.AUDIO_SETTINGS['DEFAULT_EXPORT_BITRATE'])

    duration = len(result) / 1000.0
    file_size = os.path.getsize(full_path)

    return {
        'file_path': relative_path,
        'duration': round(duration, 2),
        'file_size': file_size,
        'format': 'mp3',
    }
