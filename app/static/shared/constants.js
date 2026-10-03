// The UI is served by the backend itself under /app, so the API lives on the
// SAME origin. Using window.location means PC (127.0.0.1) and phones on the
// same Wi-Fi (192.168.x.x) both work with zero config. Still overridable
// per-device via localStorage (fasly_api_base).
const _origin =
  (typeof window !== "undefined" && window.location && window.location.origin) ||
  "http://127.0.0.1:9001";

export const API_BASE_URL = _origin;

export const STORAGE_KEYS = {
  TOKEN: "fasly_token",
  USER: "fasly_user",
  API_BASE: "fasly_api_base",
};

export const ROLES = {
  SUPER_ADMIN: "super_admin",
  ADMIN: "admin",
  TEACHER: "teacher",
  USER: "user",
};

/** Roles that manage a class directory (boys / teachers / sheets). */
export const MANAGER_ROLES = [ROLES.SUPER_ADMIN, ROLES.ADMIN];

export const ROLE_LABELS = {
  super_admin: "أدمن عام",
  admin: "أمين فصل",
  teacher: "خادم",
  user: "ولد",
};

export const ROLE_OPTIONS = [
  { value: "user", label: "ولد (حسابه وحده)" },
  { value: "teacher", label: "خادم (مجموعته)" },
  { value: "admin", label: "أمين فصل (فصله)" },
  { value: "super_admin", label: "أدمن عام (كل الفصول)" },
];

export const GENDER = { MALE: "m", FEMALE: "f" };
export const GENDER_LABELS = { m: "ولد", f: "بنت" };
export const GENDER_OPTIONS = [
  { value: "m", label: "ولد" },
  { value: "f", label: "بنت" },
];

export const FOLLOW_STATUS = [
  { value: "call", label: "مكالمة" },
  { value: "visit", label: "زيارة منزل" },
  { value: "whatsapp", label: "واتساب" },
  { value: "no_answer", label: "لا يوجد رد" },
  { value: "other", label: "أخرى" },
];

export const FOLLOW_STATUS_LABELS = Object.fromEntries(
  FOLLOW_STATUS.map((s) => [s.value, s.label])
);

/** Grade-number fallback labels used before /classes has been loaded. */
export const CLASS_LABELS = {
  1: "الصف الأول",
  2: "الصف الثاني",
  3: "الصف الثالث",
  4: "الصف الرابع",
  5: "الصف الخامس",
  6: "الصف السادس",
};

// Populated by the class registry (shared/classes.js) after GET /classes.
let _classRows = [];

export function setClassRows(rows) {
  _classRows = Array.isArray(rows) ? rows : [];
}

export function getClassRows() {
  return _classRows;
}

/**
 * Accepts a class id, a `{id, name}` row, or a legacy "1".."6" string and
 * returns the Arabic label. Unknown ids fall back to the grade table.
 */
export function classLabel(value) {
  if (value && typeof value === "object") {
    return value.name || classLabel(value.id);
  }
  if (value === null || value === undefined || value === "") return "—";
  const row = _classRows.find((c) => String(c.id) === String(value));
  if (row) return row.name;
  return CLASS_LABELS[String(value)] || `صف ${value}`;
}
