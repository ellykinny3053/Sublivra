"""
YouTube import service using yt-dlp.
Handles URL validation, metadata extraction, and audio download
with mandatory rights confirmation.
"""
import os
import re
import shutil
import uuid

import yt_dlp
from django.conf import settings


def _get_ffmpeg_path():
    """
    Find ffmpeg executable path across Linux/Docker/Windows environments.
    Prioritizes system PATH (/usr/bin/ffmpeg) and falls back to imageio-ffmpeg binary.
    """
    # 1. System PATH
    sys_ffmpeg = shutil.which('ffmpeg')
    if sys_ffmpeg and os.path.exists(sys_ffmpeg):
        return sys_ffmpeg

    # 2. Standard Linux / Docker binary locations
    for path in ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/bin/ffmpeg']:
        if os.path.exists(path):
            return path

    # 3. imageio_ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    return None


# Regex patterns for valid YouTube URLs
YOUTUBE_URL_PATTERNS = [
    r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
]


def validate_youtube_url(url):
    """
    Validate a YouTube URL and extract the video ID.

    Args:
        url: The YouTube URL to validate.

    Returns:
        str: The video ID.

    Raises:
        ValueError: If the URL is not a valid YouTube URL.
    """
    if not url or not url.strip():
        raise ValueError("URL cannot be empty.")

    for pattern in YOUTUBE_URL_PATTERNS:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)

    raise ValueError(
        "Invalid YouTube URL. Please provide a valid YouTube video link "
        "(e.g., https://www.youtube.com/watch?v=VIDEO_ID)"
    )


def _get_base_ydl_opts(extra_opts=None):
    """
    Build resilient yt-dlp options with multi-client fallbacks (Android/iOS/MWeb)
    to prevent cloud datacenter IP bot blocks.
    """
    opts = {
        'quiet': True,
        'no_warnings': True,
        'no_color': True,
        'socket_timeout': 30,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb', 'web'],
            }
        },
    }

    # Optional cookies authentication via environment variable
    cookies_content = os.getenv('YOUTUBE_COOKIES_CONTENT', '').strip()
    cookies_file = os.getenv('YOUTUBE_COOKIES_FILE', '').strip()

    if cookies_content:
        import tempfile
        cookie_path = os.path.join(tempfile.gettempdir(), 'sublivra_yt_cookies.txt')
        try:
            with open(cookie_path, 'w', encoding='utf-8') as f:
                f.write(cookies_content)
            opts['cookiefile'] = cookie_path
        except Exception:
            pass
    elif cookies_file and os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file

    if extra_opts:
        opts.update(extra_opts)

    return opts


def get_video_metadata(url):
    """
    Fetch metadata for a YouTube video without downloading it.

    Args:
        url: A valid YouTube URL.

    Returns:
        dict with video metadata:
            - video_id, title, channel_name, thumbnail_url
            - duration (seconds), description, view_count
    """
    video_id = validate_youtube_url(url)

    ydl_opts = _get_base_ydl_opts({
        'skip_download': True,
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                'video_id': video_id,
                'title': info.get('title', 'Unknown'),
                'channel_name': info.get('uploader', info.get('channel', 'Unknown')),
                'thumbnail_url': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'description': (info.get('description', '') or '')[:500],
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date', ''),
            }
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if 'private' in error_msg:
            raise ValueError("This video is private and cannot be accessed.")
        elif 'unavailable' in error_msg or 'not available' in error_msg:
            raise ValueError("This video is unavailable.")
        elif 'age' in error_msg:
            raise ValueError("This video requires age verification and cannot be imported.")
        else:
            raise ValueError(f"Could not fetch video metadata: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve video metadata: {str(e)}")


def download_audio(url):
    """
    Download audio from a YouTube video and convert to MP3.

    Args:
        url: A valid YouTube URL.

    Returns:
        dict with:
            - file_path: Relative path to the downloaded audio file.
            - duration: Audio duration in seconds.
            - file_size: File size in bytes.
            - format: Audio format (mp3).

    Raises:
        ValueError: If URL is invalid.
        RuntimeError: If download fails.
    """
    validate_youtube_url(url)

    # Create output directory
    output_dir = os.path.join(settings.MEDIA_ROOT, settings.AUDIO_SETTINGS['YOUTUBE_OUTPUT_DIR'])
    os.makedirs(output_dir, exist_ok=True)

    filename = f"yt_{uuid.uuid4().hex[:12]}"
    output_template = os.path.join(output_dir, filename)

    ffmpeg_exe = _get_ffmpeg_path()

    extra_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template + '.%(ext)s',
        'retries': 3,
        'max_filesize': 100 * 1024 * 1024,  # 100MB max
    }
    if ffmpeg_exe:
        extra_opts['ffmpeg_location'] = ffmpeg_exe
        extra_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    ydl_opts = _get_base_ydl_opts(extra_opts)

    try:
        # Extract info dict during download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Find the output file (yt-dlp adds the extension)
        output_file = output_template + '.mp3'
        if not os.path.exists(output_file):
            for ext in ['.mp3', '.m4a', '.webm', '.ogg', '.wav']:
                candidate = output_template + ext
                if os.path.exists(candidate):
                    output_file = candidate
                    break

        if not os.path.exists(output_file):
            raise RuntimeError("Download completed but output file not found.")

        duration = info.get('duration', 0)
        file_size = os.path.getsize(output_file)

        relative_path = os.path.join(
            settings.AUDIO_SETTINGS['YOUTUBE_OUTPUT_DIR'],
            os.path.basename(output_file)
        )

        return {
            'file_path': relative_path,
            'duration': round(float(duration), 2) if duration else 0.0,
            'file_size': file_size,
            'format': 'mp3',
        }

    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(
            f"Could not download audio. This video may not have an authorized "
            f"download mechanism available. Error: {str(e)}"
        )
    except Exception as e:
        # Clean up partial downloads
        for ext in ['.mp3', '.m4a', '.webm', '.ogg', '.wav', '.part', '.ytdl']:
            candidate = output_template + ext
            if os.path.exists(candidate):
                os.remove(candidate)
        raise RuntimeError(f"Audio download failed: {str(e)}")
