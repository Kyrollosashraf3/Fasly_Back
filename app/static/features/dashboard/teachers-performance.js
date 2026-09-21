import { DashboardService } from "./dashboard-data.js";
import { CLASSES, classLabel } from "../../shared/constants.js";
import { emptyState, loadingBlock, table } from "../../shared/components.js";
import { escapeHtml } from "../../shared/utils.js";
import { nOptions, trendChart } from "./dashboard-shared.js";

export class TeachersPerformancePage {
  constructor(app) {
    this.app = app;
    this.service = new DashboardService(app.api);
    this.className = "";
    this.topN = 5;
    this.teacherTrendN = 8;
    this.data = null;
  }

  async mount() {
    const html = await this.app.partial("features/dashboard/teachers-performance.html");
    this.app.setView(html);
    this.box = document.getElementById("dash-content");

    const allowed = this.app.auth.accessibleClasses();
    const sel = document.getElementById("dash-class");
    const bothAll = allowed.length > 1 || this.app.auth.isAdmin();
    sel.innerHTML = (bothAll ? `<option value="">كل الفصول</option>` : "") +
      (bothAll ? CLASSES : allowed).map((c) =>
        `<option value="${c}">${classLabel(c)}</option>`).join("");
    sel.addEventListener("change", async () => {
      this.className = sel.value;
      await this.load();
    });

    await this.load();
  }

  async load() {
    this.box.innerHTML = loadingBlock("جارٍ حساب مؤشرات الخدام...");
    try {
      this.data = await this.service.summary({
        className: this.className || null,
        topN: this.topN,
        teacherTrendN: this.teacherTrendN,
      });
      this.render();
    } catch (err) {
      this.box.innerHTML = `<div class="error-block"><h3>حدث خطأ</h3>
        <p>${escapeHtml(err.message)}</p>
        <button class="btn btn-secondary" id="dash-retry">حاول مجددًا</button></div>`;
      document.getElementById("dash-retry")?.addEventListener("click", () => this.load());
    }
  }

  render() {
    const d = this.data;
    const totalChecks = d.servants.reduce((n, s) => n + s.checks, 0);
    const avg = d.servants.length
      ? (d.servants.reduce((n, s) => n + s.score, 0) / d.servants.length).toFixed(1)
      : "—";

    let html = `
      <div class="dash-kpis">
        <div class="dash-kpi hero">
          <div class="kpi-num">${d.counts.teachers}</div>
          <div class="kpi-label">خدام تمت متابعتهم</div>
          <div class="kpi-sub">متابعات مسجلة ${totalChecks} • متوسط النقاط ${avg}</div>
        </div>
        <div class="dash-kpi"><div class="kpi-num">${totalChecks}</div><div class="kpi-label">متابعات</div></div>
        <div class="dash-kpi"><div class="kpi-num">${avg}</div><div class="kpi-label">متوسط النقاط</div></div>
      </div>`;

    html += `
      <div class="dash-section">
        <h2>منحنى حضور الخدام</h2>
        <p class="dash-hint">عدد الخدام الحاضرين في كل جمعة (من الأقدم للأحدث).</p>
        <label class="n-field">عدد الجمع:
          <select class="input" id="dash-teacher-trend-n">${nOptions(d.scope.teacher_trend_n, 1, 12)}</select>
        </label>
        <div class="card">${d.teachers_trend.length ? trendChart(d.teachers_trend) : emptyState("لا توجد بيانات", "لا توجد متابعات مسجلة بعد.")}</div>
      </div>`;

    html += `
      <div class="dash-section">
        <h2>أشطر الخدام</h2>
        <p class="dash-hint">النقاط = مجموع (الحضور + تحضير الدرس + القداس + الافتقاد) في كل المتابعات. المتعادلون مع المركز الأخير يدخلون معه.</p>
        <label class="n-field">عدد الأوائل:
          <select class="input" id="dash-top-n">${nOptions(d.scope.top_n, 1, 12)}</select>
        </label>`;
    if (!d.top_servants.length) {
      html += emptyState("لا توجد متابعات بعد", "سجّل متابعة الخدام أولًا لتظهر هنا.");
    } else {
      html += `
        <ul class="name-list">
          ${d.top_servants.map((s, i) => `
            <li><span><span class="rank rank-${i + 1}">${i + 1}</span>
              <strong> ${escapeHtml(s.teacher_name)}</strong>
              <span class="muted small"> • ${escapeHtml(classLabel(s.class_name))}</span></span>
              <span class="score-pill">${s.score} نقطة</span></li>`).join("")}
        </ul>`;
    }
    html += `</div>`;

    if (d.servants.length) {
      html += `
      <div class="dash-section">
        <h2>أداء الخدام</h2>
        <p class="dash-hint">مجموع علامات ✓ التي جمعها كل خادم في كل المتابعات المسجلة.</p>
        ${table(
          ["الخادم", "الفصل", "النقاط", "متابعات", "حاضر", "درس", "قداس", "افتقاد"],
          d.servants.map((s) => `
            <tr><td><strong>${escapeHtml(s.teacher_name)}</strong></td>
            <td>${escapeHtml(classLabel(s.class_name))}</td>
            <td><span class="score-pill">${s.score}</span></td>
            <td>${s.checks}</td><td>${s.attend}</td>
            <td>${s.prepare}</td><td>${s.liturgy}</td><td>${s.follow}</td></tr>`).join("")
        )}
      </div>`;
    }

    this.box.innerHTML = html;
    this.bindNInputs();
  }

  bindNInputs() {
    const t = document.getElementById("dash-top-n");
    const tt = document.getElementById("dash-teacher-trend-n");
    let timer = null;
    const apply = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const nt = Math.max(1, Number(t?.value) || 5);
        const nh = Math.max(1, Number(tt?.value) || 8);
        if (nt === this.topN && nh === this.teacherTrendN) return;
        this.topN = nt;
        this.teacherTrendN = nh;
        await this.load();
      }, 600);
    };
    t?.addEventListener("change", apply);
    tt?.addEventListener("change", apply);
  }
}
