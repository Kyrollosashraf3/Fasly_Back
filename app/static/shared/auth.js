import {
  MANAGER_ROLES,
  ROLES,
  ROLE_LABELS,
  setClassRows,
} from "./constants.js";

/**
 * Session + what this login may open.
 *
 * Class access is resolved once per session (see :meth:`syncClasses`) and
 * cached, so every other module can ask the question synchronously.
 *
 *   super_admin / admin  -> every class
 *   teacher              -> the class of his servant record
 *   user (boy)           -> the class of his boy record
 */
export class AuthService {
  constructor({ api, storage, onAuthChange }) {
    this.api = api;
    this.storage = storage;
    this.onAuthChange = onAuthChange;
    this._user = storage.getUser();
    this._classes = null; // [{id, name, grade_number, academic_year}]
  }

  async login(mail, password) {
    const token = await this.api.postForm("/auth/login", {
      username: mail.trim(),
      password,
    });
    this.storage.setToken(token.access_token);
    this._classes = null;
    const user = await this.me(true);
    await this.syncClasses();
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

  isManager() {
    const user = this.currentUser();
    return Boolean(user && MANAGER_ROLES.includes(user.role));
  }

  /** Kept for older callers: an amin of a class (or the super admin). */
  isAdmin() {
    return this.isManager();
  }

  isSuperAdmin() {
    const user = this.currentUser();
    return Boolean(user && user.role === ROLES.SUPER_ADMIN);
  }

  isServant() {
    const user = this.currentUser();
    return Boolean(user && user.role === ROLES.TEACHER);
  }

  isBoy() {
    const user = this.currentUser();
    return Boolean(user && user.role === ROLES.USER);
  }

  roleLabel(role) {
    return ROLE_LABELS[role] || role || "—";
  }

  /**
   * Load /classes and narrow it down to what this login may open.
   * Cached until logout or a fresh login.
   */
  async syncClasses(force = false) {
    if (this._classes && !force) return this._classes;
    const user = this.currentUser();
    if (!user) {
      this._setClasses([]);
      return this._classes;
    }

    let all = [];
    try {
      const rows = await this.api.get("/classes");
      all = Array.isArray(rows) ? rows : [];
    } catch {
      all = [];
    }

    if (this.isManager()) {
      this._setClasses(all);
      return this._classes;
    }

    let classId = null;
    try {
      if (user.role === ROLES.TEACHER && user.teacher_id) {
        const t = await this.api.get(`/teachers/${user.teacher_id}`);
        classId = t ? t.class_id : null;
      } else if (user.role === ROLES.USER && user.boy_id) {
        const b = await this.api.get(`/boys/${user.boy_id}`);
        classId = b ? b.class_id : null;
      }
    } catch {
      classId = null;
    }

    this._setClasses(
      classId === null ? [] : all.filter((c) => c.id === classId)
    );
    return this._classes;
  }

  _setClasses(rows) {
    this._classes = rows;
    setClassRows(rows);
  }

  /** Every class this login may open: [{id, name, ...}] (sync after login). */
  accessibleClasses() {
    return this._classes || [];
  }

  accessibleClassIds() {
    return this.accessibleClasses().map((c) => c.id);
  }

  canAccess(classId) {
    if (classId === null || classId === undefined || classId === "") return false;
    return this.accessibleClassIds().some((id) => String(id) === String(classId));
  }

  canWriteDirectory() {
    return this.isManager();
  }

  logout() {
    this._user = null;
    this._classes = null;
    setClassRows([]);
    this.storage.clearAll();
    if (this.onAuthChange) this.onAuthChange(null);
  }
}
