import { DashboardService } from "./dashboard-data.js";
import { CLASSES, classLabel } from "../../shared/constants.js";
import { badge, emptyState, loadingBlock, table } from "../../shared/components.js";
import { escapeHtml, formatDate } from "../../shared/utils.js";
import { groupList, nOptions, openBoyModal, trendChart } from "./dashboard-shared.js";

export class BoysPerformancePage {
  constructor(app) {
    this.app = app;
    this.service = new DashboardService(app.api);
    this.className = "";
    this.streakN = 4;
    this.absentN = 4;
    this.trendN = 8;
    this.data = null;
  }

  async mount() {
    const html = await this.app.partial("features/dashboard/boys-performance.html");
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
    this.box.innerHTML = loadingBlock("جارٍ حساب مؤشرات الأولاد...");
    try {
      this.data = await this.service.summary({
        className: this.className || null,
        streakN: this.streakN,
        absentN: this.absentN,
        trendN: this.trendN,
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
    const a = d.attendance;
    const bound = [];

    let html = `
      <div class="dash-kpis">
        <div class="dash-kpi hero">
          <div class="kpi-num">${a.percent}%</div>
          <div class="kpi-label">نسبة حضور الأولاد</div>
          <div class="progress"><span style="width:${a.percent}%"></span></div>
          <div class="kpi-sub">حاضر ${a.present} • غائب ${a.absent} • الكل ${a.total}</div>
        </div>
        <div class="dash-kpi"><div class="kpi-num">${d.counts.boys}</div><div class="kpi-label">الأولاد</div></div>
        <div class="dash-kpi"><div class="kpi-num">${d.counts.fridays}</div><div class="kpi-label">جُمع مسجلة</div></div>
      </div>`;

    if (!d.scope.single_class) {
      const rows = Object.entries(a.by_class)
        .filter(([, v]) => v.total > 0)
        .sort((x, y) => y[1].percent - x[1].percent);
      if (rows.length) {
        html += `
        <div class="dash-section">
          <h2>نسبة الحضور لكل فصل</h2>
          <div class="card" style="display:grid;gap:10px">
            ${rows.map(([c, v]) => `
              <div>
                <div style="display:flex;justify-content:space-between;font-size:var(--text-sm)">
                  <strong>${escapeHtml(classLabel(c))}</strong><span>${v.percent}% (${v.present}/${v.total})</span>
                </div>
                <div class="progress"><span style="width:${v.percent}%"></span></div>
              </div>`).join("")}
          </div>
        </div>`;
      }
    }

    html += `
      <div class="dash-section">
        <h2>منحنى حضور الأولاد</h2>
        <p class="dash-hint">عدد الحاضرين في كل جمعة (من الأقدم للأحدث).</p>
        <label class="n-field">عدد الجمع:
          <select class="input" id="dash-trend-n">${nOptions(d.scope.trend_n, 1, 12)}</select>
        </label>
        <div class="card">${d.boys_trend.length ? trendChart(d.boys_trend) : emptyState("لا توجد بيانات", "لا توجد جمعات مسجلة بعد.")}</div>
      </div>`;

    html += `
      <div class="dash-section">
        <h2>المواظبون على الحضور</h2>
        <p class="dash-hint">الحاضرون جمعات متواصلة حتى آخر جمعة مسجلة (${d.last_friday.date ? escapeHtml(formatDate(d.last_friday.date)) : "—"}).</p>
        <label class="n-field">عدد الجمع المتواصلة:
          <select class="input" id="dash-streak-n">${nOptions(d.scope.streak_n, 1, 12)}</select>
        </label>
        <div id="dash-streaks"></div>
      </div>`;
    bound.push(["dash-streaks", groupList(d.streaks, {
      singleClass: d.scope.single_class,
      emptyTitle: "لا يوجد مواظبون",
      emptyMsg: `لا أحد وصل ${d.scope.streak_n} جمعات متواصلة. جرّب رقمًا أصغر.`,
      rowBadge: (b) => `<span class="score-pill">${b.streak} جمعة</span>`,
      onBoy: (id) => openBoyModal(this.service, id),
    })]);

    const lf = d.last_friday;
    html += `
      <div class="dash-section">
        <h2>غياب آخر جمعة مسجلة</h2>
        ${lf.date ? `<p class="dash-hint">${escapeHtml(formatDate(lf.date))} — حاضر ${lf.present_count} • غائب ${lf.absent_count}</p>
        <div id="dash-last"></div>` : emptyState("لا يوجد تسجيل بعد", "لم يتم تسجيل أي حضور حتى الآن.")}`;
    if (lf.date) {
      bound.push(["dash-last", groupList(lf.by_class, {
        singleClass: d.scope.single_class,
        emptyTitle: "لا يوجد غياب",
        emptyMsg: "الكل كان حاضرًا في آخر جمعة مسجلة.",
        rowBadge: () => badge("غائب", "red"),
        onBoy: (id) => openBoyModal(this.service, id),
      })]);
    }

    html += `
      <div class="dash-section">
        <h2>الغياب المتكرر</h2>
        <p class="dash-hint">الأولاد الذين غابوا أكثر من العدد المحدد من الجمع.</p>
        <label class="n-field">أكثر من كام جمعة غياب:
          <select class="input" id="dash-absent-n">${nOptions(d.scope.absent_n, 0, 12)}</select>
        </label>
        <div id="dash-freq"></div>
      </div>`;
    bound.push(["dash-freq", groupList(d.frequent_absent, {
      singleClass: d.scope.single_class,
      emptyTitle: "لا يوجد غياب متكرر",
      emptyMsg: `لا أحد غاب أكثر من ${d.scope.absent_n} جمعات.`,
      rowBadge: (b) => badge(`غياب ${b.absent_count}`, "red"),
      onBoy: (id) => openBoyModal(this.service, id),
    })]);

    this.box.innerHTML = html;
    for (const [id, g] of bound) {
      const el = document.getElementById(id);
      if (!el) continue;
      if (typeof g === "string") { el.innerHTML = g; continue; }
      el.innerHTML = g.html;
      g.bind(el);
    }
    this.bindNInputs();
  }

  bindNInputs() {
    const s = document.getElementById("dash-streak-n");
    const a = document.getElementById("dash-absent-n");
    const bt = document.getElementById("dash-trend-n");
    let timer = null;
    const apply = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const ns = Math.max(1, Number(s?.value) || 4);
        const na = Math.max(0, Number(a?.value) || 0);
        const nb = Math.max(1, Number(bt?.value) || 8);
        if (ns === this.streakN && na === this.absentN && nb === this.trendN) return;
        this.streakN = ns;
        this.absentN = na;
        this.trendN = nb;
        await this.load();
      }, 600);
    };
    s?.addEventListener("change", apply);
    a?.addEventListener("change", apply);
    bt?.addEventListener("change", apply);
  }
}
