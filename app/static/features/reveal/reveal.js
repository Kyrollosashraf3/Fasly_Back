import { DashboardService } from "../dashboard/dashboard-data.js";
import { BoyService } from "../boys/boys-data.js";
import { TeacherService } from "../teachers/teachers-data.js";
import { GENDER_LABELS, FOLLOW_STATUS_LABELS, classLabel } from "../../shared/constants.js";
import { badge, emptyState, loadingBlock } from "../../shared/components.js";
import { escapeHtml, formatDate } from "../../shared/utils.js";

export class RevealPage {
  constructor(app) {
    this.app = app;
    this.service = new DashboardService(app.api);
    this.boys = new BoyService(app.api);
    this.teachers = new TeacherService(app.api);
    this.allBoys = [];
    this.teacherNames = new Map();
    this.classId = "";
    this.picked = null;
    this.search = "";
  }

  async mount() {
    const html = await this.app.partial("features/reveal/reveal.html");
    this.app.setView(html);
    this.box = document.getElementById("rev-candidates");
    this.result = document.getElementById("rev-result");
    this.goBtn = document.getElementById("rev-go");

    // Follow-ups come back with teacher_id only; resolve the Arabic names once.
    try {
      const list = await this.teachers.list(undefined);
      for (const t of Array.isArray(list) ? list : []) {
        this.teacherNames.set(t.id, t.teacher_name);
      }
    } catch {
      /* a boy login may not read the servant directory */
    }

    const allowed = this.app.auth.accessibleClasses();
    const sel = document.getElementById("rev-class");
    sel.innerHTML = `<option value="">اختر الفصل...</option>` +
      allowed.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    sel.addEventListener("change", async () => {
      this.classId = sel.value;
      this.picked = null;
      this.updateGo();
      if (this.classId) await this.loadBoys();
      else this.box.innerHTML = `<p class="muted">اختر الفصل أولًا لعرض الأولاد.</p>`;
    });

    document.getElementById("rev-search").addEventListener("input", (e) => {
      this.search = e.target.value.trim();
      this.renderCandidates();
    });
    this.goBtn.addEventListener("click", () => this.reveal());
  }

  async loadBoys() {
    this.box.innerHTML = loadingBlock("جارٍ تحميل الأولاد...");
    try {
      const data = await this.boys.list(this.classId);
      this.allBoys = Array.isArray(data) ? data : [];
      this.renderCandidates();
    } catch (err) {
      this.box.innerHTML = `<div class="form-error">${escapeHtml(err.message)}</div>`;
    }
  }

  renderCandidates() {
    const q = this.search;
    const rows = this.allBoys.filter((b) => !q || (b.boy_name || "").includes(q));
    if (!rows.length) {
      this.box.innerHTML = emptyState("لا يوجد أولاد", "لا توجد أسماء مطابقة في هذا الفصل.");
      return;
    }
    this.box.innerHTML = `<div class="candidate-list">${rows.map((b) => `
      <button data-id="${b.id}" class="${this.picked && this.picked.id === b.id ? "picked" : ""}">
        ${escapeHtml(b.boy_name)}</button>`).join("")}</div>`;
    this.box.querySelectorAll("button[data-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.picked = this.allBoys.find((x) => String(x.id) === String(btn.dataset.id)) || null;
        this.box.querySelectorAll("button[data-id]").forEach((x) =>
          x.classList.toggle("picked", x === btn));
        this.updateGo();
      });
    });
  }

  updateGo() {
    this.goBtn.disabled = !this.picked;
    this.goBtn.textContent = this.picked ? `اكشفلي — ${this.picked.boy_name}` : "اكشفلي";
  }

  async reveal() {
    if (!this.picked) return;
    this.result.innerHTML = loadingBlock("جارٍ كشف الملف...");
    this.result.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      const p = await this.service.boyProfile(this.picked.id);
      this.renderResult(p);
    } catch (err) {
      this.result.innerHTML = `<div class="form-error">${escapeHtml(err.message)}</div>`;
    }
  }

  renderResult(p) {
    const b = p.boy;
    const s = p.season;
    const cells = s.fridays.map((f) => `
      <div class="friday-cell present-${f.present}">
        <div class="d">${escapeHtml(formatDate(f.date))}</div>
        ${f.present ? badge("حاضر", "green") : badge("غائب", "red")}
        ${f.note ? `<div class="muted small" title="${escapeHtml(f.note)}">✎ ملاحظة</div>` : ""}
      </div>`).join("");
    const notes = p.notes.length
      ? `<ul class="notes-list">${p.notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>`
      : `<p class="muted">لا توجد ملاحظات.</p>`;
    const fus = p.followups.length
      ? `<ul class="timeline">${p.followups.map((f) => `
        <li><div class="tl-head">
            <strong>${escapeHtml(formatDate(f.action_date))}</strong>
            <span>${escapeHtml(this.teacherNames.get(f.teacher_id) || "—")}</span>
            ${badge(FOLLOW_STATUS_LABELS[f.status] || f.status || "—", "yellow")}
          </div>
          ${f.note ? `<div class="tl-note">${escapeHtml(f.note)}</div>` : ""}</li>`).join("")}</ul>`
      : `<p class="muted">لا يوجد افتقاد مسجل لهذا الولد بعد.</p>`;

    this.result.innerHTML = `
      <div class="reveal-hero">
        <div class="hero-info">
          <h2>${escapeHtml(b.boy_name)}</h2>
          <div class="hero-sub">${escapeHtml(classLabel(b.class_id))} •
            ${escapeHtml(GENDER_LABELS[b.gender] || "")} •
            ${escapeHtml(b.phone || "بدون تليفون")} •
            ${escapeHtml(b.address || "")}</div>
        </div>
        <div class="reveal-score">
          <div class="pct">${s.percent}%</div>
          <div class="frac">حضر ${s.present} من ${s.total}</div>
        </div>
      </div>
      <div class="dash-section">
        <h2>جمعات السنة الكنسية (من ${escapeHtml(formatDate(s.start))})</h2>
        <p class="dash-hint">حضر ${s.present} من ${s.total} جمعة — نسبة الحضور ${s.percent}%</p>
        <div class="friday-grid">${cells}</div>
      </div>
      <div class="dash-section">
        <h2>الملاحظات</h2>${notes}
      </div>
      <div class="dash-section">
        <h2>سجل الافتقاد</h2>
        <p class="dash-hint">كل مرة اتعمل له فيها افتقاد: التاريخ والخادم والطريقة.</p>${fus}
      </div>`;
  }
}
