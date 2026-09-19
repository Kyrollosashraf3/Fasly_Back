import { CLASSES, ROLES } from "./constants.js";

export class AuthService {
  constructor({ api, storage, onAuthChange }) {
    this.api = api;
    this.storage = storage;
    this.onAuthChange = onAuthChange;
    this._user = storage.getUser();
  }

  async login(mail, password) {
    const token = await this.api.postForm("/auth/login", {
      username: mail.trim(),
      password,
    });
    this.storage.setToken(token.access_token);
    const user = await this.me(true);
    if (this.onAuthChange) this.onAuthChange(user);
    return user;
  }

  async me(refresh = false) {
    if (this._user && !refresh) return this._user;
    const user = await this.api.get("/auth/me");
    this._user = user;
    this.storage.setUser(user);
    return user;
  }

  currentUser() {
    return this._user || this.storage.getUser();
  }

  isAuthenticated() {
    return Boolean(this.storage.getToken());
  }

  isAdmin() {
    const user = this.currentUser();
    return user && user.role === ROLES.ADMIN;
  }

  /** Classes this user may open. Admin: all. User: only the assigned class. */
  accessibleClasses() {
    const user = this.currentUser();
    if (!user) return [];
    if (user.role === ROLES.ADMIN) return [...CLASSES];
    if (user.class_name && CLASSES.includes(String(user.class_name))) {
      return [String(user.class_name)];
    }
    return [...CLASSES];
  }

  canAccess(className) {
    return this.accessibleClasses().includes(String(className));
  }

  logout() {
    this._user = null;
    this.storage.clearAll();
    if (this.onAuthChange) this.onAuthChange(null);
  }
}
