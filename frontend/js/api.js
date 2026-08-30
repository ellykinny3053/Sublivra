/**
 * Sublivra API Client
 * Manages JWT tokens, automatic refresh, error handling, and requests.
 */

// Dynamic API Base URL: auto-detects localhost vs production Koyeb backend
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE = isLocal 
  ? 'http://127.0.0.1:8000/api' 
  : (window.SUBLIVRA_API_URL || 'https://sublivra-api.koyeb.app/api');

class ApiClient {
  constructor() {
    this.accessToken = localStorage.getItem('sublivra_access_token') || null;
    this.refreshToken = localStorage.getItem('sublivra_refresh_token') || null;
  }

  setTokens(access, refresh) {
    this.accessToken = access;
    this.refreshToken = refresh;
    if (access) localStorage.setItem('sublivra_access_token', access);
    if (refresh) localStorage.setItem('sublivra_refresh_token', refresh);
  }

  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('sublivra_access_token');
    localStorage.removeItem('sublivra_refresh_token');
  }

  isAuthenticated() {
    return !!this.accessToken;
  }

  async refreshAuthToken() {
    if (!this.refreshToken) {
      this.clearTokens();
      return false;
    }

    try {
      const response = await fetch(`${API_BASE}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: this.refreshToken }),
      });

      if (response.ok) {
        const data = await response.json();
        this.setTokens(data.access, this.refreshToken);
        return true;
      } else {
        this.clearTokens();
        return false;
      }
    } catch (err) {
      this.clearTokens();
      return false;
    }
  }

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
    const headers = options.headers || {};

    if (this.accessToken && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    let response = await fetch(url, { ...options, headers });

    // Handle Token Expiry
    if (response.status === 401 && this.refreshToken) {
      const refreshed = await this.refreshAuthToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.accessToken}`;
        response = await fetch(url, { ...options, headers });
      }
    }

    return response;
  }

  async get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }

  async post(endpoint, body) {
    return this.request(endpoint, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  async patch(endpoint, body) {
    return this.request(endpoint, {
      method: 'PATCH',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  async delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
}

window.api = new ApiClient();
