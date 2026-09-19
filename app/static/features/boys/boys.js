import { BoyService } from "./boys-data.js";
import { GENDER_LABELS, classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, badge, compact, emptyState, errorBlock,
  field, formValues, loadingBlock, skeletonTable, table,
} from "../../shared/components.js";
import { calcAge, debounce, escapeHtml } from "../../shared/utils.js";

export class BoysPage {
  constructor(app) {
    this.app = app;
    this.service = new BoyService(app.api);
    this.boys = [];
    this.search = "";
    this.flaggedOnly = false;
  }

  async mount(ctx) {
    this.className = ctx.params.className;
    const html = await this.app.partial("features/boys/boys.html");
    this.app.setView(html);

    document.querySelector("[data-crumb-class]").textContent = classLabel(this.className);
    document.querySelector("[data-crumb-class]").href = `#/class/${this.className}`;
    document.querySelector("[data-attendance-link]").href = `#/class/${this.className}/boys/attendance`;

    document.getElementById("add-boy").addEventListener("click", () => this.openForm());
    document.getElementById("boys-search").addEventListener(
      "input", debounce((e) => { this.search = e.target.value.trim().toLowerCase(); this.render(); }, 200)
    );
    document.getElementById("boys-flag-tabs").addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      this.flaggedOnly = btn.dataset.flag === "true";
      document.querySelectorAll("#boys-flag-tabs button").forEach((b) =>
        b.classList.toggle("active", b === btn));
      this.render();
    });

    await this.load();
  }

  async load() {
    const box = document.getElementById("boys-content");
    box.innerHTML = skeletonTable(6);
    try {
      const data = await this.service.list(this.className);
      this.boys = Array.isArray(data) ? data : [];
      this.render();
    } catch (err) {
      box.innerHTML = errorBlock(err.message, `<button class="btn btn-secondary" id="retry">Try again</button>`);
      document.getElementById("retry")?.addEventListener("click", () => this.load());
    }
  }

  filtered() {
    return this.boys.filter((b) => {
      if (this.flaggedOnly && !b.issue_flag) return false;
      if (!this.search) return true;
      const hay = `${b.boy_name || ""} ${b.phone || ""} ${b.address || ""}`.toLowerCase();
      return hay.includes(this.search);
    });
  }

  render() {
    const box = document.getElementById("boys-content");
    const rows = this.filtered();
    if (!rows.length) {
      box.innerHTML = this.boys.length
        ? emptyState("No boys match", "Try a different search.")
        : emptyState(
            "No boys found",
            "There are no boys registered in this class yet.",
            `<button class="btn btn-primary" id="empty-add">+ Add Boy</button>`
          );
      document.getElementById("empty-add")?.addEventListener("click", () => this.openForm());
      return;
    }
    box.innerHTML = table(
      ["Name", "Gender", "Age", "Phone", "Note", "Actions"],
      rows.map((b) => `
        <tr>
          <td><strong>${b.issue_flag ? `<span class="flag-dot" title="Flagged"></span>` : ""}${escapeHtml(b.boy_name)}</strong></td>
          <td>${escapeHtml(GENDER_LABELS[b.gender] || b.gender || "—")}</td>
          <td>${escapeHtml(calcAge(b.birth_date, b.age))}</td>
          <td>${escapeHtml(b.phone || "—")}</td>
          <td>${b.note
            ? `<span class="note-indicator" title="${escapeHtml(b.note)}">Has note</span>`
            : `<span class="muted">—</span>`}</td>
          <td class="cell-actions">
            <button class="btn-link" data-act="view" data-id="${b.id}">View</button>
            <button class="btn-link" data-act="edit" data-id="${b.id}">Edit</button>
            <button class="btn-link danger" data-act="del" data-id="${b.id}">Delete</button>
          </td>
        </tr>`).join("")
    );
    box.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const boy = this.boys.find((x) => x.id === btn.dataset.id);
        if (!boy) return;
        if (btn.dataset.act === "view") this.openView(boy);
        if (btn.dataset.act === "edit") this.openForm(boy);
        if (btn.dataset.act === "del") this.remove(boy);
      });
    });
  }

  openView(b) {
    const row = (k, v) =>
      `<div class="detail-row"><span>${k}</span><span>${v || "—"}</span></div>`;
    Modal.open({
      title: b.boy_name,
      sub: `${classLabel(this.className)}${b.issue_flag ? " • Flagged" : ""}`,
      body: `<div class="details">
        ${row("Gender", escapeHtml(GENDER_LABELS[b.gender] || b.gender || "—"))}
        ${row("Birth date", escapeHtml(b.birth_date || "—"))}
        ${row("Age", escapeHtml(calcAge(b.birth_date, b.age)))}
        ${row("Phone", escapeHtml(b.phone || "—"))}
        ${row("Phone 2", escapeHtml(b.phone_2 || "—"))}
        ${row("Address", escapeHtml(b.address || "—"))}
        ${row("Location", b.location ? `<a href="${escapeHtml(b.location)}" target="_blank" rel="noopener">Open map</a>` : "—")}
        ${row("Note", escapeHtml(b.note || "—"))}
      </div>`,
      actions: [
        { label: "Close" },
        { label: "Edit", kind: "btn-primary", onClick: ({ close }) => { close(); this.openForm(b); } },
      ],
    });
  }

  openForm(boy = null) {
    const isEdit = Boolean(boy);
    const v = boy || {};
    const body = document.createElement("form");
    body.id = "boy-form";
    body.innerHTML = `
      ${field({ name: "boy_name", label: "Full name", value: v.boy_name || "", required: true })}
      <div class="form-grid">
        ${field({ name: "gender", label: "Gender", value: v.gender || "m", options: [
          { value: "m", label: "Boy" }, { value: "f", label: "Girl" }] })}
        ${field({ name: "birth_date", label: "Birth date", type: "date", value: v.birth_date || "" })}
      </div>
      <div class="form-grid">
        ${field({ name: "age", label: "Age", type: "number", value: v.age ?? "", attrs: 'min="0" max="30"' })}
        ${field({ name: "phone", label: "Phone", type: "tel", value: v.phone || "" })}
      </div>
      ${field({ name: "phone_2", label: "Second phone", type: "tel", value: v.phone_2 || "" })}
      ${field({ name: "address", label: "Address", value: v.address || "" })}
      ${field({ name: "location", label: "Location (map link)", value: v.location || "" })}
      ${field({ name: "note", label: "Note", type: "textarea", value: v.note || "" })}
      <div class="field check-field">
        <label><input type="checkbox" class="check" name="issue_flag"${v.issue_flag ? " checked" : ""} /> Flag for follow-up</label>
      </div>`;
    Modal.open({
      title: isEdit ? "Edit boy" : "Add boy",
      sub: classLabel(this.className),
      body,
      actions: [
        { label: "Cancel" },
        {
          label: isEdit ? "Save changes" : "Add boy",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            const form = document.getElementById("boy-form");
            if (!form.reportValidity()) return;
            const values = formValues(form);
            values.issue_flag = form.issue_flag.checked;
            if (values.age !== "") values.age = Number(values.age);
            button.disabled = true;
            try {
              if (isEdit) {
                await this.service.update(boy.id, compact(values));
                Toast.success("Boy updated.");
              } else {
                await this.service.create({ ...compact(values), class_name: this.className });
                Toast.success("Boy added.");
              }
              close();
              await this.load();
            } catch (err) {
              Toast.error(err.message);
              button.disabled = false;
            }
          },
        },
      ],
    });
  }

  async remove(boy) {
    const ok = await Modal.confirm({
      title: "Delete boy?",
      message: `"${boy.boy_name}" will be permanently removed.`,
    });
    if (!ok) return;
    try {
      await this.service.remove(boy.id);
      Toast.success("Boy deleted.");
      await this.load();
    } catch (err) {
      Toast.error(err.message);
    }
  }
}
