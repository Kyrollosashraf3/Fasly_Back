import { TeacherService } from "./teachers-data.js";
import { ATTEND, classLabel } from "../../shared/constants.js";
import { Modal, Toast, emptyState, skeletonTable } from "../../shared/components.js";
import { escapeHtml, formatDate, lastFridayISO } from "../../shared/utils.js";

/** Data-access layer for the weekly teacher checklist. */
export class TeacherCheckService {
  constructor(api) {
    this.api = api;
  }

  list(className, actionDate) {
    return this.api.get("/teacher-checks", { class_name: className, action_date: actionDate });
  }

  saveBulk(className, actionDate, items, recordedBy = null) {
    return this.api.post("/teacher-checks/bulk", {
      class_name: className,
      action_date: actionDate,
      recorded_by: recordedBy,
      items,
    });
  }
}

const COLS = [
  { key: "attend", label: "حاضر" },
  { key: "prepare_flag", label: "تحضير الدرس" },
  { key: "liturgy_flag", label: "القداس" },
  { key: "follow_flag", label: "افتقاد" },
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
    this.className = ctx.params.className;
    this.date = lastFridayISO();
    this.render_shell();
    await this.reload();
  }

  render_shell() {
    this.app.setView(`
      <div class="page-head">
        <div class="crumb"><a href="#/home">الفصول</a> / <a href="#/class/${this.className}">${escapeHtml(classLabel(this.className))}</a></div>
        <h1>متابعة الخدام</h1>
        <p class="sub">المتابعة الأسبوعية لكل خادم: الحضور وتحضير الدرس والقداس والافتقاد. حفظ نفس التاريخ يحدّث البيانات.</p>
      </div>
      <div class="toolbar">
        <div class="toolbar-group">
          <label class="date-field">التاريخ
            <input class="input" id="check-date" type="date" value="${this.date}" />
          </label>
        </div>
        <div class="toolbar-group">
          <input class="input search-input" id="check-search" type="search" placeholder="ابحث بالاسم..." autocomplete="off" />
        </div>
      </div>
      <div id="check-content"></div>
      <div class="summary-bar" id="check-summary" hidden>
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
    document.getElementById("check-summary").hidden = true;
    try {
      const [teachers, records] = await Promise.all([
        this.teachers.list(this.className),
        this.service.list(this.className, this.date),
      ]);
      this.allTeachers = Array.isArray(teachers) ? teachers : [];
      const byTeacher = new Map((Array.isArray(records) ? records : []).map((r) => [r.teacher_id, r]));
      this.state = new Map(
        this.allTeachers.map((t) => {
          const rec = byTeacher.get(t.id);
          return [t.id, {
            attend: rec ? rec.attend : ATTEND.NO,
            prepare_flag: Boolean(rec?.prepare_flag),
            liturgy_flag: Boolean(rec?.liturgy_flag),
            follow_flag: Boolean(rec?.follow_flag),
            note: rec?.note || "",
          }];
        })
      );
      this.render();
      document.getElementById("check-summary").hidden = !this.allTeachers.length;
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
    this.box.innerHTML = `
      <div class="table-wrap">
        <table class="table check-table">
          <thead><tr><th>الخادم</th>${COLS.map((c) => `<th class="center">${c.label}</th>`).join("")}<th>ملاحظة</th></tr></thead>
          <tbody>
            ${rows.map((t) => {
              const s = this.state.get(t.id);
              const cells = COLS.map((c) => {
                const checked = c.key === "attend" ? s.attend === ATTEND.YES : s[c.key];
                return `<td class="center"><input type="checkbox" class="check" data-col="${c.key}" data-id="${t.id}"${checked ? " checked" : ""} aria-label="${c.label}" /></td>`;
              }).join("");
              return `<tr>
                <td><strong>${escapeHtml(t.teacher_name)}</strong><div class="muted small">${escapeHtml(t.duty || "")}</div></td>
                ${cells}
                <td><button class="btn-link" data-note="${t.id}">${s.note ? "&#9998; *" : "&#9998;"}</button></td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
      <p class="muted small" style="margin-top:8px">${escapeHtml(formatDate(this.date))} — الحضور، تحضير الدرس، حضور القداس، وافتقاد المجموعة.</p>`;

    this.box.querySelectorAll("input[data-col]").forEach((cb) => {
      cb.addEventListener("change", () => {
        const s = this.state.get(cb.dataset.id);
        if (cb.dataset.col === "attend") {
          s.attend = cb.checked ? ATTEND.YES : ATTEND.NO;
        } else {
          s[cb.dataset.col] = cb.checked;
        }
      });
    });
    this.box.querySelectorAll("[data-note]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const s = this.state.get(btn.dataset.note);
        const teacher = this.allTeachers.find((t) => t.id === btn.dataset.note);
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
    if (!this.date) {
      Toast.error("من فضلك اختر التاريخ.");
      return;
    }
    const btn = document.getElementById("check-save");
    const items = [...this.state.entries()].map(([teacher_id, s]) => ({
      teacher_id,
      attend: s.attend,
      prepare_flag: s.prepare_flag,
      liturgy_flag: s.liturgy_flag,
      follow_flag: s.follow_flag,
      note: s.note || null,
    }));
    btn.disabled = true;
    btn.textContent = "جارٍ الحفظ...";
    try {
      const user = this.app.auth.currentUser();
      await this.service.saveBulk(this.className, this.date, items, user?.id || null);
      Toast.success(`تم حفظ متابعة الخدام في ${formatDate(this.date)}.`);
    } catch (err) {
      Toast.error(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "حفظ";
    }
  }
}
