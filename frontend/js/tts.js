/**
 * "Make Your Own Sub" Module (Subliminal Creator Studio)
 * Features:
 * 1. Background Music: Import from YouTube, Upload from Device, or Pick from Library
 * 2. Affirmations: Neural TTS Voices (Male/Female, US/UK/IN/AU/etc. Accents), Speedup (up to 4.0x), Volume
 * 3. Real-Time Multi-Layer Synchronized Preview
 * 4. Master Mixing & 1-Click Complete Subliminal Download
 */

class MakeYourSubManager {
  constructor() {
    this.selectedBackgroundTrack = null;
    this.generatedAffirmationTrack = null;
    this.audioContext = null;
    this.bgSourceNode = null;
    this.affSourceNode = null;
    this.bgGainNode = null;
    this.affGainNode = null;
    this.bgAudio = null;
    this.affAudio = null;
    this.isPlayingPreview = false;
    this.previewTimer = null;
    this.init();
  }

  init() {
    this.bindEvents();
    this.loadVoicesAndLanguages();
  }

  bindEvents() {
    // Tab switching for Background Track source (YouTube / Upload / Library)
    const bgSourceBtns = document.querySelectorAll('.mys-bg-tab-btn');
    bgSourceBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        bgSourceBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const target = btn.dataset.target;
        document.querySelectorAll('.mys-bg-pane').forEach(p => p.style.display = 'none');
        const pane = document.getElementById(target);
        if (pane) pane.style.display = 'block';
      });
    });

    // YouTube Import in Make Your Own Sub
    const ytImportBtn = document.getElementById('mys-yt-import-btn');
    if (ytImportBtn) {
      ytImportBtn.addEventListener('click', () => this.handleYouTubeImport());
    }

    // Device Upload in Make Your Own Sub
    const uploadInput = document.getElementById('mys-upload-file');
    if (uploadInput) {
      uploadInput.addEventListener('change', () => this.handleDeviceUpload());
    }

    // Library Track Select in Make Your Own Sub
    const librarySelect = document.getElementById('mys-library-select');
    if (librarySelect) {
      librarySelect.addEventListener('change', (e) => this.handleLibrarySelect(e.target.value));
    }

    // Affirmations Form Submit (Generate Voice)
    const affForm = document.getElementById('mys-affirmation-form');
    if (affForm) {
      affForm.addEventListener('submit', (e) => this.handleGenerateAffirmations(e));
    }

    // Speed Slider listener
    const speedSlider = document.getElementById('mys-speed-slider');
    const speedVal = document.getElementById('mys-speed-val');
    const speedPresets = document.querySelectorAll('.mys-speed-chip');

    const updateActiveSpeedChip = (val) => {
      speedPresets.forEach(chip => {
        if (Math.abs(parseFloat(chip.dataset.speed) - val) < 0.05) {
          chip.classList.add('active');
        } else {
          chip.classList.remove('active');
        }
      });
    };

    if (speedSlider && speedVal) {
      speedSlider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        speedVal.textContent = `${val.toFixed(1)}x`;
        updateActiveSpeedChip(val);
      });
    }

    // Speed Preset Chips
    speedPresets.forEach(chip => {
      chip.addEventListener('click', () => {
        const val = parseFloat(chip.dataset.speed);
        if (speedSlider) {
          speedSlider.value = val;
          speedVal.textContent = `${val.toFixed(1)}x`;
          updateActiveSpeedChip(val);
        }
      });
    });

    // Synchronized Live Preview Controls
    const previewPlayBtn = document.getElementById('mys-preview-play-btn');
    const previewStopBtn = document.getElementById('mys-preview-stop-btn');
    if (previewPlayBtn) {
      previewPlayBtn.addEventListener('click', () => this.toggleLivePreview());
    }
    if (previewStopBtn) {
      previewStopBtn.addEventListener('click', () => this.stopLivePreview());
    }

    // Live relative volume sliders
    const bgVolSlider = document.getElementById('mys-bg-vol-slider');
    const affVolSlider = document.getElementById('mys-aff-vol-slider');
    if (bgVolSlider) {
      bgVolSlider.addEventListener('input', (e) => {
        if (this.bgGainNode) {
          const gain = Math.pow(10, parseFloat(e.target.value) / 20);
          this.bgGainNode.gain.value = gain;
        }
        document.getElementById('mys-bg-vol-val').textContent = `${e.target.value} dB`;
      });
    }
    if (affVolSlider) {
      affVolSlider.addEventListener('input', (e) => {
        if (this.affGainNode) {
          const gain = Math.pow(10, parseFloat(e.target.value) / 20);
          this.affGainNode.gain.value = gain;
        }
        document.getElementById('mys-aff-vol-val').textContent = `${e.target.value} dB`;
      });
    }

    // Final Mix & Export Button
    const exportBtn = document.getElementById('mys-final-export-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => this.handleFinalSubliminalExport());
    }
  }

  async loadVoicesAndLanguages() {
    try {
      const response = await window.api.get('/tracks/tts/languages/');
      if (response.ok) {
        const data = await response.json();
        const voiceSelect = document.getElementById('mys-voice-select');
        if (voiceSelect && data.voices) {
          voiceSelect.innerHTML = data.voices.map(v => `
            <option value="${v.id}" data-lang="${v.lang}">
              ${v.accent} • ${v.name} (${v.gender})
            </option>
          `).join('');
        }
      }
    } catch (err) {
      console.error('Failed to load TTS voices:', err);
    }
  }

  populateLibraryDropdown() {
    const librarySelect = document.getElementById('mys-library-select');
    if (!librarySelect) return;

    const tracks = window.library?.tracks || [];
    librarySelect.innerHTML = `
      <option value="">-- Select Track from Your Library --</option>
      ${tracks.map(t => `
        <option value="${t.id}">${t.title} (${t.duration_display || '--:--'})</option>
      `).join('')}
    `;
  }

  // --- Step 1: Background Music Handlers ---

  async handleYouTubeImport() {
    const urlInput = document.getElementById('mys-yt-url');
    const url = urlInput.value.trim();
    if (!url) {
      window.toast.show('Please enter a YouTube URL', 'error');
      return;
    }

    const consentBox = document.getElementById('mys-yt-consent');
    if (!consentBox.checked) {
      window.toast.show('Please check the rights confirmation box', 'error');
      return;
    }

    const btn = document.getElementById('mys-yt-import-btn');
    btn.disabled = true;
    btn.textContent = 'Extracting Audio...';
    window.toast.show('Downloading YouTube audio into base track...', 'info');

    try {
      const response = await window.api.post('/tracks/youtube/import/', {
        url: url,
        youtube_url: url,
        rights_confirmed: true,
        license_info: 'Make Your Own Sub YouTube Import'
      });

      let track = {};
      try {
        track = await response.json();
      } catch (e) {
        track = { error: `Server error (${response.status})` };
      }

      if (response.ok) {
        window.toast.show(`YouTube audio "${track.title}" loaded as base track!`, 'success');
        this.setBackgroundTrack(track);
        urlInput.value = '';
        await window.library.loadTracks();
      } else {
        window.toast.show(track.error || track.detail || 'YouTube download failed', 'error');
      }
    } catch (err) {
      window.toast.show(err.message || 'Error importing YouTube audio', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Import YouTube Audio';
    }
  }

  async handleDeviceUpload() {
    const fileInput = document.getElementById('mys-upload-file');
    if (!fileInput.files || fileInput.files.length === 0) return;

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name.replace(/\.[^/.]+$/, ""));
    formData.append('rights_confirmed', 'true');
    formData.append('license_info', 'User Device Upload');

    window.toast.show('Uploading audio track from device...', 'info');

    try {
      const response = await window.api.post('/tracks/upload/', formData);

      if (response.ok) {
        const track = await response.json();
        window.toast.show(`"${track.title}" uploaded and loaded as base track!`, 'success');
        this.setBackgroundTrack(track);
        fileInput.value = '';
        await window.library.loadTracks();
        if (window.trackEvent) window.trackEvent('base_track_uploaded', { format: track.format });
      } else {
        const err = await response.json();
        window.toast.show(err.detail || 'Upload failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error uploading file', 'error');
    }
  }

  handleLibrarySelect(trackId) {
    if (!trackId) return;
    const track = (window.library?.tracks || []).find(t => t.id === parseInt(trackId));
    if (track) {
      this.setBackgroundTrack(track);
      window.toast.show(`Selected "${track.title}" as background track`, 'success');
    }
  }

  setBackgroundTrack(track) {
    this.selectedBackgroundTrack = track;
    const card = document.getElementById('mys-bg-selected-card');
    const titleEl = document.getElementById('mys-bg-selected-title');
    const metaEl = document.getElementById('mys-bg-selected-meta');

    if (card && titleEl && metaEl) {
      titleEl.textContent = track.title;
      metaEl.textContent = `${track.duration_display || '--:--'} • Source: ${track.source_type}`;
      card.style.display = 'flex';
    }

    this.updateExportButtonState();
  }

  removeBackgroundTrack() {
    this.selectedBackgroundTrack = null;
    const card = document.getElementById('mys-bg-selected-card');
    if (card) card.style.display = 'none';
    this.stopLivePreview();
    this.updateExportButtonState();
  }

  // --- Step 2: Affirmation Generator Handlers ---

  applyPresetAffirmations(category) {
    const textInput = document.getElementById('mys-aff-text');
    const titleInput = document.getElementById('mys-sub-title');
    if (!textInput) return;

    const presets = {
      wealth: {
        text: "I am a powerful money magnet. Wealth, abundance, and lucrative opportunities flow into my life effortlessly every single day. I am financially free and prosperous.",
        title: "10x Wealth & Prosperity Subliminal"
      },
      confidence: {
        text: "I radiate supreme confidence, charisma, and magnetic self-worth. I am unstoppable, fearless, and deeply respected wherever I go.",
        title: "Ultimate Confidence & Charisma Subliminal"
      },
      health: {
        text: "Every cell in my body vibrates with vitality, perfect health, and youthful energy. My immune system is invincible and I sleep deeply and peacefully.",
        title: "Deep Health & Cellular Regeneration"
      },
      focus: {
        text: "My mind is laser-focused, razor-sharp, and absorbs complex knowledge instantly. I learn with effortless speed and excel in all my goals.",
        title: "Super Focus & Memory Mastery"
      },
      glowup: {
        text: "I radiate captivating beauty, perfect skin, and mesmerizing allure. My aura is irresistibly magnetic and enchanting.",
        title: "Supreme Glow Up & Physical Allure"
      },
      calm: {
        text: "I release all stress, anxiety, and fear. My nervous system is calm, peaceful, and anchored in deep serenity.",
        title: "Deep Peace & Anxiety Release"
      }
    };

    if (presets[category]) {
      textInput.value = presets[category].text;
      if (titleInput && (!titleInput.value || titleInput.value.startsWith('Custom Subliminal'))) {
        titleInput.value = presets[category].title;
      }
      window.toast.show(`Loaded ${category.toUpperCase()} affirmation preset!`, 'info');
    }
  }

  async handleGenerateAffirmations(e) {
    e.preventDefault();
    const text = document.getElementById('mys-aff-text').value.trim();
    if (!text) {
      window.toast.show('Please write your affirmation statements', 'error');
      return;
    }

    const voiceSelect = document.getElementById('mys-voice-select');
    const voice = voiceSelect ? voiceSelect.value : 'en-US-JennyNeural';
    const lang = voiceSelect?.selectedOptions[0]?.dataset.lang || 'en';
    const speed = parseFloat(document.getElementById('mys-speed-slider').value) || 1.0;

    const btn = document.getElementById('mys-generate-aff-btn');
    btn.disabled = true;
    btn.textContent = 'Synthesizing Neural Voice...';
    window.toast.show(`Generating voice (${speed}x speed)...`, 'info');

    try {
      const response = await window.api.post('/tracks/tts/generate/', {
        text,
        title: `Affirmations (${speed}x): ${text.slice(0, 30)}...`,
        language: lang,
        voice: voice,
        speed: speed
      });

      if (response.ok) {
        const track = await response.json();
        this.generatedAffirmationTrack = track;
        window.toast.show('Affirmation audio generated successfully!', 'success');

        // Show Affirmation Track Card
        const card = document.getElementById('mys-aff-generated-card');
        const titleEl = document.getElementById('mys-aff-generated-title');
        const metaEl = document.getElementById('mys-aff-generated-meta');

        if (card && titleEl && metaEl) {
          titleEl.textContent = track.title;
          metaEl.textContent = `${track.duration_display || '--:--'} • Voice: ${voice.split('-')[2] || voice}`;
          card.style.display = 'flex';
        }

        // Set default title if empty
        const titleInput = document.getElementById('mys-sub-title');
        if (titleInput && !titleInput.value) {
          titleInput.value = `Subliminal: ${text.slice(0, 35)}...`;
        }

        await window.library.loadTracks();
        this.updateExportButtonState();
        if (window.trackEvent) {
          window.trackEvent('affirmation_generated', {
            voice: voice,
            speed: speed,
            text_length: text.length
          });
        }
      } else {
        const err = await response.json();
        window.toast.show(err.error || 'Affirmation generation failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error generating affirmations', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '⚡ Generate Neural Affirmation Audio';
    }
  }

  // --- Step 3: Synchronized Live Preview & Final Subliminal Export ---

  toggleLivePreview() {
    if (this.isPlayingPreview) {
      this.stopLivePreview();
    } else {
      this.startLivePreview();
    }
  }

  startLivePreview() {
    if (!this.selectedBackgroundTrack && !this.generatedAffirmationTrack) {
      window.toast.show('Please select a background track or generate affirmations first', 'info');
      return;
    }

    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioContextClass();

      const bgUrl = this.selectedBackgroundTrack?.file;
      const affUrl = this.generatedAffirmationTrack?.file;

      const bgVol = parseFloat(document.getElementById('mys-bg-vol-slider').value) || 0;
      const affVol = parseFloat(document.getElementById('mys-aff-vol-slider').value) || -14;

      if (bgUrl) {
        this.bgAudio = new Audio(bgUrl);
        this.bgAudio.crossOrigin = 'anonymous';
        this.bgAudio.loop = document.getElementById('mys-loop-bg').checked;
        const source = this.audioContext.createMediaElementSource(this.bgAudio);
        this.bgGainNode = this.audioContext.createGain();
        this.bgGainNode.gain.value = Math.pow(10, bgVol / 20);
        source.connect(this.bgGainNode);
        this.bgGainNode.connect(this.audioContext.destination);
        this.bgAudio.play();
      }

      if (affUrl) {
        this.affAudio = new Audio(affUrl);
        this.affAudio.crossOrigin = 'anonymous';
        const source = this.audioContext.createMediaElementSource(this.affAudio);
        this.affGainNode = this.audioContext.createGain();
        this.affGainNode.gain.value = Math.pow(10, affVol / 20);
        source.connect(this.affGainNode);
        this.affGainNode.connect(this.audioContext.destination);
        this.affAudio.play();
      }

      this.isPlayingPreview = true;
      const btn = document.getElementById('mys-preview-play-btn');
      if (btn) {
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> Pause Live Preview`;
        btn.classList.add('btn-secondary');
        btn.classList.remove('btn-primary');
      }

    } catch (err) {
      console.error('Error starting live preview:', err);
      window.toast.show('Live preview playback error', 'error');
    }
  }

  stopLivePreview() {
    if (this.bgAudio) {
      this.bgAudio.pause();
      this.bgAudio.currentTime = 0;
      this.bgAudio = null;
    }
    if (this.affAudio) {
      this.affAudio.pause();
      this.affAudio.currentTime = 0;
      this.affAudio = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.isPlayingPreview = false;
    const btn = document.getElementById('mys-preview-play-btn');
    if (btn) {
      btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> Listen & Preview Subliminal Mix`;
      btn.classList.remove('btn-secondary');
      btn.classList.add('btn-primary');
    }
  }

  updateExportButtonState() {
    const exportBtn = document.getElementById('mys-final-export-btn');
    if (exportBtn) {
      const hasContent = this.selectedBackgroundTrack || this.generatedAffirmationTrack;
      exportBtn.disabled = !hasContent;
    }
  }

  async handleFinalSubliminalExport() {
    this.stopLivePreview();

    if (!this.selectedBackgroundTrack && !this.generatedAffirmationTrack) {
      window.toast.show('Please select a background track or generate affirmations', 'error');
      return;
    }

    const titleInput = document.getElementById('mys-sub-title');
    const title = titleInput.value.trim() || 'My Custom Subliminal Track';

    const bgVol = parseFloat(document.getElementById('mys-bg-vol-slider').value) || 0;
    const affVol = parseFloat(document.getElementById('mys-aff-vol-slider').value) || -14;
    const loopShorter = document.getElementById('mys-loop-bg').checked;

    const layers = [];
    if (this.selectedBackgroundTrack) {
      layers.push({
        track_id: this.selectedBackgroundTrack.id,
        volume: bgVol,
        start_ms: 0,
        muted: false
      });
    }
    if (this.generatedAffirmationTrack) {
      layers.push({
        track_id: this.generatedAffirmationTrack.id,
        volume: affVol,
        start_ms: 0,
        muted: false
      });
    }

    const btn = document.getElementById('mys-final-export-btn');
    btn.disabled = true;
    btn.innerHTML = `⏳ Rendering Master Subliminal...`;
    window.toast.show('Mastering & rendering your complete subliminal audio track...', 'info');

    try {
      const response = await window.api.post('/tracks/mixer/export/', {
        title: title,
        layers: layers,
        loop_shorter: loopShorter
      });

      if (response.ok) {
        const masterTrack = await response.json();
        window.toast.show(`Subliminal "${masterTrack.title}" created successfully!`, 'success');

        // Show Success Download Box
        const successBox = document.getElementById('mys-download-success-box');
        const downloadBtn = document.getElementById('mys-direct-download-btn');
        const successTitle = document.getElementById('mys-success-title');

        if (successBox && downloadBtn && successTitle) {
          successTitle.textContent = masterTrack.title;
          downloadBtn.onclick = () => window.library.downloadTrack(masterTrack.id, masterTrack.title);
          successBox.style.display = 'block';
          successBox.scrollIntoView({ behavior: 'smooth' });
        }

        await window.library.loadTracks();
        window.player.playTrack(masterTrack);
        if (window.trackEvent) {
          window.trackEvent('subliminal_downloaded', {
            title: masterTrack.title,
            duration: masterTrack.duration
          });
        }
      } else {
        const err = await response.json();
        window.toast.show(err.error || 'Subliminal export failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error creating subliminal track', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Create & Download Subliminal`;
    }
  }
}

window.tts = new MakeYourSubManager();
