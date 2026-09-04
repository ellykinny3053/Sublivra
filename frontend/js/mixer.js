/**
 * Audio Mixer Module with Real-Time Web Audio API Preview & Live Volume Adjustments
 * Allows hearing layers playing together, adjusting volume in real time, setting time offsets,
 * solo/mute, and exporting the final mix.
 */

class AudioMixer {
  constructor() {
    this.layers = [
      { id: 1, trackId: null, volume: 0, offsetSec: 0, muted: false, solo: false },
      { id: 2, trackId: null, volume: -4, offsetSec: 0, muted: false, solo: false }
    ];

    this.audioContext = null;
    this.audioElements = new Map(); // layerId -> { audio, sourceNode, gainNode }
    this.isPlaying = false;
    this.previewDuration = 0;
    this.playbackInterval = null;

    this.init();
  }

  init() {
    this.bindEvents();
    this.renderLayers();
  }

  getAudioContext() {
    if (!this.audioContext) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioCtx();
    }
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume();
    }
    return this.audioContext;
  }

  bindEvents() {
    const addLayerBtn = document.getElementById('mixer-add-layer-btn');
    const exportBtn = document.getElementById('mixer-export-btn');
    const playPreviewBtn = document.getElementById('mixer-preview-play-btn');
    const stopPreviewBtn = document.getElementById('mixer-preview-stop-btn');
    const masterTimeline = document.getElementById('mixer-master-timeline');

    if (addLayerBtn) {
      addLayerBtn.addEventListener('click', () => this.addLayer());
    }

    if (exportBtn) {
      exportBtn.addEventListener('click', () => this.handleExport());
    }

    if (playPreviewBtn) {
      playPreviewBtn.addEventListener('click', () => this.toggleLivePreview());
    }

    if (stopPreviewBtn) {
      stopPreviewBtn.addEventListener('click', () => this.stopLivePreview());
    }

    if (masterTimeline) {
      masterTimeline.addEventListener('click', (e) => {
        const rect = masterTimeline.getBoundingClientRect();
        const pos = (e.clientX - rect.left) / rect.width;
        this.seekLivePreview(pos);
      });
    }
  }

  addLayer() {
    if (this.layers.length >= 6) {
      window.toast.show('Maximum 6 layers allowed in studio mixer', 'info');
      return;
    }
    const nextId = this.layers.length > 0 ? Math.max(...this.layers.map(l => l.id)) + 1 : 1;
    this.layers.push({ id: nextId, trackId: null, volume: 0, offsetSec: 0, muted: false, solo: false });
    this.renderLayers();
  }

  removeLayer(layerId) {
    if (this.layers.length <= 2) {
      window.toast.show('At least 2 layers are needed for mixing', 'info');
      return;
    }
    this.teardownAudioNode(layerId);
    this.layers = this.layers.filter(l => l.id !== layerId);
    this.renderLayers();
  }

  renderLayers() {
    const container = document.getElementById('mixer-layers-container');
    if (!container) return;

    container.innerHTML = this.layers.map((layer, idx) => `
      <div class="glass-card" style="padding: 16px; margin-bottom: 14px; position: relative;" data-layer-id="${layer.id}">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-weight: 700; font-size: 0.95rem; color: var(--text-accent);">Layer ${idx + 1}</span>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-outline btn-sm ${layer.muted ? 'btn-danger' : ''}" 
                style="padding: 3px 8px; font-size: 0.72rem; border-radius: 4px;" 
                onclick="window.mixer.toggleMute(${layer.id})">
                ${layer.muted ? 'MUTED' : 'MUTE'}
              </button>
              <button class="btn btn-outline btn-sm ${layer.solo ? 'btn-primary' : ''}" 
                style="padding: 3px 8px; font-size: 0.72rem; border-radius: 4px;" 
                onclick="window.mixer.toggleSolo(${layer.id})">
                SOLO
              </button>
            </div>
          </div>
          ${this.layers.length > 2 ? `
            <button class="btn-icon" onclick="window.mixer.removeLayer(${layer.id})" style="width: 28px; height: 28px;" title="Remove Layer">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          ` : ''}
        </div>

        <div class="mixer-layer-controls-grid" style="display: grid; grid-template-columns: 2fr 1.2fr 1fr; gap: 16px; align-items: center;">
          <!-- Track Select -->
          <div>
            <label for="layer-track-${layer.id}" class="form-label" style="font-size: 0.75rem; margin-bottom: 4px;">Audio Source</label>
            <select id="layer-track-${layer.id}" class="form-select layer-track-select" aria-label="Layer ${idx + 1} Audio Source" onchange="window.mixer.updateLayerTrack(${layer.id}, this.value)">
              <option value="">-- Choose Audio Track --</option>
              ${(window.library?.tracks || []).map(t => `
                <option value="${t.id}" ${layer.trackId == t.id ? 'selected' : ''}>${t.title} (${t.duration_display})</option>
              `).join('')}
            </select>
          </div>

          <!-- Live Real-Time Volume -->
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">
              <label for="vol-slider-${layer.id}" style="font-size: 0.75rem; color: inherit; margin-bottom: 0;">Real-Time Volume</label>
              <span id="vol-val-${layer.id}" style="font-family: var(--font-mono); color: var(--text-accent); font-weight: 600;">${layer.volume > 0 ? '+' : ''}${layer.volume} dB</span>
            </div>
            <input type="range" id="vol-slider-${layer.id}" min="-24" max="10" step="0.5" value="${layer.volume}" class="custom-range" aria-label="Layer ${idx + 1} Volume"
              oninput="window.mixer.updateLayerVolume(${layer.id}, this.value)">
          </div>

          <!-- Time Offset (Delay) -->
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">
              <label for="offset-slider-${layer.id}" style="font-size: 0.75rem; color: inherit; margin-bottom: 0;">Start Delay</label>
              <span id="offset-val-${layer.id}" style="font-family: var(--font-mono); color: var(--accent-secondary); font-weight: 600;">${layer.offsetSec}s</span>
            </div>
            <input type="range" id="offset-slider-${layer.id}" min="0" max="30" step="0.5" value="${layer.offsetSec}" class="custom-range" aria-label="Layer ${idx + 1} Start Delay"
              oninput="window.mixer.updateLayerOffset(${layer.id}, this.value)">
          </div>
        </div>
      </div>
    `).join('');
  }

  updateLayerTrack(layerId, trackId) {
    const layer = this.layers.find(l => l.id === layerId);
    if (layer) {
      layer.trackId = trackId ? parseInt(trackId) : null;
      this.teardownAudioNode(layerId);
      if (this.isPlaying) {
        this.setupAudioNode(layer);
      }
    }
  }

  updateLayerVolume(layerId, volume) {
    const layer = this.layers.find(l => l.id === layerId);
    if (layer) {
      layer.volume = parseFloat(volume);
      const valEl = document.getElementById(`vol-val-${layerId}`);
      if (valEl) {
        valEl.textContent = `${layer.volume > 0 ? '+' : ''}${layer.volume} dB`;
      }
      this.applyLiveGain(layer);
    }
  }

  updateLayerOffset(layerId, offsetSec) {
    const layer = this.layers.find(l => l.id === layerId);
    if (layer) {
      layer.offsetSec = parseFloat(offsetSec);
      const valEl = document.getElementById(`offset-val-${layerId}`);
      if (valEl) {
        valEl.textContent = `${layer.offsetSec}s`;
      }
    }
  }

  toggleMute(layerId) {
    const layer = this.layers.find(l => l.id === layerId);
    if (layer) {
      layer.muted = !layer.muted;
      this.renderLayers();
      this.applyAllGains();
    }
  }

  toggleSolo(layerId) {
    const layer = this.layers.find(l => l.id === layerId);
    if (layer) {
      layer.solo = !layer.solo;
      this.renderLayers();
      this.applyAllGains();
    }
  }

  applyLiveGain(layer) {
    const node = this.audioElements.get(layer.id);
    if (!node || !node.gainNode) return;

    let targetGain = Math.pow(10, layer.volume / 20);

    const hasSolo = this.layers.some(l => l.solo);
    if (hasSolo) {
      if (!layer.solo) targetGain = 0;
    } else if (layer.muted) {
      targetGain = 0;
    }

    const ctx = this.getAudioContext();
    node.gainNode.gain.setValueAtTime(targetGain, ctx.currentTime);
  }

  applyAllGains() {
    this.layers.forEach(layer => this.applyLiveGain(layer));
  }

  teardownAudioNode(layerId) {
    const entry = this.audioElements.get(layerId);
    if (entry) {
      try {
        entry.audio.pause();
        entry.audio.src = '';
      } catch (e) {}
      this.audioElements.delete(layerId);
    }
  }

  setupAudioNode(layer) {
    if (!layer.trackId) return;
    const track = (window.library?.tracks || []).find(t => t.id === layer.trackId);
    if (!track || !track.file) return;

    let entry = this.audioElements.get(layer.id);
    if (!entry) {
      const ctx = this.getAudioContext();
      const audio = new Audio();
      audio.crossOrigin = "anonymous";
      const fileUrl = track.file.startsWith('http') ? track.file : `http://127.0.0.1:8000${track.file}`;
      audio.src = fileUrl;

      const sourceNode = ctx.createMediaElementSource(audio);
      const gainNode = ctx.createGain();
      sourceNode.connect(gainNode);
      gainNode.connect(ctx.destination);

      entry = { audio, sourceNode, gainNode, track };
      this.audioElements.set(layer.id, entry);
    }

    this.applyLiveGain(layer);
    return entry;
  }

  async toggleLivePreview() {
    if (this.isPlaying) {
      this.pauseLivePreview();
    } else {
      await this.startLivePreview();
    }
  }

  async startLivePreview() {
    const activeLayers = this.layers.filter(l => l.trackId !== null);
    if (activeLayers.length < 2) {
      window.toast.show('Please select at least 2 tracks to preview real-time mixing', 'info');
      return;
    }

    const ctx = this.getAudioContext();
    if (ctx.state === 'suspended') {
      await ctx.resume();
    }

    // Initialize all audio nodes
    activeLayers.forEach(l => this.setupAudioNode(l));

    let maxDuration = 0;
    this.audioElements.forEach((entry, layerId) => {
      const layer = this.layers.find(l => l.id === layerId);
      const dur = (entry.track?.duration || 0) + (layer?.offsetSec || 0);
      if (dur > maxDuration) maxDuration = dur;
    });

    this.previewDuration = maxDuration || 30;

    // Synchronize and play all layers
    this.audioElements.forEach((entry, layerId) => {
      const layer = this.layers.find(l => l.id === layerId);
      const offset = layer?.offsetSec || 0;
      entry.audio.currentTime = 0;
      
      if (offset > 0) {
        entry.audio.pause();
        setTimeout(() => {
          if (this.isPlaying) entry.audio.play().catch(e => console.warn(e));
        }, offset * 1000);
      } else {
        entry.audio.play().catch(e => console.warn(e));
      }
    });

    this.isPlaying = true;
    this.updatePlayStateUI(true);
    this.startProgressTracker();
  }

  pauseLivePreview() {
    this.isPlaying = false;
    this.audioElements.forEach(entry => entry.audio.pause());
    this.updatePlayStateUI(false);
    clearInterval(this.playbackInterval);
  }

  stopLivePreview() {
    this.pauseLivePreview();
    this.audioElements.forEach(entry => {
      entry.audio.currentTime = 0;
    });
    const progressEl = document.getElementById('mixer-preview-progress');
    const timeEl = document.getElementById('mixer-preview-time');
    if (progressEl) progressEl.style.width = '0%';
    if (timeEl) timeEl.textContent = '00:00 / ' + this.formatTime(this.previewDuration);
  }

  seekLivePreview(ratio) {
    const seekTime = ratio * this.previewDuration;
    this.audioElements.forEach((entry, layerId) => {
      const layer = this.layers.find(l => l.id === layerId);
      const offset = layer?.offsetSec || 0;
      const trackTime = Math.max(0, seekTime - offset);
      if (entry.audio.duration && trackTime < entry.audio.duration) {
        entry.audio.currentTime = trackTime;
      }
    });
  }

  startProgressTracker() {
    clearInterval(this.playbackInterval);
    const progressEl = document.getElementById('mixer-preview-progress');
    const timeEl = document.getElementById('mixer-preview-time');

    const startTime = Date.now();

    this.playbackInterval = setInterval(() => {
      let maxCurrent = 0;
      this.audioElements.forEach((entry, layerId) => {
        const layer = this.layers.find(l => l.id === layerId);
        const curr = entry.audio.currentTime + (layer?.offsetSec || 0);
        if (curr > maxCurrent) maxCurrent = curr;
      });

      if (this.previewDuration > 0) {
        const percent = Math.min(100, (maxCurrent / this.previewDuration) * 100);
        if (progressEl) progressEl.style.width = `${percent}%`;
        if (timeEl) timeEl.textContent = `${this.formatTime(maxCurrent)} / ${this.formatTime(this.previewDuration)}`;
      }

      if (maxCurrent >= this.previewDuration) {
        this.stopLivePreview();
      }
    }, 100);
  }

  updatePlayStateUI(isPlaying) {
    const playBtn = document.getElementById('mixer-preview-play-btn');
    if (playBtn) {
      playBtn.innerHTML = isPlaying
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> Pause Live Preview`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> Listen & Preview Live Mix`;
    }
  }

  formatTime(seconds) {
    if (isNaN(seconds) || seconds === null) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  renderTrackSelectors() {
    this.renderLayers();
  }

  async handleExport() {
    const selectedLayers = this.layers.filter(l => l.trackId !== null);
    if (selectedLayers.length < 2) {
      window.toast.show('Please select at least 2 tracks to mix', 'error');
      return;
    }

    this.pauseLivePreview();

    const title = document.getElementById('mixer-title').value;
    const loopShorter = document.getElementById('mixer-loop-shorter').checked;
    const btn = document.getElementById('mixer-export-btn');

    btn.disabled = true;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin" style="animation: spin 1s linear infinite;"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg> Mixing & Exporting...`;

    try {
      const response = await window.api.post('/tracks/mixer/export/', {
        title: title || 'Mixed Audio Studio Production',
        loop_shorter: loopShorter,
        tracks: selectedLayers.map(l => ({
          track_id: l.trackId,
          volume: l.muted ? -60 : l.volume,
          offset_ms: Math.round(l.offsetSec * 1000),
        }))
      });

      const data = await response.json();
      if (response.ok) {
        window.toast.show('Mixed track generated and saved to library!', 'success');
        await window.library.loadTracks();
        window.player.playTrack(data);
      } else {
        window.toast.show(data.error || 'Mixing failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error mixing tracks', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Mix & Export Track`;
    }
  }
}

window.mixer = new AudioMixer();
