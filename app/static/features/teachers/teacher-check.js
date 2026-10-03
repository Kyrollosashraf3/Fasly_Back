import { TeacherService } from "./teachers-data.js";
import { classLabel } from "../../shared/constants.js";
import { Modal, Toast, emptyState, skeletonTable } from "../../shared/components.js";
import { escapeHtml, formatDate, lastFridayISO } from "../../shared/utils.js";

/** Data-access layer for the weekly teacher checklist. */
export class TeacherCheckService {
  constructor(api) {
    this.api = api;
  }

  list(classId, actionDate) {
    const query = {};
    if (classId !== null && classId !== undefined && classId !== "") query.class_id = classId;
    if (actionDate) query.action_date = actionDate;
    return this.api.get("/teacher-checks", query);
  }

  saveBulk(actionDate, items) {
    // TeacherCheckBulkCreate carries only {date, items}.
    const body = { items };
    if (actionDate) body.date = actionDate;
    return this.api.post("/teacher-checks/bulk", body);
  }
}

const COLS = [
  { key: "attend", label: "حاضر" },
  { key: "prepare", label: "تحضير الدرس" },
  { key: "liturgy", label: "القداس" },
  { key: "follow", label: "افتقاد" },
];

export class TeacherCheckPage {
  constructor(app) {
    this.app = app;
    this.teachers = new TeacherService(app.api);
    this.service = new TeacherCheckService(app.api);
    this.allTeachers = [];
    this.state = new Map();
    this.search = "";
  }

  async mount(ctx) {
    this.classId = ctx.params.classId;
    this.canWrite = this.app.auth.isManager();
    this.date = lastFridayISO();
    this.render_shell();
    await this.reload();
  }

  render_shell() {
    const label = classLabel(this.classId);
    this.app.setView(`
      <div class="page-head">
        <div class="crumb"><a href="#/home">الفصول</a> / <a href="#/class/${this.classId}">${escapeHtml(label)}</a></div>
        <h1>متابعة الخدام</h1>
        <p class="sub">المتابعة الأسبوعية لكل خادم: الحضور وتحضير الدرس والقداس والافتقاد. حفظ نفس التاريخ يحدّث البيانات.</p>
      </div>
      <div class="toolbar">
        <div class="toolbar-group">
          <label class="date-field">التاريخ
            <input class="input" id="check-date" type="date" value="${this.date}" ${this.canWrite ? "" : "disabled"} />
          </label>
        </div>
        <div class="toolbar-group">
          <input class="input search-input" id="check-search" type="search" placeholder="ابحث بالاسم..." autocomplete="off" />
        </div>
      </div>
      <div id="check-content"></div>
      <div class="summary-bar" id="check-summary" ${this.canWrite ? "" : "hidden"}>
        <div class="counts"><span id="check-count" class="muted small"></span></div>
        <button class="btn btn-primary" id="check-save">حفظ</button>
      </div>`);
    this.box = document.getElementById("check-content");

    document.getElementById("check-date").addEventListener("change", async (e) => {
      this.date = e.target.value;
      await this.reload();
    });
    document.getElementById("check-search").addEventListener("input", (e) => {
      this.search = e.target.value.trim().toLowerCase();
      this.render();
    });
    document.getElementById("check-save").addEventListener("click", () => this.save());
  }

  async reload() {
    this.box.innerHTML = skeletonTable(5);
    const summary = document.getElementById("check-summary");
    if (this.canWrite) summary.hidden = true;
    try {
      const [teachers, records] = await Promise.all([
        this.teachers.list(this.classId),
        this.service.list(this.classId, this.date),
      ]);
      this.allTeachers = Array.isArray(teachers) ? teachers : [];
      const byTeacher = new Map((Array.isArray(records) ? records : []).map((r) => [r.teacher_id, r]));
      this.state = new Map(
        this.allTeachers.map((t) => {
          const rec = byTeacher.get(t.id);
          return [t.id, {
            attend: Boolean(rec && rec.attend),
            prepare: Boolean(rec?.prepare),
            liturgy: Boolean(rec?.liturgy),
            follow: Boolean(rec?.follow),
            note: rec?.note || "",
          }];
        })
      );
      this.render();
      if (this.canWrite) summary.hidden = !this.allTeachers.length;
    } catch (err) {
      this.box.innerHTML = `<div class="error-block"><h3>حدث خطأ</h3>
        <p>${escapeHtml(err.message)}</p>
        <button class="btn btn-secondary" id="retry">حاول مجددًا</button></div>`;
      document.getElementById("retry")?.addEventListener("click", () => this.reload());
    }
  }

  render() {
    const rows = this.allTeachers.filter((t) =>
      !this.search || `${t.teacher_name || ""}`.toLowerCase().includes(this.search));
    if (!rows.length) {
      this.box.innerHTML = this.allTeachers.length
        ? emptyState("لا توجد نتائج", "جرّب بحثًا مختلفًا.")
        : emptyState("لا يوجد خدام", "سجّل خدام هذا الفصل أولًا قبل المتابعة.");
      return;
    }
    const editable = this.canWrite ? " checked" : "";
    this.box.innerHTML = `
      <div class="table-wrap">
        <table class="table check-table">
          <thead><tr><th>الخادم</th>${COLS.map((c) => `<th class="center">${c.label}</th>`).join("")}<th>ملاحظة</th></tr></thead>
          <tbody>
            ${rows.map((t) => {
              const s = this.state.get(t.id);
              const cells = COLS.map((c) => {
                const checked = s[c.key] ? editable : "";
                return `<td class="center"><input type="checkbox" class="check" data-col="${c.key}" data-id="${t.id}"${checked}${this.canWrite ? "" : " disabled"} aria-label="${c.label}" /></td>`;
              }).join("");
              return `<tr>
                <td><strong>${escapeHtml(t.teacher_name)}</strong><div class="muted small">${escapeHtml(t.phone || "")}</div></td>
                ${cells}
                <td><button class="btn-link" data-note="${t.id}"${this.canWrite ? "" : " disabled"}>${s.note ? "&#9998; *" : "&#9998;"}</button></td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
      <p class="muted small" style="margin-top:8px">${escapeHtml(formatDate(this.date))} — الحضور، تحضير الدرس، حضور القداس، وافتقاد المجموعة.</p>`;

    this.box.querySelectorAll("input[data-col]").forEach((cb) => {
      cb.addEventListener("change", () => {
        this.state.get(cb.dataset.id)[cb.dataset.col] = cb.checked;
      });
    });
    this.box.querySelectorAll("[data-note]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const s = this.state.get(btn.dataset.note);
        const teacher = this.allTeachers.find((t) => String(t.id) === String(btn.dataset.note));
        const value = await Modal.note({ title: `ملاحظة — ${teacher?.teacher_name || ""}`, value: s.note });
        if (value === null) return;
        s.note = value;
        btn.innerHTML = value ? "&#9998; *" : "&#9998;";
      });
    });
    document.getElementById("check-count").textContent =
      `${this.allTeachers.length} خدام • ${formatDate(this.date)}`;
  }

  async save() {
    if (!this.canWrite) return;
    if (!this.date) {
      Toast.error("من فضلك اختر التاريخ.");
      return;
    }
    const btn = document.getElementById("check-save");
    const items = [...this.state.entries()].map(([teacherId, s]) => ({
      teacher_id: Number(teacherId),
      attend: Boolean(s.attend),
      prepare: Boolean(s.prepare),
      liturgy: Boolean(s.liturgy),
      follow: Boolean(s.follow),
      note: s.note || null,
    }));
    if (!items.length) {
      Toast.error("لا يوجد خدام للمتابعة.");
      return;
    }
    btn.disabled = true;
    btn.textContent = "جارٍ الحفظ...";
    try {
      await this.service.saveBulk(this.date, items);
      Toast.success(`تم حفظ متابعة الخدام في ${formatDate(this.date)}.`);
    } catch (err) {
      Toast.error(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "حفظ";
    }
  }
}
