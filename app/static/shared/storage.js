import { API_BASE_URL, STORAGE_KEYS } from "./constants.js";

function read(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    if (value === null || value === undefined) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, value);
    }
  } catch {
    /* storage unavailable — app still works for the session */
  }
}

export class Storage {
  getToken() {
    return read(STORAGE_KEYS.TOKEN);
  }
  setToken(token) {
    write(STORAGE_KEYS.TOKEN, token);
  }
  clearToken() {
    write(STORAGE_KEYS.TOKEN, null);
  }

  getUser() {
    const raw = read(STORAGE_KEYS.USER);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }
  setUser(user) {
    write(STORAGE_KEYS.USER, user ? JSON.stringify(user) : null);
  }

  getApiBase() {
    return read(STORAGE_KEYS.API_BASE) || API_BASE_URL;
  }
  setApiBase(url) {
    write(STORAGE_KEYS.API_BASE, url || null);
  }

  clearAll() {
    this.clearToken();
    this.setUser(null);
  }
}

export const storage = new Storage();
