export class ApiError extends Error {
  constructor(status, message, fields = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

function formatDetail(detail) {
  if (!detail) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (!first) return "Invalid request. Please check your input.";
    if (typeof first === "string") return first;
    const loc = Array.isArray(first.loc)
      ? first.loc.filter((p) => p !== "body").join(".")
      : "";
    const msg = first.msg || "Invalid value";
    return loc ? `${loc}: ${msg}` : msg;
  }
  if (typeof detail === "object") return detail.msg || JSON.stringify(detail);
  return String(detail);
}

const FRIENDLY = {
  400: "Invalid request. Please check your input.",
  401: "Your session has expired. Please log in again.",
  403: "You do not have permission to do that.",
  404: "Record not found. It may have been deleted.",
  422: "Some fields are invalid. Please review the form.",
  429: "Too many requests. Please wait a moment and try again.",
  500: "Server error. Please try again later.",
};

export class ApiClient {
  constructor({ getBaseUrl, getToken, onUnauthorized }) {
    this.getBaseUrl = getBaseUrl;
    this.getToken = getToken;
    this.onUnauthorized = onUnauthorized;
  }

  buildUrl(path, query) {
    const base = (this.getBaseUrl() || "").replace(/\/$/, "");
    const url = new URL(base + path);
    if (query) {
      for (const [key, value] of Object.entries(query)) {
        if (value === null || value === undefined || value === "") continue;
        url.searchParams.append(key, String(value));
      }
    }
    return url.toString();
  }

  async request(method, path, { query = null, body = null, form = null } = {}) {
    const headers = {};
    const token = this.getToken ? this.getToken() : null;
    if (token) headers["Authorization"] = `Bearer ${token}`;

    let payload = null;
    if (form) {
      payload = new URLSearchParams();
      for (const [key, value] of Object.entries(form)) {
        payload.append(key, value);
      }
      headers["Content-Type"] = "application/x-www-form-urlencoded";
    } else if (body !== null && body !== undefined) {
      payload = JSON.stringify(body);
      headers["Content-Type"] = "application/json";
    }

    let res;
    try {
      res = await fetch(this.buildUrl(path, query), {
        method,
        headers,
        body: payload,
      });
    } catch {
      throw new ApiError(0, "Cannot reach the server. Check your connection.");
    }
    return this.handleResponse(res);
  }

  async upload(path, file, fieldName = "file") {
    const headers = {};
    const token = this.getToken ? this.getToken() : null;
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const form = new FormData();
    form.append(fieldName, file, file.name);

    let res;
    try {
      res = await fetch(this.buildUrl(path), { method: "POST", headers, body: form });
    } catch {
      throw new ApiError(0, "Cannot reach the server. Check your connection.");
    }
    return this.handleResponse(res);
  }

  async handleResponse(res) {

    if (res.status === 204) return null;

    let data = null;
    const text = await res.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = null;
      }
    }

    if (res.ok) return data;

    if (res.status === 401 && this.onUnauthorized) {
      this.onUnauthorized();
    }
    const detail = data && data.detail !== undefined ? data.detail : null;
    const message =
      (typeof detail === "string" && detail) ||
      FRIENDLY[res.status] ||
      formatDetail(detail) ||
      `Request failed (${res.status})`;
    throw new ApiError(
      res.status,
      res.status === 422 ? formatDetail(detail) : message,
      res.status === 422 ? detail : null
    );
  }

  get(path, query) {
    return this.request("GET", path, { query });
  }
  post(path, body) {
    return this.request("POST", path, { body });
  }
  postForm(path, form) {
    return this.request("POST", path, { form });
  }
  patch(path, body) {
    return this.request("PATCH", path, { body });
  }
  delete(path) {
    return this.request("DELETE", path);
  }
}
