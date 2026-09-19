// Backend lives on the SAME host, port 9001 (single-server deploy: UI is
// served from the backend itself under /app). Using the page's own hostname
// means PC (127.0.0.1) and phones on the same Wi-Fi (192.168.x.x) both work
// with zero config. Still overridable per-device via storage (fasly_api_base).
const _host = (typeof window !== "undefined" && window.location.hostname) || "127.0.0.1";
const _protocol = (typeof window !== "undefined" && window.location.protocol) || "http:";
export const API_BASE_URL = `${_protocol}//${_host}:9001`;

export const STORAGE_KEYS = {
  TOKEN: "fasly_token",
  USER: "fasly_user",
  API_BASE: "fasly_api_base",
};

export const CLASSES = ["1", "2", "3", "4", "5", "6"];

export const CLASS_LABELS = {
  1: "Grade 1",
  2: "Grade 2",
  3: "Grade 3",
  4: "Grade 4",
  5: "Grade 5",
  6: "Grade 6",
};

export const ROLES = {
  ADMIN: "admin",
  USER: "user",
};

export const ATTEND = {
  YES: "y",
  NO: "n",
};

export const GENDER = {
  MALE: "m",
  FEMALE: "f",
};

export const GENDER_LABELS = { m: "Boy", f: "Girl" };

export const FOLLOW_STATUS = [
  { value: "call", label: "Call" },
  { value: "visit", label: "Visit" },
  { value: "no answer", label: "No Answer" },
  { value: "other", label: "Other" },
];

export function classLabel(className) {
  return CLASS_LABELS[String(className)] || `Grade ${className}`;
}
