import { BoyService } from "./boys-data.js";
import { ATTEND, classLabel } from "../../shared/constants.js";
import { Modal, Toast, emptyState, skeletonTable } from "../../shared/components.js";
import { escapeHtml, formatDate, lastFridayISO } from "../../shared/utils.js";

/** Data-access layer for attendance records. */
export class AttendanceService {
  constructor(api) {
    this.api = api;
  }

  list(className, actionDate) {
    return this.api.get("/attendance", { class_name: className, action_date: actionDate });
  }

  saveBulk(className, actionDate, items, recordedBy = null) {
    return this.api.post("/attendance/bulk", {
      class_name: className,
      action_date: actionDate,
      recorded_by: recordedBy,
      items,
    });
  }
}

export class AttendancePage {
  constructor(app) {
    this.app = app;
    this.boys = new BoyService(app.api);
    this.service = new AttendanceService(app.api);
    this.allBoys = [];
    this.state = new Map(); // boy_id -> { attend: 'y'|'n', note: string }
    this.search = "";
    this.gender = "";
  }

  async mount(ctx) {
    this.className = ctx.params.className;
    this.date = lastFridayISO();
    this.view = "remaining";
    this.render_shell();
    await this.reload();
  }

  render_shell() {
    this.app.setView(`
      <div class="page-head">
        <div class="crumb"><a href="#/home">الفصول</a> / <a href="#/class/${this.className}">${escapeHtml(classLabel(this.className))}</a></div>
        <h1>الحضور</h1>
        <p class="sub">علّم على الحاضرين بعلامة ✓. حفظ نفس التاريخ مرة أخرى يحدّث الكشف.</p>
      </div>
      <div class="toolbar">
        <div class="toolbar-group">
          <label class="date-field">التاريخ
            <input class="input" id="att-date" type="date" value="${this.date}" />
          </label>
        </div>
        <div class="toolbar-group">
          <input class="input search-input" id="att-search" type="search" placeholder="ابحث بالاسم..." autocomplete="off" />
          <div class="filter-tabs" id="att-gender-tabs">
            <button data-g="" class="active">الكل</button>
            <button data-g="m">أولاد</button>
            <button data-g="f">بنات</button>
          </div>
        </div>
      </div>
      <div class="att-view-row">
        <div class="filter-tabs" id="att-view-tabs" role="tablist" aria-label="عرض الحضور">
          <button data-view="remaining" class="active">المتبقي (<span id="n-remaining">0</span>)</button>
          <button data-view="present">الحاضرون (<span id="n-present">0</span>)</button>
          <button data-view="all">الكل</button>
        </div>
      </div>
      <div id="att-content"></div>
      <div class="summary-bar" id="att-summary" hidden>
        <div class="counts"><span>حاضر: <strong id="count-present">0</strong></span><span>غائب: <strong id="count-absent">0</strong></span></div>
        <button class="btn btn-primary" id="att-save">حفظ الحضور</button>
      </div>`);
    this.box = document.getElementById("att-content");

    document.getElementById("att-date").addEventListener("change", async (e) => {
      this.date = e.target.value;
      await this.reload();
    });
    document.getElementById("att-search").addEventListener("input", (e) => {
      this.search = e.target.value.trim().toLowerCase();
      this.render();
    });
    document.getElementById("att-gender-tabs").addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      this.gender = btn.dataset.g;
      document.querySelectorAll("#att-gender-tabs button").forEach((b) =>
        b.classList.toggle("active", b === btn));
      this.render();
    });
    document.getElementById("att-view-tabs").addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      this.view = btn.dataset.view;
      document.querySelectorAll("#att-view-tabs button").forEach((b) =>
        b.classList.toggle("active", b === btn));
      this.render();
    });
    document.getElementById("att-save").addEventListener("click", () => this.save());
  }

  async reload() {
    this.box.innerHTML = skeletonTable(8);
    document.getElementById("att-summary").hidden = true;
    try {
      const [boys, records] = await Promise.all([
        this.boys.list(this.className),
        this.service.list(this.className, this.date),
      ]);
      this.allBoys = Array.isArray(boys) ? boys : [];
      const byBoy = new Map((Array.isArray(records) ? records : []).map((r) => [r.boy_id, r]));
      this.state = new Map(
        this.allBoys.map((b) => {
          const rec = byBoy.get(b.id);
          return [b.id, { attend: rec ? rec.attend : ATTEND.NO, note: rec?.note || "" }];
        })
      );
      this.render();
      document.getElementById("att-summary").hidden = !this.allBoys.length;
    } catch (err) {
      this.box.innerHTML = `<div class="error-block"><h3>حدث خطأ</h3>
        <p>${escapeHtml(err.message)}</p>
        <button class="btn btn-secondary" id="retry">حاول مجددًا</button></div>`;
      document.getElementById("retry")?.addEventListener("click", () => this.reload());
    }
  }

  visible() {
    return this.allBoys.filter((b) => {
      const s = this.state.get(b.id);
      const present = s && s.attend === ATTEND.YES;
      if (this.view === "remaining" && present) return false;
      if (this.view === "present" && !present) return false;
      if (this.gender && b.gender !== this.gender) return false;
      if (!this.search) return true;
      return `${b.boy_name || ""}`.toLowerCase().includes(this.search);
    });
  }

  render() {
    const rows = this.visible();
    if (!rows.length) {
      if (!this.allBoys.length) {
        this.box.innerHTML = emptyState("لا يوجد أولاد", "سجّل أولاد هذا الفصل أولًا قبل أخذ الحضور.");
      } else if (this.view === "remaining") {
        this.box.innerHTML = emptyState(
          "تمام، خلصت",
          `الكل اتعلم حضور في ${formatDate(this.date)}.`,
          `<button class="btn btn-secondary" id="show-all">مراجعة الكل</button>`
        );
        document.getElementById("show-all")?.addEventListener("click", () => this.setView("all"));
      } else {
        this.box.innerHTML = emptyState("لا توجد نتائج", "جرّب بحثًا أو فلترًا مختلفًا.");
      }
      this.updateCounts();
      return;
    }
    this.box.innerHTML = `
      <div class="table-wrap">
        <table class="table att-table">
          <thead><tr><th style="width:44px"><span class="sr-only">حاضر</span></th><th>الاسم</th><th>ملاحظة</th></tr></thead>
          <tbody>
            ${rows.map((b) => {
              const s = this.state.get(b.id);
              const present = s.attend === ATTEND.YES;
              return `<tr data-row="${b.id}" class="${present ? "row-present" : ""}">
                <td><input type="checkbox" class="check" data-check="${b.id}"${present ? " checked" : ""} aria-label="حاضر" /></td>
                <td><strong>${escapeHtml(b.boy_name)}</strong></td>
                <td><button class="btn-link" data-note="${b.id}" title="إضافة ملاحظة">${s.note ? "&#9998; *" : "&#9998;"}</button></td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
      <p class="muted small" style="margin-top:8px">${escapeHtml(formatDate(this.date))} — راجع الفصل كله ثم احفظ.</p>`;

    this.box.querySelectorAll("[data-check]").forEach((cb) => {
      cb.addEventListener("change", () => {
        const s = this.state.get(cb.dataset.check);
        s.attend = cb.checked ? ATTEND.YES : ATTEND.NO;
        // In "Remaining" view the row disappears right away to keep the list short.
        this.render();
      });
    });
    this.box.querySelectorAll("[data-note]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const s = this.state.get(btn.dataset.note);
        const boy = this.allBoys.find((b) => b.id === btn.dataset.note);
        const value = await Modal.note({ title: `ملاحظة — ${boy?.boy_name || ""}`, value: s.note });
        if (value === null) return;
        s.note = value;
        btn.innerHTML = value ? "&#9998; *" : "&#9998;";
      });
    });
    this.updateCounts();
  }

  setView(view) {
    this.view = view;
    document.querySelectorAll("#att-view-tabs button").forEach((b) =>
      b.classList.toggle("active", b.dataset.view === view));
    this.render();
  }

  updateCounts() {
    let present = 0;
    for (const s of this.state.values()) {
      if (s.attend === ATTEND.YES) present += 1;
    }
    document.getElementById("count-present").textContent = present;
    document.getElementById("count-absent").textContent = this.state.size - present;
    const nR = document.getElementById("n-remaining");
    const nP = document.getElementById("n-present");
    if (nR) nR.textContent = this.state.size - present;
    if (nP) nP.textContent = present;
  }

  async save() {
    if (this._saving) return; // double-click guard: one request at a time
    if (!this.date) {
      Toast.error("من فضلك اختر التاريخ.");
      return;
    }
    const btn = document.getElementById("att-save");
    // Defensive dedupe: one row per boy even if state was built twice.
    const items = [...new Map(
      [...this.state.entries()].map(([boy_id, s]) => [boy_id, {
        boy_id,
        attend: s.attend,
        note: s.note || null,
      }])
    ).values()];
    this._saving = true;
    btn.disabled = true;
    btn.textContent = "جارٍ الحفظ...";
    try {
      const user = this.app.auth.currentUser();
      await this.service.saveBulk(this.className, this.date, items, user?.id || null);
      Toast.success(`تم حفظ حضور ${formatDate(this.date)}.`);
      await this.reload(); // re-read canonical rows so a second save is a pure update
    } catch (err) {
      Toast.error(err.message);
    } finally {
      this._saving = false;
      btn.disabled = false;
      btn.textContent = "حفظ الحضور";
    }
  }
}
