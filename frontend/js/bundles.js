/**
 * Subliminal Playlist Maker Module
 * Features:
 * - Direct Multi-Select Checkbox Picker for bulk adding tracks
 * - YouTube-Style Drag-and-Drop Dynamic Track Reordering
 * - Instant Step-by-Step Up (▲) / Down (▼) Reorder buttons
 * - 1-Click Continuous Playlist Concatenation Export
 */

/**
 * Escapes HTML special characters to prevent XSS injection (H-5 security fix).
 */
function escapeHtmlBundles(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
class PlaylistMaker {
  constructor() {
    this.playlists = [];
    this.activePlaylistIdForAdd = null;
    this.draggedItemIndex = null;
    this.draggedPlaylistId = null;
    this.init();
  }

  init() {
    this.bindEvents();
    if (window.api && window.api.isAuthenticated()) {
      this.loadPlaylists();
    }
  }

  bindEvents() {
    const createPlaylistForm = document.getElementById('create-playlist-form');
    if (createPlaylistForm) {
      createPlaylistForm.addEventListener('submit', (e) => this.handleCreatePlaylist(e));
    }

    const selectAllBtn = document.getElementById('playlist-select-all-btn');
    const deselectAllBtn = document.getElementById('playlist-deselect-all-btn');
    const confirmAddBtn = document.getElementById('playlist-confirm-add-btn');
    const closePickerBtn = document.getElementById('btn-close-playlist-picker');

    if (selectAllBtn) {
      selectAllBtn.addEventListener('click', () => this.toggleAllCheckboxes(true));
    }

    if (deselectAllBtn) {
      deselectAllBtn.addEventListener('click', () => this.toggleAllCheckboxes(false));
    }

    if (confirmAddBtn) {
      confirmAddBtn.addEventListener('click', () => this.confirmAddSelectedTracks());
    }

    if (closePickerBtn) {
      closePickerBtn.addEventListener('click', () => this.closeTrackPickerModal());
    }
  }

  async loadData() {
    await this.loadPlaylists();
  }

  async loadPlaylists() {
    try {
      const response = await window.api.get('/bundles/playlists/');
      if (response.ok) {
        const data = await response.json();
        this.playlists = data.results || data;
        this.renderPlaylists();
      }
    } catch (err) {
      console.error('Error loading playlists:', err);
    }
  }

  renderPlaylists() {
    const container = document.getElementById('playlists-list-container');
    if (!container) return;

    if (this.playlists.length === 0) {
      container.innerHTML = `
        <div class="glass-card" style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 12px; opacity: 0.5;"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>
          <p style="font-size: 1.1rem; font-weight: 600; color: var(--text-primary);">No Playlists Created Yet</p>
          <p style="font-size: 0.85rem; margin-top: 4px;">Type a title above and click "Create Playlist" to start sequencing subliminals.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = this.playlists.map(pl => {
      const tracks = pl.tracks || [];
      return `
        <div class="glass-card playlist-card" style="margin-bottom: 24px; padding: 22px; border-left: 4px solid var(--accent-secondary);" data-playlist-id="${pl.id}">
          <!-- Playlist Header -->
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <h4 style="font-weight: 700; font-size: 1.2rem;">${escapeHtmlBundles(pl.title)}</h4>
                <span class="badge badge-tts" style="font-size: 0.72rem;">1-BY-1 SEQUENCE</span>
              </div>
              <p style="font-size: 0.84rem; color: var(--text-muted); margin-top: 4px;">
                ${tracks.length} Tracks in Sequence • Total Continuous Duration: <strong>${this.formatDuration(pl.total_duration)}</strong>
              </p>
            </div>

            <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
              <button class="btn btn-secondary btn-sm" onclick="window.bundles.openTrackPickerModal(${pl.id})" style="padding: 8px 14px; font-weight: 600;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
                + Add Tracks 
              </button>
              <button id="btn-export-playlist-${pl.id}" class="btn btn-primary btn-sm" onclick="window.bundles.exportPlaylistAudio(${pl.id}, this)" ${tracks.length === 0 ? 'disabled' : ''} style="padding: 8px 14px;" title="Merge all tracks in sequence into one single continuous audio file">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                Export Continuous Track
              </button>
              <button class="btn-icon" onclick="window.bundles.deletePlaylist(${pl.id})" style="width: 34px; height: 34px;" title="Delete Playlist">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>

          <!-- Sequenced Tracks Container (YouTube-style Reorderable) -->
          <div style="background: rgba(0,0,0,0.3); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.06);">
              <span style="font-size: 0.8rem; font-weight: 700; color: var(--text-accent); text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                Track Playback Order
              </span>
              <span style="font-size: 0.75rem; color: var(--text-muted);">
                <em>Drag handle (⠿) or use ▲ ▼ to reorder</em>
              </span>
            </div>

            ${tracks.length === 0 ? `
              <div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 0.88rem;">
                No tracks in this playlist yet. Click <strong style="color: var(--text-accent);">"+ Add Tracks "</strong> above to add subliminals.
              </div>
            ` : `
              <div class="playlist-sortable-list" id="sortable-list-${pl.id}" style="display: flex; flex-direction: column; gap: 8px;">
                ${tracks.map((t, idx) => `
                  <div class="playlist-track-row" 
                    draggable="true"
                    data-playlist-id="${pl.id}"
                    data-index="${idx}"
                    ondragstart="window.bundles.handleDragStart(event, ${pl.id}, ${idx})"
                    ondragover="window.bundles.handleDragOver(event)"
                    ondragenter="window.bundles.handleDragEnter(event)"
                    ondragleave="window.bundles.handleDragLeave(event)"
                    ondrop="window.bundles.handleDrop(event, ${pl.id}, ${idx})"
                    style="display: flex; align-items: center; justify-content: space-between; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 10px 16px; cursor: grab; transition: all 0.18s ease; user-select: none;">
                    
                    <!-- Drag Handle + Order Number + Title -->
                    <div style="display: flex; align-items: center; gap: 14px; overflow: hidden; flex: 1;">
                      <span class="drag-handle" style="color: var(--text-muted); font-size: 1.2rem; cursor: grab;" title="Drag to reorder">
                        ⠿
                      </span>
                      <span style="font-family: var(--font-mono); font-size: 0.88rem; font-weight: 700; color: var(--text-accent); min-width: 24px; text-align: center; background: rgba(139,92,246,0.15); border-radius: 4px; padding: 2px 6px;">
                        ${idx + 1}
                      </span>
                      <div style="overflow: hidden; flex: 1;">
                        <span style="font-size: 0.92rem; font-weight: 600; color: var(--text-primary); white-space: nowrap; text-overflow: ellipsis; display: block;">
                          ${escapeHtmlBundles(t.title) || 'Track'}
                        </span>
                        <div style="display: flex; align-items: center; gap: 8px; font-size: 0.76rem; color: var(--text-muted); margin-top: 2px;">
                          <span>${t.duration_display || '--:--'}</span>
                          <span>•</span>
                          <span class="badge badge-${escapeHtmlBundles(t.source_type)}" style="font-size: 0.68rem; padding: 1px 6px;">${escapeHtmlBundles(t.source_type)}</span>
                        </div>
                      </div>
                    </div>

                    <!-- Dynamic Up/Down Reorder Buttons + Delete -->
                    <div style="display: flex; align-items: center; gap: 6px; margin-left: 12px;">
                      <button class="btn btn-outline btn-sm" onclick="window.bundles.moveTrackStep(${pl.id}, ${idx}, -1)" 
                        ${idx === 0 ? 'disabled' : ''} style="padding: 4px 9px; font-size: 0.8rem; border-radius: 4px;" title="Move Up in Sequence">
                        ▲
                      </button>
                      <button class="btn btn-outline btn-sm" onclick="window.bundles.moveTrackStep(${pl.id}, ${idx}, 1)" 
                        ${idx === tracks.length - 1 ? 'disabled' : ''} style="padding: 4px 9px; font-size: 0.8rem; border-radius: 4px;" title="Move Down in Sequence">
                        ▼
                      </button>
                      <button class="btn-icon" onclick="window.bundles.removeTrackFromPlaylist(${pl.id}, ${t.id})" 
                        style="width: 30px; height: 30px; color: #ef4444; border-radius: 4px;" title="Remove from Sequence">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </button>
                    </div>
                  </div>
                `).join('')}
              </div>
            `}
          </div>
        </div>
      `;
    }).join('');
  }

  formatDuration(seconds) {
    if (!seconds) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  async handleCreatePlaylist(e) {
    e.preventDefault();
    const titleInput = document.getElementById('new-playlist-title');
    if (!titleInput) return;
    const title = titleInput.value.trim();
    if (!title) return;

    try {
      const response = await window.api.post('/bundles/playlists/', { title });
      if (response.ok || response.status === 201) {
        window.toast.show(`Playlist "${title}" created successfully!`, 'success');
        titleInput.value = '';
        await this.loadPlaylists();
        if (window.trackEvent) window.trackEvent('playlist_created', { title: title });
      } else {
        const errData = await response.json().catch(() => ({}));
        window.toast.show(errData.error || errData.detail || 'Failed to create playlist', 'error');
      }
    } catch (err) {
      console.error('Create playlist error:', err);
      window.toast.show('Error creating playlist', 'error');
    }
  }

  // --- Multi-Select Checkbox Modal ---

  async openTrackPickerModal(playlistId) {
    this.activePlaylistIdForAdd = playlistId;
    const modal = document.getElementById('playlist-picker-modal');
    const container = document.getElementById('playlist-picker-tracks-list');
    if (!modal || !container) return;

    // Ensure library tracks are loaded
    if (!window.library?.tracks || window.library.tracks.length === 0) {
      await window.library.loadTracks();
    }

    const availableTracks = window.library?.tracks || [];
    const playlist = this.playlists.find(p => p.id === playlistId);
    const existingTrackIds = new Set((playlist?.tracks || []).map(t => t.id));

    if (availableTracks.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 24px; color: var(--text-muted);">
          No tracks in library yet. Generate an affirmation or upload audio first.
        </div>
      `;
    } else {
      container.innerHTML = availableTracks.map(t => {
        const alreadyIn = existingTrackIds.has(t.id);
        return `
          <label style="display: flex; align-items: center; gap: 14px; background: var(--bg-card); border: 1px solid ${alreadyIn ? 'rgba(139, 92, 246, 0.4)' : 'var(--border-subtle)'}; border-radius: var(--radius-sm); padding: 12px 16px; cursor: pointer; transition: all 0.2s;">
            <input type="checkbox" value="${t.id}" class="playlist-picker-checkbox" ${alreadyIn ? 'disabled checked' : ''} style="width: 20px; height: 20px; accent-color: var(--accent-primary); cursor: pointer;">
            <div style="flex: 1; overflow: hidden;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-weight: 600; font-size: 0.95rem; color: var(--text-primary);">${escapeHtmlBundles(t.title)}</span>
                ${alreadyIn ? '<span class="badge badge-mixed" style="font-size: 0.65rem;">Already in Playlist</span>' : ''}
              </div>
              <span style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px; display: block;">${t.duration_display || '--:--'} • Source: ${escapeHtmlBundles(t.source_type)}</span>
            </div>
          </label>
        `;
      }).join('');
    }

    modal.classList.add('active');
  }

  closeTrackPickerModal() {
    const modal = document.getElementById('playlist-picker-modal');
    if (modal) modal.classList.remove('active');
    this.activePlaylistIdForAdd = null;
  }

  toggleAllCheckboxes(checked) {
    const checkboxes = document.querySelectorAll('.playlist-picker-checkbox:not(:disabled)');
    checkboxes.forEach(cb => cb.checked = checked);
  }

  async confirmAddSelectedTracks() {
    if (!this.activePlaylistIdForAdd) return;

    const checkboxes = document.querySelectorAll('.playlist-picker-checkbox:checked:not(:disabled)');
    const selectedTrackIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

    if (selectedTrackIds.length === 0) {
      window.toast.show('Please check at least one track box to add', 'info');
      return;
    }

    const playlistId = this.activePlaylistIdForAdd;
    const confirmBtn = document.getElementById('playlist-confirm-add-btn');
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Adding Selected Tracks...';
    }

    try {
      for (const trackId of selectedTrackIds) {
        await window.api.post(`/bundles/playlists/${playlistId}/tracks/`, { track_id: trackId });
      }

      window.toast.show(`Added ${selectedTrackIds.length} tracks to playlist sequence!`, 'success');
      this.closeTrackPickerModal();
      await this.loadPlaylists();
      if (window.trackEvent) window.trackEvent('playlist_tracks_added', { count: selectedTrackIds.length });
    } catch (err) {
      window.toast.show('Error adding tracks to playlist', 'error');
    } finally {
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Add Selected Tracks to Playlist';
      }
    }
  }

  // --- YouTube-Style Dynamic Drag-and-Drop Reordering ---

  handleDragStart(e, playlistId, index) {
    this.draggedItemIndex = index;
    this.draggedPlaylistId = playlistId;
    e.dataTransfer.effectAllowed = 'move';
    e.currentTarget.style.opacity = '0.4';
    e.currentTarget.classList.add('is-dragging');
  }

  handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }

  handleDragEnter(e) {
    e.preventDefault();
    const row = e.currentTarget.closest('.playlist-track-row');
    if (row && !row.classList.contains('is-dragging')) {
      row.style.border = '2px dashed var(--accent-primary)';
      row.style.background = 'rgba(139, 92, 246, 0.15)';
    }
  }

  handleDragLeave(e) {
    const row = e.currentTarget.closest('.playlist-track-row');
    if (row && !row.classList.contains('is-dragging')) {
      row.style.border = '1px solid var(--border-subtle)';
      row.style.background = 'var(--bg-card)';
    }
  }

  async handleDrop(e, playlistId, dropIndex) {
    e.preventDefault();
    const fromIndex = this.draggedItemIndex;
    this.draggedItemIndex = null;

    if (fromIndex === null || fromIndex === undefined || fromIndex === dropIndex) {
      this.renderPlaylists();
      return;
    }

    const playlist = this.playlists.find(p => p.id === playlistId);
    if (!playlist || !playlist.tracks) return;

    // Reorder tracks array
    const updatedTracks = [...playlist.tracks];
    const [movedItem] = updatedTracks.splice(fromIndex, 1);
    updatedTracks.splice(dropIndex, 0, movedItem);

    playlist.tracks = updatedTracks;
    this.renderPlaylists();

    // Persist reordered sequence to server
    const trackOrder = updatedTracks.map(t => t.id);
    try {
      const response = await window.api.patch(`/bundles/playlists/${playlistId}/reorder/`, {
        track_order: trackOrder
      });

      if (response.ok) {
        window.toast.show('Sequence order dynamically updated!', 'success');
      } else {
        const data = await response.json();
        window.toast.show(data.error || 'Reorder failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error saving reordered sequence', 'error');
    }
  }

  // Step-by-step Move (▲ / ▼)
  async moveTrackStep(playlistId, currentIndex, direction) {
    const playlist = this.playlists.find(p => p.id === playlistId);
    if (!playlist || !playlist.tracks) return;

    const newIndex = currentIndex + direction;
    if (newIndex < 0 || newIndex >= playlist.tracks.length) return;

    const updatedTracks = [...playlist.tracks];
    const temp = updatedTracks[currentIndex];
    updatedTracks[currentIndex] = updatedTracks[newIndex];
    updatedTracks[newIndex] = temp;

    playlist.tracks = updatedTracks;
    this.renderPlaylists();

    const trackOrder = updatedTracks.map(t => t.id);
    try {
      const response = await window.api.patch(`/bundles/playlists/${playlistId}/reorder/`, {
        track_order: trackOrder
      });

      if (response.ok) {
        window.toast.show('Sequence order updated!', 'success');
      } else {
        const data = await response.json();
        window.toast.show(data.error || 'Reorder failed', 'error');
      }
    } catch (err) {
      window.toast.show('Error saving sequence order', 'error');
    }
  }

  async removeTrackFromPlaylist(playlistId, trackId) {
    try {
      const response = await window.api.delete(`/bundles/playlists/${playlistId}/tracks/${trackId}/`);
      if (response.ok) {
        window.toast.show('Track removed from sequence', 'success');
        await this.loadPlaylists();
      }
    } catch (err) {
      window.toast.show('Error removing track', 'error');
    }
  }

  async exportPlaylistAudio(playlistId, triggerBtn) {
    const btn = triggerBtn || document.getElementById(`btn-export-playlist-${playlistId}`);
    const originalContent = btn ? btn.innerHTML : '';

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `
        <span style="display:inline-block; width:13px; height:13px; border:2px solid #ffffff; border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite; margin-right:6px; vertical-align:middle;"></span>
        Merging Track...
      `;
    }

    try {
      window.toast.show('Merging playlist tracks into continuous audio file. Please wait...', 'info', 7000);
      const response = await window.api.get(`/bundles/playlists/${playlistId}/export/`);
      let data = null;
      try {
        data = await response.json();
      } catch (parseErr) {
        data = null;
      }

      if (response.ok && data) {
        window.toast.show('Continuous playlist track exported and saved to library!', 'success');
        if (window.library?.loadTracks) await window.library.loadTracks();
        if (window.player?.playTrack) window.player.playTrack(data);
        if (window.trackEvent) window.trackEvent('playlist_exported', { title: data.title });
      } else {
        const errorMsg = data?.error || data?.detail || data?.message || (response.status === 401 ? 'Please sign in to export playlist' : 'Export failed');
        window.toast.show(errorMsg, 'error', 6000);
      }
    } catch (err) {
      console.error('Export playlist audio error:', err);
      window.toast.show('Error exporting playlist audio. Please check connection.', 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalContent;
      }
    }
  }

  async deletePlaylist(playlistId) {
    if (!confirm('Are you sure you want to delete this playlist?')) return;
    try {
      const response = await window.api.delete(`/bundles/playlists/${playlistId}/`);
      if (response.ok || response.status === 204) {
        window.toast.show('Playlist deleted', 'success');
        await this.loadPlaylists();
      }
    } catch (err) {
      window.toast.show('Error deleting playlist', 'error');
    }
  }
}

window.bundles = new PlaylistMaker();
