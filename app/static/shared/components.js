import { escapeHtml } from "./utils.js";

function toastRoot() {
  return document.getElementById("toast-root");
}

export class Toast {
  static show(message, type = "") {
    const root = toastRoot();
    if (!root) return;
    const el = document.createElement("div");
    el.className = `toast${type ? ` toast-${type}` : ""}`;
    el.textContent = message;
    root.appendChild(el);
    setTimeout(() => el.remove(), 3600);
  }
  static success(message) {
    this.show(message, "success");
  }
  static error(message) {
    this.show(message, "error");
  }
}

export class Modal {
  static open({ title, sub = "", body = "", actions = [] }) {
    const root = document.getElementById("modal-root");
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true">
        <h2>${escapeHtml(title)}</h2>
        ${sub ? `<p class="modal-sub">${escapeHtml(sub)}</p>` : ""}
        <div class="modal-body"></div>
        <div class="modal-actions"></div>
      </div>`;
    const bodyEl = backdrop.querySelector(".modal-body");
    if (typeof body === "string") {
      bodyEl.innerHTML = body;
    } else if (body instanceof Node) {
      bodyEl.appendChild(body);
    }
    const actionsEl = backdrop.querySelector(".modal-actions");

    const close = () => {
      document.removeEventListener("keydown", onKey);
      backdrop.remove();
    };
    const onKey = (e) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    backdrop.addEventListener("mousedown", (e) => {
      if (e.target === backdrop) close();
    });

    for (const action of actions) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `btn ${action.kind || "btn-secondary"}`;
      btn.textContent = action.label;
      btn.addEventListener("click", async () => {
        try {
          if (action.onClick) await action.onClick({ close, button: btn, body: bodyEl });
          else close();
        } catch (err) {
          Toast.error(err.message || "Something went wrong.");
        }
      });
      actionsEl.appendChild(btn);
    }

    root.appendChild(backdrop);
    const firstInput = bodyEl.querySelector("input, select, textarea");
    if (firstInput) firstInput.focus();
    return { close, body: bodyEl };
  }

  static confirm({ title = "Are you sure?", message = "", confirmLabel = "Delete" }) {
    return new Promise((resolve) => {
      const { close } = this.open({
        title,
        body: `<p class="muted" style="margin:0">${escapeHtml(message)}</p>`,
        actions: [
          { label: "Cancel", onClick: () => { close(); resolve(false); } },
          {
            label: confirmLabel,
            kind: "btn-danger",
            onClick: () => { close(); resolve(true); },
          },
        ],
      });
      void close;
    });
  }

  static note({ title = "Note", value = "" }) {
    return new Promise((resolve) => {
      const body = document.createElement("div");
      body.innerHTML = `
        <div class="field">
          <textarea class="input" rows="4" maxlength="500">${escapeHtml(value)}</textarea>
        </div>`;
      const ta = body.querySelector("textarea");
      this.open({
        title,
        actions: [
          { label: "Cancel", onClick: ({ close }) => { close(); resolve(null); } },
          {
            label: "Save",
            kind: "btn-primary",
            onClick: ({ close }) => { close(); resolve(ta.value.trim()); },
          },
        ],
        body,
      });
    });
  }
}

export function table(headers, rowsHtml) {
  return `
    <div class="table-wrap">
      <table class="table">
        <thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>`;
}

export function emptyState(title, message, actionHtml = "") {
  return `
    <div class="empty-state">
      <h3>${escapeHtml(title)}</h3>
      <p style="margin:0 0 14px">${escapeHtml(message)}</p>
      ${actionHtml}
    </div>`;
}

export function loadingBlock(message = "Loading...") {
  return `<div class="loading-block" role="status">${escapeHtml(message)}</div>`;
}

export function skeletonTable(rows = 5) {
  return `<div class="table-wrap" aria-hidden="true">${"<div class='skeleton-row'></div>".repeat(rows)}</div>`;
}

export function errorBlock(message, retryHtml = "") {
  return `
    <div class="error-block">
      <h3>Something went wrong</h3>
      <p style="margin:0 0 14px">${escapeHtml(message || "Please try again.")}</p>
      ${retryHtml}
    </div>`;
}

export function badge(text, kind = "") {
  return `<span class="badge${kind ? ` badge-${kind}` : ""}">${escapeHtml(text)}</span>`;
}

export function field({ name, label, type = "text", value = "", required = false, hint = "", options = null, attrs = "" }) {
  const req = required ? " required" : "";
  let control;
  if (options) {
    control = `<select class="input" name="${name}"${req} ${attrs}>${options
      .map(
        (o) =>
          `<option value="${escapeHtml(o.value)}"${String(o.value) === String(value) ? " selected" : ""}>${escapeHtml(o.label)}</option>`
      )
      .join("")}</select>`;
  } else if (type === "textarea") {
    control = `<textarea class="input" name="${name}" rows="3"${req} ${attrs}>${escapeHtml(value)}</textarea>`;
  } else {
    control = `<input class="input" type="${type}" name="${name}" value="${escapeHtml(value)}"${req} ${attrs} />`;
  }
  return `
    <div class="field">
      <label>${escapeHtml(label)}${required ? " *" : ""}</label>
      ${control}
      ${hint ? `<div class="hint">${escapeHtml(hint)}</div>` : ""}
    </div>`;
}

export function formValues(form) {
  const data = {};
  new FormData(form).forEach((value, key) => {
    data[key] = typeof value === "string" ? value.trim() : value;
  });
  return data;
}

/** Drop empty-string values so PATCH sends only real changes. */
export function compact(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v === "" || v === null || v === undefined) continue;
    out[k] = v;
  }
  return out;
}
