import { DashboardService } from "./dashboard-data.js";
import { CLASSES, GENDER_LABELS, classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, badge, emptyState, loadingBlock, skeletonTable, table,
} from "../../shared/components.js";
import { escapeHtml, formatDate } from "../../shared/utils.js";

export class DashboardPage {
  constructor(app) {
    this.app = app;
    this.service = new DashboardService(app.api);
    this.className = "";
    this.streakN = 4;
    this.absentN = 4;
    this.topN = 5;
    this.data = null;
  }

  async mount() {
    const html = await this.app.partial("features/dashboard/dashboard.html");
    this.app.setView(html);
    this.box = document.getElementById("dash-content");

    // External class filter: admin sees all + every class, amin sees own only.
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
    this.box.innerHTML = loadingBlock("جارٍ حساب المؤشرات...");
    try {
      this.data = await this.service.summary({
        className: this.className || null,
        streakN: this.streakN,
        absentN: this.absentN,
        topN: this.topN,
      });
      this.render();
    } catch (err) {
      this.box.innerHTML = `<div class="error-block"><h3>حدث خطأ</h3>
        <p>${escapeHtml(err.message)}</p>
        <button class="btn btn-secondary" id="dash-retry">حاول مجددًا</button></div>`;
      document.getElementById("dash-retry")?.addEventListener("click", () => this.load());
    }
  }

  // ---------- pieces ----------
  kpis(d) {
    const a = d.attendance;
    return `
      <div class="dash-kpis">
        <div class="dash-kpi hero">
          <div class="kpi-num">${a.percent}%</div>
          <div class="kpi-label">نسبة الحضور العامة</div>
          <div class="progress"><span style="width:${a.percent}%"></span></div>
          <div class="kpi-sub">حاضر ${a.present} • غائب ${a.absent} • الكل ${a.total}</div>
        </div>
        <div class="dash-kpi"><div class="kpi-num">${d.counts.boys}</div><div class="kpi-label">الأولاد</div></div>
        <div class="dash-kpi"><div class="kpi-num">${d.counts.fridays}</div><div class="kpi-label">جُمع مسجلة</div></div>
        <div class="dash-kpi"><div class="kpi-num">${d.counts.teachers}</div><div class="kpi-label">خدام تمت متابعتهم</div></div>
      </div>`;
  }

  byClassBars(d) {
    if (d.scope.single_class) return "";
    const rows = Object.entries(d.attendance.by_class)
      .filter(([, v]) => v.total > 0)
      .sort((a, b) => b[1].percent - a[1].percent);
    if (!rows.length) return "";
    return `
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

  topServants(d) {
    if (!d.top_servants.length) {
      return `<div class="dash-section"><h2>أشطر الخدام</h2>
        ${emptyState("لا توجد متابعات بعد", "سجّل متابعة الخدام أولًا لتظهر هنا.")}</div>`;
    }
    return `
      <div class="dash-section">
        <h2>أشطر الخدام</h2>
        <p class="dash-hint">النقاط = مجموع (الحضور + تحضير الدرس + القداس + الافتقاد) في كل المتابعات. المتعادلون مع المركز الأخير يدخلون معه.</p>
        <label class="n-field">عدد الأوائل:
          <input class="input" id="dash-top-n" type="number" min="1" max="50" value="${d.scope.top_n}" />
        </label>
        <ul class="name-list">
          ${d.top_servants.map((s, i) => `
            <li><span><span class="rank rank-${i + 1}">${i + 1}</span>
              <strong> ${escapeHtml(s.teacher_name)}</strong>
              <span class="muted small"> • ${escapeHtml(classLabel(s.class_name))}</span></span>
              <span class="score-pill">${s.score} نقطة</span></li>`).join("")}
        </ul>
      </div>`;
  }

  servantsTable(d) {
    if (!d.servants.length) return "";
    return `
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

  groupList(groups, { emptyTitle, emptyMsg, rowBadge }) {
    const classes = Object.keys(groups).filter((c) => groups[c].length);
    if (!classes.length) {
      return emptyState(emptyTitle, emptyMsg);
    }
    const showHead = classes.length > 1 || !this.data.scope.single_class;
    return classes.map((c) => `
      <div class="class-group">
        ${showHead ? `<h3>${escapeHtml(classLabel(c))}</h3>` : ""}
        <ul class="name-list">
          ${groups[c].map((b) => `
            <li><strong>${escapeHtml(b.boy_name)}</strong>
              <span style="display:flex;gap:6px;align-items:center">${rowBadge(b)}
              <button class="btn btn-secondary btn-sm" data-boy="${b.boy_id}">عرض الملف</button></span></li>`).join("")}
        </ul>
      </div>`).join("");
  }

  streaksSection(d) {
    return `
      <div class="dash-section">
        <h2>المواظبون على الحضور</h2>
        <p class="dash-hint">الحاضرون جمعات متواصلة حتى آخر جمعة مسجلة (${d.last_friday.date ? escapeHtml(formatDate(d.last_friday.date)) : "—"}).</p>
        <label class="n-field">عدد الجمع المتواصلة:
          <input class="input" id="dash-streak-n" type="number" min="1" max="52" value="${d.scope.streak_n}" />
        </label>
        <div id="dash-streaks">${this.groupList(d.streaks, {
          emptyTitle: "لا يوجد مواظبون",
          emptyMsg: `لا أحد وصل ${d.scope.streak_n} جمعات متواصلة. جرّب رقمًا أصغر.`,
          rowBadge: (b) => `<span class="score-pill">${b.streak} جمعة</span>`,
        })}</div>
      </div>`;
  }

  lastFridaySection(d) {
    const lf = d.last_friday;
    if (!lf.date) {
      return `<div class="dash-section"><h2>غياب آخر جمعة</h2>
        ${emptyState("لا يوجد تسجيل بعد", "لم يتم تسجيل أي حضور حتى الآن.")}</div>`;
    }
    return `
      <div class="dash-section">
        <h2>غياب آخر جمعة مسجلة</h2>
        <p class="dash-hint">${escapeHtml(formatDate(lf.date))} — حاضر ${lf.present_count} • غائب ${lf.absent_count}</p>
        <div>${this.groupList(lf.by_class, {
          emptyTitle: "لا يوجد غياب",
          emptyMsg: "الكل كان حاضرًا في آخر جمعة مسجلة.",
          rowBadge: () => badge("غائب", "red"),
        })}</div>
      </div>`;
  }

  frequentSection(d) {
    return `
      <div class="dash-section">
        <h2>الغياب المتكرر</h2>
        <p class="dash-hint">الأولاد الذين غابوا أكثر من العدد المحدد من الجمع.</p>
        <label class="n-field">أكثر من كام جمعة غياب:
          <input class="input" id="dash-absent-n" type="number" min="0" max="52" value="${d.scope.absent_n}" />
        </label>
        <div>${this.groupList(d.frequent_absent, {
          emptyTitle: "لا يوجد غياب متكرر",
          emptyMsg: `لا أحد غاب أكثر من ${d.scope.absent_n} جمعات.`,
          rowBadge: (b) => badge(`غياب ${b.absent_count}`, "red"),
        })}</div>
      </div>`;
  }

  // ---------- render + events ----------
  render() {
    const d = this.data;
    this.box.innerHTML =
      this.kpis(d) + this.byClassBars(d) + this.topServants(d) +
      this.servantsTable(d) + this.streaksSection(d) +
      this.lastFridaySection(d) + this.frequentSection(d);
    this.bindNInputs();
    this.bindBoyButtons();
  }

  bindNInputs() {
    const s = document.getElementById("dash-streak-n");
    const a = document.getElementById("dash-absent-n");
    const t = document.getElementById("dash-top-n");
    let timer = null;
    const apply = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const ns = Math.max(1, Number(s?.value) || 4);
        const na = Math.max(0, Number(a?.value) || 0);
        const nt = Math.max(1, Number(t?.value) || 5);
        if (ns === this.streakN && na === this.absentN && nt === this.topN) return;
        this.streakN = ns;
        this.absentN = na;
        this.topN = nt;
        await this.load();
      }, 600);
    };
    s?.addEventListener("input", apply);
    a?.addEventListener("input", apply);
    t?.addEventListener("input", apply);
  }

  bindBoyButtons() {
    this.box.querySelectorAll("[data-boy]").forEach((btn) => {
      btn.addEventListener("click", () => this.openBoy(btn.dataset.boy));
    });
  }

  async openBoy(boyId) {
    try {
      const p = await this.service.boyProfile(boyId);
      const b = p.boy;
      const row = (k, v) => `<div class="detail-row"><span>${k}</span><span>${v || "—"}</span></div>`;
      const hist = p.history.length
        ? `<div class="table-wrap"><table class="table hist-table"><thead>
             <tr><th>التاريخ</th><th>الحالة</th><th>ملاحظة</th></tr></thead><tbody>
             ${p.history.map((h) => `<tr>
               <td>${escapeHtml(h.action_date || "—")}</td>
               <td>${h.attend === "y" ? badge("حاضر", "green") : badge("غائب", "red")}</td>
               <td>${h.note ? escapeHtml(h.note) : "—"}</td></tr>`).join("")}
           </tbody></table></div>`
        : `<p class="muted">لا يوجد سجل حضور لهذا الولد بعد.</p>`;
      const notes = p.notes.length
        ? `<ul class="notes-list">${p.notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>`
        : `<p class="muted">لا توجد ملاحظات.</p>`;
      Modal.open({
        title: b.boy_name || "ملف الولد",
        sub: `${classLabel(b.class_name)} • نسبة الحضور ${p.percent}% (${p.present}/${p.total})`,
        body: `<div class="details" style="margin-bottom:12px">
            ${row("النوع", GENDER_LABELS[b.gender] || "—")}
            ${row("تاريخ الميلاد", b.birth_date || "—")}
            ${row("السن", b.age ?? "—")}
            ${row("التليفون", b.phone || "—")}
            ${row("العنوان", b.address || "—")}
          </div>
          <h3 style="margin:8px 0">سجل الحضور الكامل</h3>${hist}
          <h3 style="margin:12px 0 4px">الملاحظات</h3>${notes}`,
        actions: [{ label: "إغلاق", kind: "btn-primary" }],
      });
    } catch (err) {
      Toast.error(err.message);
    }
  }
}
