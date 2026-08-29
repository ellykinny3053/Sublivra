/**
 * YouTube Rights-Verified Import Module
 * Fetches video metadata preview, requires explicit legal ownership/permission confirmation, then imports.
 */

class YouTubeImporter {
  constructor() {
    this.currentMetadata = null;
    this.init();
  }

  init() {
    this.bindEvents();
  }

  bindEvents() {
    const checkBtn = document.getElementById('yt-check-btn');
    const importForm = document.getElementById('yt-import-form');
    const openModalBtn = document.getElementById('btn-open-yt-modal');
    const closeModalBtn = document.getElementById('btn-close-yt-modal');
    const modal = document.getElementById('yt-modal');

    if (openModalBtn) {
      openModalBtn.addEventListener('click', () => {
        modal.classList.add('active');
      });
    }

    if (closeModalBtn) {
      closeModalBtn.addEventListener('click', () => {
        modal.classList.remove('active');
      });
    }

    if (checkBtn) {
      checkBtn.addEventListener('click', () => this.checkVideo());
    }

    if (importForm) {
      importForm.addEventListener('submit', (e) => this.handleImport(e));
    }
  }

  async checkVideo() {
    const url = document.getElementById('yt-url-input').value.trim();
    const btn = document.getElementById('yt-check-btn');
    const previewContainer = document.getElementById('yt-preview-card');

    if (!url) {
      window.toast.show('Please enter a YouTube video URL', 'error');
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Checking Video...';

    try {
      const response = await window.api.post('/tracks/youtube/metadata/', { url });
      const data = await response.json();

      if (response.ok) {
        this.currentMetadata = data;
        previewContainer.style.display = 'flex';
        document.getElementById('yt-preview-thumb').src = data.thumbnail_url || '';
        document.getElementById('yt-preview-title').textContent = data.title || 'Untitled';
        document.getElementById('yt-preview-channel').textContent = data.channel_name || '';
        document.getElementById('yt-preview-duration').textContent = `${Math.floor(data.duration / 60)}:${(data.duration % 60).toString().padStart(2, '0')}`;
        document.getElementById('yt-import-submit-btn').disabled = false;
      } else {
        window.toast.show(data.error || 'Could not access YouTube video', 'error');
      }
    } catch (err) {
      window.toast.show('Error retrieving video info', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Check Video';
    }
  }

  async handleImport(e) {
    e.preventDefault();
    const url = document.getElementById('yt-url-input').value.trim();
    const consent = document.getElementById('yt-consent-checkbox').checked;
    const licenseInfo = document.getElementById('yt-license-info').value.trim();
    const btn = document.getElementById('yt-import-submit-btn');

    if (!url) {
      window.toast.show('Please enter a YouTube URL', 'error');
      return;
    }

    if (!consent) {
      window.toast.show('You must confirm copyright ownership or licensing rights', 'error');
      return;
    }

    btn.disabled = true;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin" style="animation: spin 1s linear infinite;"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg> Extracting & Converting Audio...`;

    try {
      const response = await window.api.post('/tracks/youtube/import/', {
        url,
        rights_confirmed: true,
        license_info: licenseInfo || 'Creator-verified audio',
        title: this.currentMetadata?.title || '',
      });

      const data = await response.json();

      if (response.ok) {
        window.toast.show('Audio imported successfully from YouTube into library!', 'success');
        document.getElementById('yt-modal').classList.remove('active');
        document.getElementById('yt-import-form').reset();
        document.getElementById('yt-preview-card').style.display = 'none';
        await window.library.loadTracks();
        window.player.playTrack(data);
      } else {
        const msg = data.error || data.detail || (data.suggestion ? data.suggestion : 'Import failed');
        window.toast.show(msg, 'error', 6000);
      }
    } catch (err) {
      window.toast.show('Network error while importing YouTube audio', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = 'Import Audio to Library';
    }
  }
}

window.youtube = new YouTubeImporter();
