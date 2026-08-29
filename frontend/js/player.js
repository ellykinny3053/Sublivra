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
    this.init();
  }

  init() {
    this.playBtn.addEventListener('click', () => this.togglePlay());
    if (this.downloadBtn) {
      this.downloadBtn.addEventListener('click', () => {
        if (this.currentTrack && window.library) {
          window.library.downloadTrack(this.currentTrack);
        }
      });
    }
    this.audio.addEventListener('timeupdate', () => this.updateProgress());
    this.audio.addEventListener('ended', () => this.onEnded());
    this.audio.addEventListener('loadedmetadata', () => {
      this.totalTimeEl.textContent = this.formatTime(this.audio.duration);
    });

    this.timeline.addEventListener('click', (e) => {
      const rect = this.timeline.getBoundingClientRect();
      const pos = (e.clientX - rect.left) / rect.width;
      if (this.audio.duration) {
        this.audio.currentTime = pos * this.audio.duration;
      }
    });

    this.volumeSlider.addEventListener('input', (e) => {
      this.audio.volume = parseFloat(e.target.value);
    });
  }

  playTrack(track) {
    this.currentTrack = track;
    const fileUrl = track.file.startsWith('http') ? track.file : `http://127.0.0.1:8000${track.file}`;
    this.audio.src = fileUrl;
    this.titleEl.textContent = track.title;
    this.artistEl.textContent = track.source_type ? track.source_type.toUpperCase() : 'AUDIO';
    this.dock.classList.remove('hidden');

    this.audio.play()
      .then(() => {
        this.updatePlayIcon(true);
      })
      .catch((err) => {
        console.error('Audio play error:', err);
      });
  }

  togglePlay() {
    if (this.audio.paused) {
      this.audio.play();
      this.updatePlayIcon(true);
    } else {
      this.audio.pause();
      this.updatePlayIcon(false);
    }
  }

  updatePlayIcon(isPlaying) {
    this.playBtn.innerHTML = isPlaying
      ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>`
      : `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
  }

  updateProgress() {
    if (!this.audio.duration) return;
    const percent = (this.audio.currentTime / this.audio.duration) * 100;
    this.progress.style.width = `${percent}%`;
    this.currTimeEl.textContent = this.formatTime(this.audio.currentTime);
  }

  onEnded() {
    this.updatePlayIcon(false);
    this.progress.style.width = '0%';
  }

  formatTime(seconds) {
    if (isNaN(seconds) || seconds === null) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
}

window.player = new AudioPlayer();
