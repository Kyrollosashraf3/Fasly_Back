import { BoyService } from "../boys/boys-data.js";
import { TeacherService } from "../teachers/teachers-data.js";
import { FOLLOW_STATUS, classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, badge, emptyState, errorBlock, skeletonTable, table,
} from "../../shared/components.js";
import { escapeHtml, formatDate, lastFridayISO } from "../../shared/utils.js";

/** Data-access layer for weekly follow-ups. */
export class FollowUpService {
  constructor(api) {
    this.api = api;
  }

  list(className, { teacherId = null, boyId = null, actionDate = null } = {}) {
    return this.api.get("/follow-ups", {
      class_name: className,
      teacher_id: teacherId,
      boy_id: boyId,
      action_date: actionDate,
    });
  }

  create(data) {
    return this.api.post("/follow-ups", data);
  }

  update(recordId, data) {
    return this.api.patch(`/follow-ups/${recordId}`, data);
  }

  remove(recordId) {
    return this.api.delete(`/follow-ups/${recordId}`);
  }
}

const STATUS_BADGE = { call: "", visit: "yellow", "no answer": "red", other: "green" };

export class FollowUpPage {
  constructor(app) {
    this.app = app;
    this.service = new FollowUpService(app.api);
    this.boys = new BoyService(app.api);
    this.teachers = new TeacherService(app.api);
    this.allBoys = [];
    this.allTeachers = [];
    this.existing = new Map(); // boy_id -> record (for selected teacher+date)
    this.draft = new Map(); // boy_id -> { status: ''|..., note }
    this.search = "";
    this.historyDate = "";
  }

  async mount(ctx) {
    this.className = ctx.params.className;
    this.teacherId = "";
    this.date = lastFridayISO();
    const html = await this.app.partial("features/follow-up/follow-up.html");
    this.app.setView(html);

    document.querySelector("[data-crumb-class]").textContent = classLabel(this.className);
    document.querySelector("[data-crumb-class]").href = `#/class/${this.className}`;

    this.box = document.getElementById("fu-content");
    this.histBox = document.getElementById("fu-history");

    document.getElementById("fu-date").value = this.date;
    document.getElementById("fu-date").addEventListener("change", async (e) => {
      this.date = e.target.value;
      await this.reloadRows();
    });
    document.getElementById("fu-teacher").addEventListener("change", async (e) => {
      this.teacherId = e.target.value;
      await this.reloadRows();
    });
    document.getElementById("fu-search").addEventListener("input", (e) => {
      this.search = e.target.value.trim().toLowerCase();
      this.renderRows();
    });
    document.getElementById("fu-save").addEventListener("click", () => this.save());
    document.getElementById("fu-hist-date").addEventListener("change", async (e) => {
      this.historyDate = e.target.value;
      await this.reloadHistory();
    });
    document.getElementById("fu-hist-clear").addEventListener("click", async () => {
      this.historyDate = "";
      document.getElementById("fu-hist-date").value = "";
      await this.reloadHistory();
    });

    await this.loadBase();
  }

  async loadBase() {
    this.box.innerHTML = skeletonTable(6);
    try {
      const [boys, teachers] = await Promise.all([
        this.boys.list(this.className),
        this.teachers.list(this.className),
      ]);
      this.allBoys = Array.isArray(boys) ? boys : [];
      this.allTeachers = Array.isArray(teachers) ? teachers : [];
      const sel = document.getElementById("fu-teacher");
      sel.innerHTML =
        `<option value="">Select teacher...</option>` +
        this.allTeachers.map((t) => `<option value="${t.id}">${escapeHtml(t.teacher_name)}</option>`).join("");
      await this.reloadRows();
      await this.reloadHistory();
    } catch (err) {
      this.box.innerHTML = errorBlock(err.message);
    }
  }

  async reloadRows() {
    if (!this.teacherId || !this.date || !this.allBoys.length) {
      this.box.innerHTML = emptyState(
        "Select a teacher and date",
        "Choose the teacher and week date above to log follow-ups."
      );
      document.getElementById("fu-summary").hidden = true;
      return;
    }
    this.box.innerHTML = skeletonTable(6);
    try {
      const records = await this.service.list(this.className, {
        teacherId: this.teacherId,
        actionDate: this.date,
      });
      this.existing = new Map((Array.isArray(records) ? records : []).map((r) => [r.boy_id, r]));
      this.draft = new Map(
        this.allBoys.map((b) => {
          const rec = this.existing.get(b.id);
          return [b.id, { status: rec?.status || "", note: rec?.note || "" }];
        })
      );
      this.renderRows();
      document.getElementById("fu-summary").hidden = false;
    } catch (err) {
      this.box.innerHTML = errorBlock(err.message);
    }
  }

  renderRows() {
    const rows = this.allBoys.filter((b) =>
      !this.search || `${b.boy_name || ""}`.toLowerCase().includes(this.search));
    if (!rows.length) {
      this.box.innerHTML = emptyState("No boys found", "There are no boys in this class yet.");
      return;
    }
    this.box.innerHTML = table(
      ["Boy", "Follow Up", "Note"],
      rows.map((b) => {
        const d = this.draft.get(b.id) || { status: "", note: "" };
        return `<tr>
          <td><strong>${escapeHtml(b.boy_name)}</strong></td>
          <td>
            <select class="input fu-status" data-id="${b.id}" aria-label="Follow up method">
              <option value="">—</option>
              ${FOLLOW_STATUS.map((s) =>
                `<option value="${s.value}"${d.status === s.value ? " selected" : ""}>${s.label}</option>`).join("")}
            </select>
          </td>
          <td><button class="btn-link" data-note="${b.id}">${d.note ? "&#9998; *" : "&#9998;"}</button></td>
        </tr>`;
      }).join("")
    );
    this.box.querySelectorAll(".fu-status").forEach((sel) => {
      sel.addEventListener("change", () => {
        this.draft.get(sel.dataset.id).status = sel.value;
        this.updateCount();
      });
    });
    this.box.querySelectorAll("[data-note]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const d = this.draft.get(btn.dataset.note);
        const boy = this.allBoys.find((b) => b.id === btn.dataset.note);
        const value = await Modal.note({ title: `Note — ${boy?.boy_name || ""}`, value: d.note });
        if (value === null) return;
        d.note = value;
        btn.innerHTML = value ? "&#9998; *" : "&#9998;";
        this.updateCount();
      });
    });
    this.updateCount();
  }

  updateCount() {
    let n = 0;
    for (const d of this.draft.values()) {
      if (d.status) n += 1;
    }
    document.getElementById("fu-count").textContent =
      `${n} follow-up${n === 1 ? "" : "s"} • ${formatDate(this.date)}`;
  }

  async save() {
    const teacher = this.allTeachers.find((t) => t.id === this.teacherId);
    if (!teacher) {
      Toast.error("Please select a teacher.");
      return;
    }
    const btn = document.getElementById("fu-save");
    btn.disabled = true;
    btn.textContent = "Saving...";
    try {
      let saved = 0;
      for (const boy of this.allBoys) {
        const d = this.draft.get(boy.id);
        const rec = this.existing.get(boy.id);
        if (rec) {
          if (d.status && (d.status !== rec.status || (d.note || "") !== (rec.note || ""))) {
            await this.service.update(rec.id, { status: d.status, note: d.note || null });
            saved += 1;
          }
        } else if (d.status) {
          await this.service.create({
            teacher_id: teacher.id,
            teacher_name: teacher.teacher_name,
            boy_id: boy.id,
            boy_name: boy.boy_name,
            class_name: this.className,
            action_date: this.date,
            status: d.status,
            note: d.note || null,
          });
          saved += 1;
        }
      }
      Toast.success(saved ? `${saved} follow-up${saved === 1 ? "" : "s"} saved.` : "Nothing new to save.");
      await this.reloadRows();
      await this.reloadHistory();
    } catch (err) {
      Toast.error(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Save Follow Ups";
    }
  }

  async reloadHistory() {
    this.histBox.innerHTML = skeletonTable(4);
    try {
      const records = await this.service.list(this.className, {
        actionDate: this.historyDate || null,
      });
      const list = (Array.isArray(records) ? records : [])
        .slice()
        .sort((a, b) => String(b.action_date || "").localeCompare(String(a.action_date || "")))
        .slice(0, 50);
      if (!list.length) {
        this.histBox.innerHTML = emptyState("No follow-ups yet", "Saved follow-ups will appear here.");
        return;
      }
      this.histBox.innerHTML = table(
        ["Date", "Teacher", "Boy", "Method", "Note", "Actions"],
        list.map((r) => `
          <tr>
            <td>${escapeHtml(r.action_date || "—")}</td>
            <td>${escapeHtml(r.teacher_name || "—")}</td>
            <td>${escapeHtml(r.boy_name || "—")}</td>
            <td>${badge(r.status || "—", STATUS_BADGE[r.status] || "")}</td>
            <td>${r.note ? `<span class="note-indicator" title="${escapeHtml(r.note)}">View</span>` : `<span class="muted">—</span>`}</td>
            <td class="cell-actions">
              <button class="btn-link" data-hact="edit" data-id="${r.id}">Edit</button>
              <button class="btn-link danger" data-hact="del" data-id="${r.id}">Delete</button>
            </td>
          </tr>`).join("")
      );
      this.histBox.querySelectorAll("button[data-hact]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const rec = list.find((x) => x.id === btn.dataset.id);
          if (!rec) return;
          if (btn.dataset.hact === "edit") this.editRecord(rec);
          if (btn.dataset.hact === "del") this.deleteRecord(rec);
        });
      });
    } catch (err) {
      this.histBox.innerHTML = errorBlock(err.message);
    }
  }

  editRecord(rec) {
    const body = document.createElement("div");
    body.innerHTML = `
      <div class="field"><label>Method</label>
        <select class="input" id="hist-status">
          ${FOLLOW_STATUS.map((s) =>
            `<option value="${s.value}"${rec.status === s.value ? " selected" : ""}>${s.label}</option>`).join("")}
        </select>
      </div>
      <div class="field"><label>Note</label>
        <textarea class="input" id="hist-note" rows="3">${escapeHtml(rec.note || "")}</textarea>
      </div>`;
    Modal.open({
      title: `Edit — ${rec.boy_name || ""}`,
      sub: `${rec.teacher_name || ""} • ${rec.action_date || ""}`,
      body,
      actions: [
        { label: "Cancel" },
        {
          label: "Save changes",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            button.disabled = true;
            try {
              await this.service.update(rec.id, {
                status: body.querySelector("#hist-status").value,
                note: body.querySelector("#hist-note").value.trim() || null,
              });
              Toast.success("Follow-up updated.");
              close();
              await this.reloadRows();
              await this.reloadHistory();
            } catch (err) {
              Toast.error(err.message);
              button.disabled = false;
            }
          },
        },
      ],
    });
  }

  async deleteRecord(rec) {
    const ok = await Modal.confirm({
      title: "Delete follow-up?",
      message: `Follow-up for "${rec.boy_name}" on ${rec.action_date} will be removed.`,
    });
    if (!ok) return;
    try {
      await this.service.remove(rec.id);
      Toast.success("Follow-up deleted.");
      await this.reloadRows();
      await this.reloadHistory();
    } catch (err) {
      Toast.error(err.message);
    }
  }
}
