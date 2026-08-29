/**
 * Audio Editor Studio Module
 * Non-destructive audio manipulation: Trim, Speed Shift, Fade In/Out, Volume Normalization.
 */

class AudioEditor {
  constructor() {
    this.currentTrack = null;
    this.audioDurationMs = 0;
    this.init();
  }

  init() {
    this.bindEvents();
  }

  bindEvents() {
    const trackSelect = document.getElementById('editor-track-select');
    const trimForm = document.getElementById('editor-trim-form');
    const speedForm = document.getElementById('editor-speed-form');
    const fadeForm = document.getElementById('editor-fade-form');
    const normForm = document.getElementById('editor-norm-form');

    const speedSlider = document.getElementById('editor-speed-slider');
    const speedVal = document.getElementById('editor-speed-val');

    if (trackSelect) {
      trackSelect.addEventListener('change', (e) => this.onTrackSelected(e.target.value));
    }

    if (speedSlider && speedVal) {
      speedSlider.addEventListener('input', (e) => {
        speedVal.textContent = `${parseFloat(e.target.value).toFixed(2)}x`;
      });
    }

    if (trimForm) trimForm.addEventListener('submit', (e) => this.handleTrim(e));
    if (speedForm) speedForm.addEventListener('submit', (e) => this.handleSpeed(e));
    if (fadeForm) fadeForm.addEventListener('submit', (e) => this.handleFade(e));
    if (normForm) normForm.addEventListener('submit', (e) => this.handleNormalize(e));
  }

  async onTrackSelected(trackId) {
    if (!trackId) {
      this.currentTrack = null;
      document.getElementById('editor-controls-panel').style.display = 'none';
      return;
    }

    try {
      const response = await window.api.get(`/tracks/${trackId}/info/`);
      if (response.ok) {
        const info = await response.json();
        this.audioDurationMs = info.duration_ms || Math.round(info.duration * 1000);
        this.currentTrack = window.library.tracks.find(t => t.id == trackId);

        document.getElementById('editor-controls-panel').style.display = 'block';
        document.getElementById('editor-info-duration').textContent = `${(this.audioDurationMs / 1000).toFixed(2)}s`;
        document.getElementById('editor-info-rate').textContent = `${info.sample_rate || 44100} Hz`;
        document.getElementById('editor-info-dbfs').textContent = `${info.dbfs !== null ? info.dbfs + ' dBFS' : 'N/A'}`;

        // Set initial trim values
        document.getElementById('trim-start').value = '0';
        document.getElementById('trim-end').value = (this.audioDurationMs / 1000).toFixed(2);
      }
    } catch (err) {
      console.error('Failed to get audio info:', err);
    }
  }

  loadForEditing(trackId) {
    // Switch to editor tab
    const editorNavBtn = document.querySelector('[data-tab="editor"]');
    if (editorNavBtn) editorNavBtn.click();

    const select = document.getElementById('editor-track-select');
    if (select) {
      select.value = trackId;
      this.onTrackSelected(trackId);
    }
  }

  async handleTrim(e) {
    e.preventDefault();
    if (!this.currentTrack) return;

    const startSec = parseFloat(document.getElementById('trim-start').value) || 0;
    const endSec = parseFloat(document.getElementById('trim-end').value);
    const title = document.getElementById('trim-title').value;

    const start_ms = Math.round(startSec * 1000);
    const end_ms = endSec ? Math.round(endSec * 1000) : this.audioDurationMs;

    const btn = document.getElementById('trim-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Trimming Audio...';

    try {
      const response = await window.api.post('/tracks/editor/trim/', {
        track_id: this.currentTrack.id,
        start_ms,
        end_ms,
        title: title || `Trimmed: ${this.currentTrack.title}`,
      });

      const data = await response.json();
      if (response.ok) {
        window.toast.show('Audio trimmed and saved as a new track!', 'success');
        await window.library.loadTracks();
        window.player.playTrack(data);
      } else {
        window.toast.show(data.error || 'Trim failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error during trimming', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Apply Trim';
    }
  }

  async handleSpeed(e) {
    e.preventDefault();
    if (!this.currentTrack) return;

    const speed = parseFloat(document.getElementById('editor-speed-slider').value);
    const title = document.getElementById('speed-title').value;

    const btn = document.getElementById('speed-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Adjusting Speed...';

    try {
      const response = await window.api.post('/tracks/editor/speed/', {
        track_id: this.currentTrack.id,
        speed,
        title: title || `${speed}x: ${this.currentTrack.title}`,
      });

      const data = await response.json();
      if (response.ok) {
        window.toast.show(`Speed adjusted to ${speed}x! Saved as new track.`, 'success');
        await window.library.loadTracks();
        window.player.playTrack(data);
      } else {
        window.toast.show(data.error || 'Speed change failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error changing speed', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Apply Speed Change';
    }
  }

  async handleFade(e) {
    e.preventDefault();
    if (!this.currentTrack) return;

    const fadeInSec = parseFloat(document.getElementById('fade-in').value) || 0;
    const fadeOutSec = parseFloat(document.getElementById('fade-out').value) || 0;
    const title = document.getElementById('fade-title').value;

    const fade_in_ms = Math.round(fadeInSec * 1000);
    const fade_out_ms = Math.round(fadeOutSec * 1000);

    const btn = document.getElementById('fade-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Applying Fades...';

    try {
      const response = await window.api.post('/tracks/editor/fade/', {
        track_id: this.currentTrack.id,
        fade_in_ms,
        fade_out_ms,
        title: title || `Faded: ${this.currentTrack.title}`,
      });

      const data = await response.json();
      if (response.ok) {
        window.toast.show('Fades applied and saved as new track!', 'success');
        await window.library.loadTracks();
        window.player.playTrack(data);
      } else {
        window.toast.show(data.error || 'Fade operation failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error applying fades', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Apply Fades';
    }
  }

  async handleNormalize(e) {
    e.preventDefault();
    if (!this.currentTrack) return;

    const target_dbfs = parseFloat(document.getElementById('norm-target').value) || -20.0;
    const title = document.getElementById('norm-title').value;

    const btn = document.getElementById('norm-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Normalizing Volume...';

    try {
      const response = await window.api.post('/tracks/editor/normalize/', {
        track_id: this.currentTrack.id,
        target_dbfs,
        title: title || `Normalized (${target_dbfs}dB): ${this.currentTrack.title}`,
      });

      const data = await response.json();
      if (response.ok) {
        window.toast.show('Volume normalized and saved as new track!', 'success');
        await window.library.loadTracks();
        window.player.playTrack(data);
      } else {
        window.toast.show(data.error || 'Normalize failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error normalizing audio', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Normalize Audio';
    }
  }
}

window.editor = new AudioEditor();
