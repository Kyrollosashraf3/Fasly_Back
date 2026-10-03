import { BoyService } from "../boys/boys-data.js";
import { TeacherService } from "../teachers/teachers-data.js";
import { FOLLOW_STATUS, FOLLOW_STATUS_LABELS, classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, badge, emptyState, errorBlock, skeletonTable, table,
} from "../../shared/components.js";
import { escapeHtml, formatDate, lastFridayISO } from "../../shared/utils.js";

/** Data-access layer for weekly follow-ups. */
export class FollowUpService {
  constructor(api) {
    this.api = api;
  }

  list(classId, { teacherId = null, boyId = null, actionDate = null } = {}) {
    const query = {};
    if (classId !== null && classId !== undefined && classId !== "") query.class_id = classId;
    if (teacherId) query.teacher_id = teacherId;
    if (boyId) query.boy_id = boyId;
    if (actionDate) query.action_date = actionDate;
    return this.api.get("/follow-ups", query);
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

const STATUS_BADGE = { call: "", visit: "yellow", whatsapp: "green", no_answer: "red", other: "green" };
const statusLabel = (v) => FOLLOW_STATUS_LABELS[v] || v || "—";

export class FollowUpPage {
  constructor(app) {
    this.app = app;
    this.service = new FollowUpService(app.api);
    this.boys = new BoyService(app.api);
    this.teachers = new TeacherService(app.api);
    this.allBoys = [];
    this.allTeachers = [];
    this.roster = [];           // boys shown in the sheet for the picked servant
    this.groupMap = new Map();  // teacher_id -> [boy_id]
    this.existing = new Map();  // boy_id -> record (for selected teacher+date)
    this.draft = new Map();     // boy_id -> { status, note }
    this.search = "";
    this.historyDate = "";
    this.canWrite = false;
  }

  async mount(ctx) {
    this.classId = ctx.params.classId;
    this.teacherId = "";
    this.date = lastFridayISO();
    this.canWrite = this.app.auth.isManager() || this.app.auth.isServant();
    const html = await this.app.partial("features/follow-up/follow-up.html");
    this.app.setView(html);

    document.querySelector("[data-crumb-class]").textContent = classLabel(this.classId);
    document.querySelector("[data-crumb-class]").href = `#/class/${this.classId}`;

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
        this.boys.list(this.classId),
        this.teachers.list(this.classId).catch(() => []),
      ]);
      this.allBoys = Array.isArray(boys) ? boys : [];
      this.allTeachers = Array.isArray(teachers) ? teachers : [];
      await this.loadGroups();
      const sel = document.getElementById("fu-teacher");
      sel.innerHTML =
        `<option value="">اختر الخادم...</option>` +
        this.allTeachers.map((t) => `<option value="${t.id}">${escapeHtml(t.teacher_name)}</option>`).join("");
      await this.reloadRows();
      await this.reloadHistory();
    } catch (err) {
      this.box.innerHTML = errorBlock(err.message);
    }
  }

  /** teacher_id -> [boy_id], built from GET /groups (403 for a boy login). */
  async loadGroups() {
    this.groupMap = new Map();
    try {
      const data = await this.app.api.get("/groups", { class_id: this.classId });
      for (const g of (data && data.groups) || []) {
        this.groupMap.set(g.teacher_id, (g.boys || []).map((b) => b.boy_id));
      }
    } catch {
      /* no groups view for this login - fall back to the whole roster */
    }
  }

  rosterFor(teacherId) {
    const ids = this.groupMap.get(Number(teacherId));
    if (!ids) return this.allBoys;
    const set = new Set(ids);
    return this.allBoys.filter((b) => set.has(b.id));
  }

  async reloadRows() {
    if (!this.teacherId || !this.date) {
      this.box.innerHTML = emptyState(
        "اختر الخادم والتاريخ",
        "اختر الخادم وتاريخ الأسبوع من الأعلى لتسجيل الافتقاد."
      );
      document.getElementById("fu-summary").hidden = true;
      return;
    }
    this.roster = this.rosterFor(this.teacherId);
    if (!this.roster.length) {
      this.box.innerHTML = emptyState(
        "لا يوجد أولاد في مجموعة الخادم ده",
        "وزّع الأولاد على الخادم من صفحة المجموعات أولًا.",
        `<a class="btn btn-secondary" href="#/groups">فتح المجموعات</a>`
      );
      document.getElementById("fu-summary").hidden = true;
      return;
    }
    this.box.innerHTML = skeletonTable(6);
    try {
      const records = await this.service.list(this.classId, {
        teacherId: this.teacherId,
        actionDate: this.date,
      });
      this.existing = new Map((Array.isArray(records) ? records : []).map((r) => [r.boy_id, r]));
      this.draft = new Map(
        this.roster.map((b) => {
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
    const rows = this.roster.filter((b) =>
      !this.search || `${b.boy_name || ""}`.toLowerCase().includes(this.search));
    if (!rows.length) {
      this.box.innerHTML = emptyState("لا توجد نتائج", "جرّب بحثًا مختلفًا.");
      return;
    }
    this.box.innerHTML = table(
      ["الولد", "الافتقاد", "ملاحظة"],
      rows.map((b) => {
        const d = this.draft.get(b.id) || { status: "", note: "" };
        return `<tr>
          <td><strong>${escapeHtml(b.boy_name)}</strong></td>
          <td>
            <select class="input fu-status" data-id="${b.id}" aria-label="طريقة الافتقاد"${this.canWrite ? "" : " disabled"}>
              <option value="">—</option>
              ${FOLLOW_STATUS.map((s) =>
                `<option value="${s.value}"${d.status === s.value ? " selected" : ""}>${s.label}</option>`).join("")}
            </select>
          </td>
          <td><button class="btn-link" data-note="${b.id}"${this.canWrite ? "" : " disabled"}>${d.note ? "&#9998; *" : "&#9998;"}</button></td>
        </tr>`;
      }).join("")
    );
    this.box.querySelectorAll(".fu-status").forEach((sel) => {
      sel.addEventListener("change", () => {
        this.draft.get(Number(sel.dataset.id)).status = sel.value;
        this.updateCount();
      });
    });
    this.box.querySelectorAll("[data-note]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const d = this.draft.get(Number(btn.dataset.note));
        const boy = this.roster.find((b) => String(b.id) === String(btn.dataset.note));
        const value = await Modal.note({ title: `ملاحظة — ${boy?.boy_name || ""}`, value: d.note });
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
      `${n} افتقاد • ${formatDate(this.date)}`;
  }

  async save() {
    if (!this.canWrite) return;
    const teacher = this.allTeachers.find((t) => String(t.id) === String(this.teacherId));
    if (!teacher) {
      Toast.error("من فضلك اختر الخادم.");
      return;
    }
    const btn = document.getElementById("fu-save");
    btn.disabled = true;
    btn.textContent = "جارٍ الحفظ...";
    try {
      let saved = 0;
      for (const boy of this.roster) {
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
            boy_id: boy.id,
            action_date: this.date,
            status: d.status,
            note: d.note || null,
          });
          saved += 1;
        }
      }
      Toast.success(saved ? `تم حفظ ${saved} افتقاد.` : "لا يوجد جديد للحفظ.");
      await this.reloadRows();
      await this.reloadHistory();
    } catch (err) {
      Toast.error(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "حفظ الافتقاد";
    }
  }

  boyName(id) {
    const b = this.allBoys.find((x) => x.id === id);
    return b ? b.boy_name : "—";
  }

  teacherName(id) {
    const t = this.allTeachers.find((x) => x.id === id);
    return t ? t.teacher_name : "—";
  }

  async reloadHistory() {
    this.histBox.innerHTML = skeletonTable(4);
    try {
      const records = await this.service.list(this.classId, {
        actionDate: this.historyDate || null,
      });
      const list = (Array.isArray(records) ? records : [])
        .slice()
        .sort((a, b) => String(b.action_date || "").localeCompare(String(a.action_date || "")))
        .slice(0, 50);
      if (!list.length) {
        this.histBox.innerHTML = emptyState("لا يوجد افتقاد بعد", "الافتقاد المحفوظ سيظهر هنا.");
        return;
      }
      this.histBox.innerHTML = table(
        ["التاريخ", "الخادم", "الولد", "الطريقة", "ملاحظة", "إجراءات"],
        list.map((r) => `
          <tr>
            <td>${escapeHtml(r.action_date || "—")}</td>
            <td>${escapeHtml(this.teacherName(r.teacher_id))}</td>
            <td>${escapeHtml(this.boyName(r.boy_id))}</td>
            <td>${badge(statusLabel(r.status), STATUS_BADGE[r.status] || "")}</td>
            <td>${r.note ? `<span class="note-indicator" title="${escapeHtml(r.note)}">عرض</span>` : `<span class="muted">—</span>`}</td>
            <td class="cell-actions">
              ${this.canWrite ? `
              <button class="btn-link" data-hact="edit" data-id="${r.id}">تعديل</button>
              <button class="btn-link danger" data-hact="del" data-id="${r.id}">حذف</button>` : `<span class="muted">—</span>`}
            </td>
          </tr>`).join("")
      );
      this.histBox.querySelectorAll("button[data-hact]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const rec = list.find((x) => String(x.id) === String(btn.dataset.id));
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
      <div class="field"><label>الطريقة</label>
        <select class="input" id="hist-status">
          ${FOLLOW_STATUS.map((s) =>
            `<option value="${s.value}"${rec.status === s.value ? " selected" : ""}>${s.label}</option>`).join("")}
        </select>
      </div>
      <div class="field"><label>ملاحظة</label>
        <textarea class="input" id="hist-note" rows="3">${escapeHtml(rec.note || "")}</textarea>
      </div>`;
    Modal.open({
      title: `تعديل — ${this.boyName(rec.boy_id)}`,
      sub: `${this.teacherName(rec.teacher_id)} • ${rec.action_date || ""}`,
      body,
      actions: [
        { label: "إلغاء" },
        {
          label: "حفظ التعديلات",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            button.disabled = true;
            try {
              await this.service.update(rec.id, {
                status: body.querySelector("#hist-status").value,
                note: body.querySelector("#hist-note").value.trim() || null,
              });
              Toast.success("تم تعديل الافتقاد.");
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
      title: "حذف الافتقاد؟",
      message: `افتقاد "${this.boyName(rec.boy_id)}" بتاريخ ${rec.action_date} سيتم حذفه.`,
    });
    if (!ok) return;
    try {
      await this.service.remove(rec.id);
      Toast.success("تم حذف الافتقاد.");
      await this.reloadRows();
      await this.reloadHistory();
    } catch (err) {
      Toast.error(err.message);
    }
  }
}
