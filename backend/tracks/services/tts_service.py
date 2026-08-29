"""
Text-to-Speech service supporting Open-Source Neural Voices (Edge-TTS)
with fallback to gTTS (Google Text-to-Speech).
Provides male/female voices, diverse global accents, and subliminal speed-up (up to 4.0x).
"""
import os
import uuid
import asyncio
from pathlib import Path

from django.conf import settings
from pydub import AudioSegment

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

from gtts import gTTS, lang as gtts_lang


# Curated high-fidelity neural voices (Male & Female, Diverse Accents)
NEURAL_VOICES = [
    # US English
    {'id': 'en-US-JennyNeural', 'name': 'Jenny (Natural Female)', 'gender': 'Female', 'accent': '🇺🇸 US English', 'lang': 'en'},
    {'id': 'en-US-AriaNeural', 'name': 'Aria (Warm & Meditative Female)', 'gender': 'Female', 'accent': '🇺🇸 US English', 'lang': 'en'},
    {'id': 'en-US-AvaNeural', 'name': 'Ava (Soft Female)', 'gender': 'Female', 'accent': '🇺🇸 US English', 'lang': 'en'},
    {'id': 'en-US-ChristopherNeural', 'name': 'Christopher (Deep & Confident Male)', 'gender': 'Male', 'accent': '🇺🇸 US English', 'lang': 'en'},
    {'id': 'en-US-GuyNeural', 'name': 'Guy (Calm Male)', 'gender': 'Male', 'accent': '🇺🇸 US English', 'lang': 'en'},
    {'id': 'en-US-BrianNeural', 'name': 'Brian (Strong Resonant Male)', 'gender': 'Male', 'accent': '🇺🇸 US English', 'lang': 'en'},

    # British English
    {'id': 'en-GB-SoniaNeural', 'name': 'Sonia (Crisp British Female)', 'gender': 'Female', 'accent': '🇬🇧 British English', 'lang': 'en'},
    {'id': 'en-GB-LibbyNeural', 'name': 'Libby (Gentle British Female)', 'gender': 'Female', 'accent': '🇬🇧 British English', 'lang': 'en'},
    {'id': 'en-GB-RyanNeural', 'name': 'Ryan (Calm British Male)', 'gender': 'Male', 'accent': '🇬🇧 British English', 'lang': 'en'},

    # Australian English
    {'id': 'en-AU-NatashaNeural', 'name': 'Natasha (Australian Female)', 'gender': 'Female', 'accent': '🇦🇺 Australian', 'lang': 'en'},
    {'id': 'en-AU-WilliamNeural', 'name': 'William (Australian Male)', 'gender': 'Male', 'accent': '🇦🇺 Australian', 'lang': 'en'},

    # Indian English & Hindi
    {'id': 'en-IN-NeerjaNeural', 'name': 'Neerja (Clear Indian English Female)', 'gender': 'Female', 'accent': '🇮🇳 Indian English', 'lang': 'en'},
    {'id': 'en-IN-PrabhatNeural', 'name': 'Prabhat (Grounded Indian English Male)', 'gender': 'Male', 'accent': '🇮🇳 Indian English', 'lang': 'en'},
    {'id': 'hi-IN-SwaraNeural', 'name': 'Swara (Hindi Female)', 'gender': 'Female', 'accent': '🇮🇳 Hindi', 'lang': 'hi'},
    {'id': 'hi-IN-MadhurNeural', 'name': 'Madhur (Hindi Male)', 'gender': 'Male', 'accent': '🇮🇳 Hindi', 'lang': 'hi'},

    # Canadian & Irish
    {'id': 'en-CA-ClaraNeural', 'name': 'Clara (Canadian Female)', 'gender': 'Female', 'accent': '🇨🇦 Canadian', 'lang': 'en'},
    {'id': 'en-IE-EmilyNeural', 'name': 'Emily (Irish Female)', 'gender': 'Female', 'accent': '🇮🇪 Irish', 'lang': 'en'},

    # International
    {'id': 'es-ES-ElviraNeural', 'name': 'Elvira (Spanish Female)', 'gender': 'Female', 'accent': '🇪🇸 Spanish', 'lang': 'es'},
    {'id': 'fr-FR-DeniseNeural', 'name': 'Denise (French Female)', 'gender': 'Female', 'accent': '🇫🇷 French', 'lang': 'fr'},
    {'id': 'de-DE-KatjaNeural', 'name': 'Katja (German Female)', 'gender': 'Female', 'accent': '🇩🇪 German', 'lang': 'de'},
    {'id': 'ja-JP-NanamiNeural', 'name': 'Nanami (Japanese Female)', 'gender': 'Female', 'accent': '🇯🇵 Japanese', 'lang': 'ja'},
]


def get_available_voices():
    """Return list of curated neural voices with gender and accents."""
    return NEURAL_VOICES


def get_available_languages():
    """Return dict of available TTS languages with their names."""
    try:
        languages = gtts_lang.tts_langs()
        return languages
    except Exception:
        return {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'hi': 'Hindi',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh-CN': 'Chinese (Simplified)',
            'ar': 'Arabic',
            'ru': 'Russian',
        }


async def _generate_edge_tts(text, voice, file_path, speed=1.0):
    """Generate audio using Microsoft Edge Neural TTS."""
    rate_str = "+0%"
    if speed != 1.0:
        pct = int((speed - 1.0) * 100)
        rate_str = f"+{pct}%" if pct >= 0 else f"{pct}%"

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate_str)
    await communicate.save(file_path)


def generate_tts_audio(text, language='en', voice='en-US-JennyNeural', slow=False, speed=1.0):
    """
    Generate an audio file from text using Edge-TTS or gTTS.

    Args:
        text: The affirmation/text to convert to speech.
        language: Language code (e.g., 'en', 'es', 'hi').
        voice: Neural voice ID (e.g., 'en-US-JennyNeural', 'en-US-ChristopherNeural').
        slow: Slow speed flag (for gTTS).
        speed: Playback speed multiplier (0.5 - 4.0).

    Returns:
        dict with 'file_path', 'duration', 'file_size', 'format'.
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    output_dir = os.path.join(settings.MEDIA_ROOT, settings.AUDIO_SETTINGS['TTS_OUTPUT_DIR'])
    os.makedirs(output_dir, exist_ok=True)

    filename = f"tts_{uuid.uuid4().hex[:12]}.mp3"
    file_path = os.path.join(output_dir, filename)

    success = False

    # 1. Try Neural Voice via Edge-TTS
    if HAS_EDGE_TTS and voice:
        try:
            # Run async edge-tts in event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(_generate_edge_tts(text, voice, file_path, speed=speed))
            if os.path.exists(file_path) and os.path.getsize(file_path) > 500:
                success = True
        except Exception as e:
            print(f"Edge-TTS failed ({e}), falling back to gTTS...")

    # 2. Fallback to gTTS if Edge-TTS failed or voice is empty
    if not success:
        try:
            tts = gTTS(text=text, lang=language, slow=slow)
            tts.save(file_path)

            if speed != 1.0 and 0.5 <= speed <= 4.0:
                audio = AudioSegment.from_mp3(file_path)
                new_frame_rate = int(audio.frame_rate * speed)
                modified = audio._spawn(audio.raw_data, overrides={
                    'frame_rate': new_frame_rate
                }).set_frame_rate(audio.frame_rate)
                modified.export(file_path, format='mp3', bitrate='192k')
            success = True
        except Exception as e:
            raise RuntimeError(f"TTS generation failed: {str(e)}")

    # Calculate duration
    try:
        audio = AudioSegment.from_file(file_path, format='mp3')
        duration = len(audio) / 1000.0
    except Exception:
        import mutagen.mp3
        try:
            mp3_info = mutagen.mp3.MP3(file_path)
            duration = mp3_info.info.length
        except Exception:
            duration = 5.0

    file_size = os.path.getsize(file_path)
    relative_path = os.path.join(settings.AUDIO_SETTINGS['TTS_OUTPUT_DIR'], filename)

    return {
        'file_path': relative_path,
        'duration': round(duration, 2),
        'file_size': file_size,
        'format': 'mp3',
    }
