/**
 * Audio Player Dock Controller
 * Handles global audio playback, timeline seeking, and volume control.
 */

class AudioPlayer {
  constructor() {
    this.audio = new Audio();
    this.dock = document.getElementById('player-dock');
    this.titleEl = document.getElementById('player-track-title');
    this.artistEl = document.getElementById('player-track-artist');
    this.playBtn = document.getElementById('player-play-btn');
    this.timeline = document.getElementById('player-timeline');
    this.progress = document.getElementById('player-progress');
    this.currTimeEl = document.getElementById('player-curr-time');
    this.totalTimeEl = document.getElementById('player-total-time');
    this.volumeSlider = document.getElementById('player-volume');
    this.downloadBtn = document.getElementById('player-download-btn');

    this.currentTrack = null;
    this.isDragging = false;
    this.init();
  }

  init() {
    if (this.playBtn) {
      this.playBtn.addEventListener('click', () => this.togglePlay());
    }

    if (this.downloadBtn) {
      this.downloadBtn.addEventListener('click', () => {
        if (this.currentTrack && window.library) {
          window.library.downloadTrack(this.currentTrack);
        }
      });
    }

    this.audio.addEventListener('timeupdate', () => {
      if (!this.isDragging) {
        this.updateProgress();
      }
    });

    this.audio.addEventListener('ended', () => this.onEnded());
    
    this.audio.addEventListener('loadedmetadata', () => {
      if (this.audio.duration && !isNaN(this.audio.duration)) {
        this.totalTimeEl.textContent = this.formatTime(this.audio.duration);
      }
    });

    this.audio.addEventListener('error', () => {
      this.updatePlayIcon(false);
      if (window.toast) {
        window.toast.show('Could not stream audio track', 'error');
      }
    });

    // Spotify-style Interactive Timeline Scrubbing
    if (this.timeline) {
      const handleSeek = (clientX) => {
        const rect = this.timeline.getBoundingClientRect();
        let pos = (clientX - rect.left) / rect.width;
        pos = Math.max(0, Math.min(1, pos));
        this.progress.style.width = `${pos * 100}%`;
        const dur = this.audio.duration || (this.currentTrack ? this.currentTrack.duration : 0);
        if (dur) {
          this.currTimeEl.textContent = this.formatTime(pos * dur);
        }
        return pos;
      };

      this.timeline.addEventListener('click', (e) => {
        const pos = handleSeek(e.clientX);
        const dur = this.audio.duration || (this.currentTrack ? this.currentTrack.duration : 0);
        if (dur) {
          this.audio.currentTime = pos * dur;
        }
      });

      this.timeline.addEventListener('mousedown', (e) => {
        this.isDragging = true;
        handleSeek(e.clientX);

        const onMove = (moveEvt) => {
          if (this.isDragging) handleSeek(moveEvt.clientX);
        };

        const onUp = (upEvt) => {
          if (this.isDragging) {
            this.isDragging = false;
            const pos = handleSeek(upEvt.clientX);
            const dur = this.audio.duration || (this.currentTrack ? this.currentTrack.duration : 0);
            if (dur) this.audio.currentTime = pos * dur;
          }
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      });

      // Mobile Touch Scrubbing
      this.timeline.addEventListener('touchstart', (e) => {
        this.isDragging = true;
        if (e.touches && e.touches[0]) {
          handleSeek(e.touches[0].clientX);
        }
      }, { passive: true });

      this.timeline.addEventListener('touchmove', (e) => {
        if (this.isDragging && e.touches && e.touches[0]) {
          handleSeek(e.touches[0].clientX);
        }
      }, { passive: true });

      this.timeline.addEventListener('touchend', (e) => {
        if (this.isDragging) {
          this.isDragging = false;
          if (e.changedTouches && e.changedTouches[0]) {
            const pos = handleSeek(e.changedTouches[0].clientX);
            const dur = this.audio.duration || (this.currentTrack ? this.currentTrack.duration : 0);
            if (dur) this.audio.currentTime = pos * dur;
          }
        }
      });
    }

    if (this.volumeSlider) {
      this.audio.volume = parseFloat(this.volumeSlider.value || 0.85);
      this.volumeSlider.addEventListener('input', (e) => {
        this.audio.volume = parseFloat(e.target.value);
      });
    }
  }

  playTrack(track) {
    if (!track || !track.file) {
      if (window.toast) window.toast.show('Track file not found', 'error');
      return;
    }

    this.currentTrack = track;
    let fileUrl = track.file;

    // Cross-origin and relative path resolution
    if (!fileUrl.startsWith('http://') && !fileUrl.startsWith('https://')) {
      fileUrl = fileUrl.startsWith('/') ? fileUrl : `/${fileUrl}`;
    }

    this.audio.src = fileUrl;
    if (this.volumeSlider) {
      this.audio.volume = parseFloat(this.volumeSlider.value || 0.85);
    }

    if (this.titleEl) this.titleEl.textContent = track.title || 'Untitled Track';
    if (this.artistEl) {
      const source = track.source_type ? track.source_type.replace(/_/g, ' ').toUpperCase() : 'STUDIO';
      this.artistEl.textContent = source;
    }

    if (track.duration) {
      this.totalTimeEl.textContent = this.formatTime(track.duration);
    } else {
      this.totalTimeEl.textContent = '00:00';
    }
    this.currTimeEl.textContent = '00:00';
    this.progress.style.width = '0%';

    if (this.dock) {
      this.dock.classList.remove('hidden');
    }

    this.audio.play()
      .then(() => {
        this.updatePlayIcon(true);
      })
      .catch((err) => {
        console.warn('Audio auto-play prevented or failed:', err);
        this.updatePlayIcon(false);
      });
  }

  togglePlay() {
    if (this.audio.paused) {
      this.audio.play()
        .then(() => this.updatePlayIcon(true))
        .catch(err => console.warn('Play error:', err));
    } else {
      this.audio.pause();
      this.updatePlayIcon(false);
    }
  }

  updatePlayIcon(isPlaying) {
    if (!this.playBtn) return;
    this.playBtn.innerHTML = isPlaying
      ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>`
      : `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
    this.playBtn.setAttribute('aria-label', isPlaying ? 'Pause' : 'Play');
  }

  updateProgress() {
    const duration = this.audio.duration || (this.currentTrack ? this.currentTrack.duration : 0);
    if (!duration || isNaN(duration)) return;

    const percent = (this.audio.currentTime / duration) * 100;
    this.progress.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    this.currTimeEl.textContent = this.formatTime(this.audio.currentTime);
    this.totalTimeEl.textContent = this.formatTime(duration);
  }

  onEnded() {
    this.updatePlayIcon(false);
    this.progress.style.width = '0%';
    this.currTimeEl.textContent = '00:00';
  }

  formatTime(seconds) {
    if (isNaN(seconds) || seconds === null || seconds === undefined) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
}

window.player = new AudioPlayer();
