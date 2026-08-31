/**
 * Audio Library Module
 * Handles loading tracks, uploading files with consent checkbox, and filtering.
 */

class LibraryManager {
  constructor() {
    this.tracks = [];
    this.init();
  }

  init() {
    this.bindEvents();
  }

  bindEvents() {
    const uploadForm = document.getElementById('upload-form');
    const openUploadBtn = document.getElementById('btn-open-upload');
    const closeUploadBtn = document.getElementById('btn-close-upload');
    const uploadModal = document.getElementById('upload-modal');
    const searchInput = document.getElementById('library-search');
    const filterSelect = document.getElementById('library-filter-source');

    if (openUploadBtn) {
      openUploadBtn.addEventListener('click', () => {
        uploadModal.classList.add('active');
      });
    }

    if (closeUploadBtn) {
      closeUploadBtn.addEventListener('click', () => {
        uploadModal.classList.remove('active');
      });
    }

    if (uploadForm) {
      uploadForm.addEventListener('submit', (e) => this.handleUpload(e));
    }

    if (searchInput) {
      searchInput.addEventListener('input', () => this.filterTracks());
    }

    if (filterSelect) {
      filterSelect.addEventListener('change', () => this.filterTracks());
    }
  }

  async loadTracks() {
    try {
      const response = await window.api.get('/tracks/');
      if (response.ok) {
        const data = await response.json();
        this.tracks = data.results || data;
        this.renderTracks(this.tracks);
        this.updateStudioSelects();
      }
    } catch (err) {
      console.error('Failed to load library tracks:', err);
    }
  }

  renderTracks(tracks) {
    const container = document.getElementById('tracks-container');
    if (!container) return;

    if (tracks.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 48px 16px; color: var(--text-muted);">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 12px; opacity: 0.5;"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>
          <p style="font-size: 1.1rem; font-weight: 600; color: var(--text-primary);">No tracks yet</p>
          <p style="font-size: 0.88rem; margin-top: 4px;">Generate an affirmation via TTS, upload your own audio, or import a rights-verified track.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = tracks.map(track => `
      <div class="track-card">
        <div class="track-header">
          <div class="track-title-block">
            <h3 class="track-title" title="${track.title}">${track.title}</h3>
            <div class="track-meta">
              <span class="badge badge-${track.source_type}">${track.source_type}</span>
              <span>${track.duration_display || '--:--'}</span>
            </div>
          </div>
          <button class="btn-icon" onclick="window.library.deleteTrack(${track.id})" title="Delete Track">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
        
        <div class="track-actions">
          <button class="btn btn-primary" style="flex: 1; padding: 8px 10px;" onclick='window.player.playTrack(${JSON.stringify(track).replace(/'/g, "&#39;")})'>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            Play
          </button>
          <button class="btn btn-outline" style="padding: 8px 10px;" onclick='window.library.downloadTrack(${JSON.stringify(track).replace(/'/g, "&#39;")})' title="Download Audio File">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            Download
          </button>
          <button class="btn btn-secondary" style="padding: 8px 10px;" onclick="window.editor.loadForEditing(${track.id})" title="Edit in Studio">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
            Edit
          </button>
        </div>
      </div>
    `).join('');
  }

  filterTracks() {
    const search = (document.getElementById('library-search')?.value || '').toLowerCase();
    const source = document.getElementById('library-filter-source')?.value || '';

    const filtered = this.tracks.filter(t => {
      const matchSearch = t.title.toLowerCase().includes(search);
      const matchSource = source === '' || t.source_type === source;
      return matchSearch && matchSource;
    });

    this.renderTracks(filtered);
  }

  async handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('upload-file-input');
    const titleInput = document.getElementById('upload-title-input');
    const consentBox = document.getElementById('upload-consent-checkbox');
    const submitBtn = document.getElementById('upload-submit-btn');

    if (!fileInput.files[0]) {
      window.toast.show('Please select an audio file to upload', 'error');
      return;
    }

    if (!consentBox.checked) {
      window.toast.show('You must confirm copyright ownership or permission', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('title', titleInput.value || fileInput.files[0].name.replace(/\.[^/.]+$/, ""));
    formData.append('rights_confirmed', 'true');

    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading...';

    try {
      const response = await window.api.post('/tracks/upload/', formData);
      if (response.ok) {
        window.toast.show('Audio track uploaded successfully', 'success');
        document.getElementById('upload-modal').classList.remove('active');
        document.getElementById('upload-form').reset();
        await this.loadTracks();
      } else {
        const data = await response.json();
        window.toast.show(data.file || data.detail || 'Upload failed', 'error');
      }
    } catch (err) {
      window.toast.show('Network error during upload', 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Upload Track';
    }
  }

  async deleteTrack(trackId) {
    if (!confirm('Are you sure you want to delete this track?')) return;

    try {
      const response = await window.api.delete(`/tracks/${trackId}/`);
      if (response.ok || response.status === 204) {
        window.toast.show('Track deleted', 'success');
        await this.loadTracks();
      } else {
        window.toast.show('Failed to delete track', 'error');
      }
    } catch (err) {
      window.toast.show('Error deleting track', 'error');
    }
  }

  downloadTrack(track) {
    if (!track || !track.file) return;
    const fileUrl = track.file.startsWith('http') ? track.file : track.file;
    const token = window.api.accessToken;

    fetch(fileUrl, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {}
    })
      .then(res => res.blob())
      .then(blob => {
        const a = document.createElement('a');
        a.href = window.URL.createObjectURL(blob);
        const ext = track.format ? `.${track.format}` : '.mp3';
        const cleanTitle = (track.title || 'audio_track').replace(/[^a-zA-Z0-9_-]/g, '_');
        a.download = `${cleanTitle}${ext}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.toast.show(`Downloading "${track.title}"...`, 'success');
        if (window.trackEvent) {
          window.trackEvent('track_downloaded', {
            title: track.title,
            source_type: track.source_type
          });
        }
      })
      .catch(err => {
        window.toast.show('Download failed', 'error');
      });
  }

  updateStudioSelects() {
    // Update select dropdowns across the editor, mixer, and playlists
    const editorSelect = document.getElementById('editor-track-select');
    if (editorSelect) {
      const currentVal = editorSelect.value;
      editorSelect.innerHTML = '<option value="">-- Choose a Track to Edit --</option>' +
        this.tracks.map(t => `<option value="${t.id}">${t.title} (${t.duration_display})</option>`).join('');
      if (currentVal) editorSelect.value = currentVal;
    }

    if (window.mixer) {
      window.mixer.renderTrackSelectors();
    }
  }
}

window.library = new LibraryManager();
