/**
 * Authentication Module
 * Manages login, registration, token storage, and user profile state.
 */

class AuthManager {
  constructor() {
    this.currentUser = null;
    this.init();
  }

  async init() {
    this.bindEvents();
    if (window.api.isAuthenticated()) {
      await this.fetchUserProfile();
    } else {
      this.showAuthModal();
    }
  }

  bindEvents() {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const logoutBtn = document.getElementById('logout-btn');
    const toggleToRegister = document.getElementById('toggle-to-register');
    const toggleToLogin = document.getElementById('toggle-to-login');

    if (loginForm) {
      loginForm.addEventListener('submit', (e) => this.handleLogin(e));
    }

    if (registerForm) {
      registerForm.addEventListener('submit', (e) => this.handleRegister(e));
    }

    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => this.handleLogout());
    }

    if (toggleToRegister) {
      toggleToRegister.addEventListener('click', (e) => {
        e.preventDefault();
        document.getElementById('login-card').style.display = 'none';
        document.getElementById('register-card').style.display = 'block';
      });
    }

    if (toggleToLogin) {
      toggleToLogin.addEventListener('click', (e) => {
        e.preventDefault();
        document.getElementById('register-card').style.display = 'none';
        document.getElementById('login-card').style.display = 'block';
      });
    }
  }

  async handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const btn = document.getElementById('login-submit-btn');

    btn.disabled = true;
    btn.textContent = 'Authenticating...';

    try {
      const response = await window.api.post('/auth/login/', { email, password });
      const data = await response.json();

      if (response.ok) {
        window.api.setTokens(data.access, data.refresh);
        this.hideAuthModal();
        window.toast.show('Logged in successfully', 'success');
        await this.fetchUserProfile();
        window.library.loadTracks();
      } else {
        window.toast.show(data.detail || 'Invalid email or password', 'error');
      }
    } catch (err) {
      window.toast.show('Network error during login', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Sign In';
    }
  }

  async handleRegister(e) {
    e.preventDefault();
    const email = document.getElementById('reg-email').value;
    const username = document.getElementById('reg-username').value;
    const password = document.getElementById('reg-password').value;
    const password_confirm = document.getElementById('reg-password-confirm').value;
    const btn = document.getElementById('reg-submit-btn');

    btn.disabled = true;
    btn.textContent = 'Creating Account...';

    try {
      const response = await window.api.post('/auth/register/', {
        email,
        username,
        password,
        password_confirm,
      });
      const data = await response.json();

      if (response.ok) {
        window.toast.show('Account created! Logging you in...', 'success');
        // Auto-login
        const loginRes = await window.api.post('/auth/login/', { email, password });
        const loginData = await loginRes.json();
        if (loginRes.ok) {
          window.api.setTokens(loginData.access, loginData.refresh);
          this.hideAuthModal();
          await this.fetchUserProfile();
          window.library.loadTracks();
        }
      } else {
        const errorMsg = data.password || data.email || data.username || data.detail || 'Registration failed';
        window.toast.show(Array.isArray(errorMsg) ? errorMsg[0] : errorMsg, 'error');
      }
    } catch (err) {
      window.toast.show('Registration error', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Create Account';
    }
  }

  async fetchUserProfile() {
    try {
      const response = await window.api.get('/auth/me/');
      if (response.ok) {
        this.currentUser = await response.json();
        this.updateUserUI();
      }
    } catch (err) {
      console.error('Failed to fetch profile:', err);
    }
  }

  updateUserUI() {
    if (!this.currentUser) return;
    const nameEl = document.getElementById('user-display-name');
    const emailEl = document.getElementById('user-display-email');
    const avatarEl = document.getElementById('user-display-avatar');

    if (nameEl) nameEl.textContent = this.currentUser.username || 'User';
    if (emailEl) emailEl.textContent = this.currentUser.email || '';
    if (avatarEl) {
      avatarEl.textContent = (this.currentUser.username || 'U').charAt(0).toUpperCase();
    }
  }

  handleLogout() {
    window.api.clearTokens();
    this.currentUser = null;
    window.toast.show('Logged out', 'info');
    this.showAuthModal();
  }

  showAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) modal.classList.add('active');
  }

  hideAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) modal.classList.remove('active');
  }
}

window.auth = new AuthManager();
