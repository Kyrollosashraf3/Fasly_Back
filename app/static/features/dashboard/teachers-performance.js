import { DashboardService } from "./dashboard-data.js";
import { classLabel } from "../../shared/constants.js";
import { emptyState, loadingBlock, table } from "../../shared/components.js";
import { escapeHtml } from "../../shared/utils.js";
import { nOptions, trendChart } from "./dashboard-shared.js";

export class TeachersPerformancePage {
  constructor(app) {
    this.app = app;
    this.service = new DashboardService(app.api);
    this.classId = "";
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
    const showAll = this.app.auth.isManager() && allowed.length > 1;
    sel.innerHTML = (showAll ? `<option value="">ÙƒÙ„ Ø§Ù„ÙØµÙˆÙ„</option>` : "") +
      allowed.map((c) =>
        `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    if (!showAll && allowed.length) {
      this.classId = allowed[0].id;
      sel.value = String(allowed[0].id);
    }
    sel.addEventListener("change", async () => {
      this.classId = sel.value;
      await this.load();
    });

    await this.load();
  }

  async load() {
    this.box.innerHTML = loadingBlock("Ø¬Ø§Ø±Ù Ø­Ø³Ø§Ø¨ Ù…Ø¤Ø´Ø±Ø§Øª Ø§Ù„Ø®Ø¯Ø§Ù…...");
    try {
      this.data = await this.service.summary({
        classId: this.classId || null,
        topN: this.topN,
        teacherTrendN: this.teacherTrendN,
      });
      this.render();
    } catch (err) {
      this.box.innerHTML = `<div class="error-block"><h3>Ø­Ø¯Ø« Ø®Ø·Ø£</h3>
        <p>${escapeHtml(err.message)}</p>
        <button class="btn btn-secondary" id="dash-retry">Ø­Ø§ÙˆÙ„ Ù…Ø¬Ø¯Ø¯Ù‹Ø§</button></div>`;
      document.getElementById("dash-retry")?.addEventListener("click", () => this.load());
    }
  }

  render() {
    const d = this.data;
    const totalChecks = d.servants.reduce((n, s) => n + s.checks, 0);
    const avg = d.servants.length
      ? (d.servants.reduce((n, s) => n + s.score, 0) / d.servants.length).toFixed(1)
      : "â€”";

    let html = `
      <div class="dash-kpis">
        <div class="dash-kpi hero">
          <div class="kpi-num">${d.counts.teachers}</div>
          <div class="kpi-label">Ø®Ø¯Ø§Ù… ØªÙ…Øª Ù…ØªØ§Ø¨Ø¹ØªÙ‡Ù…</div>
          <div class="kpi-sub">Ù…ØªØ§Ø¨Ø¹Ø§Øª Ù…Ø³Ø¬Ù„Ø© ${totalChecks} â€¢ Ù…ØªÙˆØ³Ø· Ø§Ù„Ù†Ù‚Ø§Ø· ${avg}</div>
        </div>
        <div class="dash-kpi"><div class="kpi-num">${totalChecks}</div><div class="kpi-label">Ù…ØªØ§Ø¨Ø¹Ø§Øª</div></div>
        <div class="dash-kpi"><div class="kpi-num">${avg}</div><div class="kpi-label">Ù…ØªÙˆØ³Ø· Ø§Ù„Ù†Ù‚Ø§Ø·</div></div>
      </div>`;

    html += `
      <div class="dash-section">
        <h2>Ù…Ù†Ø­Ù†Ù‰ Ø­Ø¶ÙˆØ± Ø§Ù„Ø®Ø¯Ø§Ù…</h2>
        <p class="dash-hint">Ø¹Ø¯Ø¯ Ø§Ù„Ø®Ø¯Ø§Ù… Ø§Ù„Ø­Ø§Ø¶Ø±ÙŠÙ† ÙÙŠ ÙƒÙ„ Ø¬Ù…Ø¹Ø© (Ù…Ù† Ø§Ù„Ø£Ù‚Ø¯Ù… Ù„Ù„Ø£Ø­Ø¯Ø«).</p>
        <label class="n-field">Ø¹Ø¯Ø¯ Ø§Ù„Ø¬Ù…Ø¹:
          <select class="input" id="dash-teacher-trend-n">${nOptions(d.scope.teacher_trend_n, 1, 12)}</select>
        </label>
        <div class="card">${d.teachers_trend.length ? trendChart(d.teachers_trend) : emptyState("Ù„Ø§ ØªÙˆØ¬Ø¯ Ø¨ÙŠØ§Ù†Ø§Øª", "Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…ØªØ§Ø¨Ø¹Ø§Øª Ù…Ø³Ø¬Ù„Ø© Ø¨Ø¹Ø¯.")}</div>
      </div>`;

    html += `
      <div class="dash-section">
        <h2>Ø£Ø´Ø·Ø± Ø§Ù„Ø®Ø¯Ø§Ù…</h2>
        <p class="dash-hint">Ø§Ù„Ù†Ù‚Ø§Ø· = Ù…Ø¬Ù…ÙˆØ¹ (Ø§Ù„Ø­Ø¶ÙˆØ± + ØªØ­Ø¶ÙŠØ± Ø§Ù„Ø¯Ø±Ø³ + Ø§Ù„Ù‚Ø¯Ø§Ø³ + Ø§Ù„Ø§ÙØªÙ‚Ø§Ø¯) ÙÙŠ ÙƒÙ„ Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø§Øª. Ø§Ù„Ù…ØªØ¹Ø§Ø¯Ù„ÙˆÙ† Ù…Ø¹ Ø§Ù„Ù…Ø±ÙƒØ² Ø§Ù„Ø£Ø®ÙŠØ± ÙŠØ¯Ø®Ù„ÙˆÙ† Ù…Ø¹Ù‡.</p>
        <label class="n-field">Ø¹Ø¯Ø¯ Ø§Ù„Ø£ÙˆØ§Ø¦Ù„:
          <select class="input" id="dash-top-n">${nOptions(d.scope.top_n, 1, 12)}</select>
        </label>`;
    if (!d.top_servants.length) {
      html += emptyState("Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…ØªØ§Ø¨Ø¹Ø§Øª Ø¨Ø¹Ø¯", "Ø³Ø¬Ù‘Ù„ Ù…ØªØ§Ø¨Ø¹Ø© Ø§Ù„Ø®Ø¯Ø§Ù… Ø£ÙˆÙ„Ù‹Ø§ Ù„ØªØ¸Ù‡Ø± Ù‡Ù†Ø§.");
    } else {
      html += `
        <ul class="name-list">
          ${d.top_servants.map((s, i) => `
            <li><span><span class="rank rank-${i + 1}">${i + 1}</span>
              <strong> ${escapeHtml(s.teacher_name)}</strong>
              <span class="muted small"> â€¢ ${escapeHtml(classLabel(s.class_id))}</span></span>
              <span class="score-pill">${s.score} Ù†Ù‚Ø·Ø©</span></li>`).join("")}
        </ul>`;
    }
    html += `</div>`;

    if (d.servants.length) {
      html += `
      <div class="dash-section">
        <h2>Ø£Ø¯Ø§Ø¡ Ø§Ù„Ø®Ø¯Ø§Ù…</h2>
        <p class="dash-hint">Ù…Ø¬Ù…ÙˆØ¹ Ø¹Ù„Ø§Ù…Ø§Øª âœ“ Ø§Ù„ØªÙŠ Ø¬Ù…Ø¹Ù‡Ø§ ÙƒÙ„ Ø®Ø§Ø¯Ù… ÙÙŠ ÙƒÙ„ Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø§Øª Ø§Ù„Ù…Ø³Ø¬Ù„Ø©.</p>
        ${table(
          ["Ø§Ù„Ø®Ø§Ø¯Ù…", "Ø§Ù„ÙØµÙ„", "Ø§Ù„Ù†Ù‚Ø§Ø·", "Ù…ØªØ§Ø¨Ø¹Ø§Øª", "Ø­Ø§Ø¶Ø±", "Ø¯Ø±Ø³", "Ù‚Ø¯Ø§Ø³", "Ø§ÙØªÙ‚Ø§Ø¯"],
          d.servants.map((s) => `
            <tr><td><strong>${escapeHtml(s.teacher_name)}</strong></td>
            <td>${escapeHtml(classLabel(s.class_id))}</td>
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
