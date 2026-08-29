/**
 * Application Master Controller
 * Handles Toast notifications, Tab navigation, Theme Toggle (Dark/Light),
 * and Global initialization.
 */

class ToastManager {
  constructor() {
    this.container = document.getElementById('toast-container');
  }

  show(message, type = 'info', duration = 3500) {
    if (!this.container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = '';
    if (type === 'success') {
      icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
    } else if (type === 'error') {
      icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
    } else {
      icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `
      ${icon}
      <span style="font-size: 0.88rem; font-weight: 500;">${message}</span>
    `;

    this.container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
}

window.toast = new ToastManager();

// --- Theme Manager (Dark / Light Edition) ---
class ThemeManager {
  constructor() {
    this.currentTheme = localStorage.getItem('sublivra_theme') || 'dark';
    this.init();
  }

  init() {
    this.applyTheme(this.currentTheme);
    const toggleBtns = document.querySelectorAll('.btn-theme-toggle');
    toggleBtns.forEach(btn => {
      btn.addEventListener('click', () => this.toggleTheme());
    });
  }

  applyTheme(theme) {
    const html = document.documentElement;
    if (theme === 'light') {
      html.classList.remove('dark');
      html.classList.add('light');
    } else {
      html.classList.remove('light');
      html.classList.add('dark');
    }
    localStorage.setItem('sublivra_theme', theme);
    this.currentTheme = theme;
    this.updateToggleIcon();
  }

  toggleTheme() {
    const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
    this.applyTheme(newTheme);
    window.toast.show(`Switched to ${newTheme === 'dark' ? 'Dark Edition' : 'Light Edition'}`, 'info', 2000);
  }

  updateToggleIcon() {
    const icons = document.querySelectorAll('.theme-toggle-icon');
    icons.forEach(icon => {
      icon.textContent = this.currentTheme === 'dark' ? 'light_mode' : 'dark_mode';
    });
  }
}

window.theme = new ThemeManager();

document.addEventListener('DOMContentLoaded', () => {
  // Tab Routing
  const tabButtons = document.querySelectorAll('.nav-item button');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const headingTitle = document.getElementById('view-heading-title');
  const headingDesc = document.getElementById('view-heading-desc');

  const titles = {
    library: { title: 'Audio Library', desc: 'Browse, manage, and play your generated, uploaded, and imported tracks' },
    tts: { title: 'Make Your Own Sub', desc: 'Import background music from YouTube/device, generate neural affirmations, speed them up, and download your complete subliminal' },
    editor: { title: 'Audio Studio Editor', desc: 'Trim, speed-shift, fade, and normalize your audio non-destructively' },
    mixer: { title: 'Subliminal Bundles', desc: 'Bundle multiple subliminals together to play all at the exact same time' },
    bundles: { title: 'Playlist Maker', desc: 'Sequence multiple subliminals one by one into a single continuous track' },
  };

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabKey = btn.dataset.tab;
      if (!tabKey) return;

      tabButtons.forEach(b => b.closest('.nav-item').classList.remove('active'));
      btn.closest('.nav-item').classList.add('active');

      tabPanes.forEach(p => p.classList.remove('active'));
      const activePane = document.getElementById(`tab-${tabKey}`);
      if (activePane) activePane.classList.add('active');

      if (titles[tabKey]) {
        headingTitle.textContent = titles[tabKey].title;
        headingDesc.textContent = titles[tabKey].desc;
      }

      if (tabKey === 'bundles' && window.bundles) {
        window.bundles.loadData();
      }
    });
  });

  // Initial load
  if (window.api.isAuthenticated()) {
    window.library.loadTracks();
    if (window.bundles) {
      window.bundles.loadData();
    }
  }
});
