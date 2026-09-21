import { GroupsService } from "./groups-data.js";
import { DashboardService } from "../dashboard/dashboard-data.js";
import { BoyService } from "../boys/boys-data.js";
import { TeacherService } from "../teachers/teachers-data.js";
import { CLASSES, classLabel } from "../../shared/constants.js";
import { FOLLOW_STATUS } from "../../shared/constants.js";
import { Toast, badge, emptyState, loadingBlock, table, Modal } from "../../shared/components.js";
import { escapeHtml, formatDate } from "../../shared/utils.js";
import { openBoyModal } from "../dashboard/dashboard-shared.js";

const STATUS_LABEL = Object.fromEntries(FOLLOW_STATUS.map((s) => [s.value, s.label]));

export class GroupsPage {
  constructor(app) {
    this.app = app;
    this.service = new GroupsService(app.api);
    this.drill = new DashboardService(app.api);
    this.boys = new BoyService(app.api);
    this.teachers = new TeacherService(app.api);
    this.className = "";
    this.teacherId = "";
    this.allBoys = [];
    this.allTeachers = [];
    this.data = null;
  }

  async mount() {
    const html = await this.app.partial("features/groups/groups.html");
    this.app.setView(html);
    this.box = document.getElementById("grp-content");

    const allowed = this.app.auth.accessibleClasses();
    const bothAll = allowed.length > 1 || this.app.auth.isAdmin();
    const classSel = document.getElementById("grp-class");
    classSel.innerHTML = (bothAll ? `<option value="">كل الفصول</option>` : "") +
      (bothAll ? CLASSES : allowed).map((c) => `<option value="${c}">${classLabel(c)}</option>`).join("");
    classSel.addEventListener("change", async () => {
      this.className = classSel.value;
      this.teacherId = "";
      await this.reloadBase();
    });

    document.getElementById("grp-teacher").addEventListener("change", async (e) => {
      this.teacherId = e.target.value;
      await this.load();
    });
    document.getElementById("grp-export").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        await this.service.exportFile(this.className || null);
        Toast.success("تم تنزيل الشيت.");
      } catch (err) {
        Toast.error(err.message);
      } finally {
        btn.disabled = false;
      }
    });
    document.getElementById("grp-assign-save").addEventListener("click", () => this.saveAssign());
    document.getElementById("grp-import").addEventListener("click", () =>
      document.getElementById("grp-import-file").click());
    document.getElementById("grp-import-file").addEventListener("change", (e) =>
      this.importFile(e.target.files[0]).finally(() => { e.target.value = ""; }));

    await this.reloadBase();
  }

  async reloadBase() {
    try {
      const [boys, teachers] = await Promise.all([
        this.boys.list(this.className || undefined),
        this.teachers.list(this.className || undefined),
      ]);
      this.allBoys = Array.isArray(boys) ? boys : [];
      this.allTeachers = Array.isArray(teachers) ? teachers : [];
    } catch (err) {
      this.allBoys = [];
      this.allTeachers = [];
      Toast.error(err.message);
    }
    const tSel = document.getElementById("grp-teacher");
    tSel.innerHTML = `<option value="">كل الخدام</option>` +
      this.allTeachers.map((t) => `<option value="${t.id}">${escapeHtml(t.teacher_name)}</option>`).join("");
    tSel.value = this.teacherId;
    const aSel = document.getElementById("grp-assign-teacher");
    aSel.innerHTML = `<option value="">اختر الخادم...</option>` +
      this.allTeachers.map((t) => `<option value="${t.id}">${escapeHtml(t.teacher_name)}</option>`).join("");
    this.renderAssignBoys();
    await this.load();
  }

  renderAssignBoys() {
    const box = document.getElementById("grp-assign-boys");
    // Only boys with no group yet — already-grouped boys are managed
    // from their servant's section (or moved via the import sheet).
    const free = this.allBoys.filter((b) => !b.follow_teacher_id);
    if (!free.length) {
      box.innerHTML = this.allBoys.length
        ? emptyState("كل الأولاد متوزعون", "لا يوجد أولاد بدون مجموعة في هذا الفصل.")
        : emptyState("لا يوجد أولاد", "اختر فصلًا به أولاد مسجلون.");
      return;
    }
    box.innerHTML = `<div class="assign-grid">${free.map((b) => `
      <label><input type="checkbox" class="check" value="${b.id}" />${escapeHtml(b.boy_name)}</label>`).join("")}</div>`;
  }

  pickedBoys() {
    return [...document.querySelectorAll("#grp-assign-boys input:checked")].map((c) => c.value);
  }

  async saveAssign() {
    const tid = document.getElementById("grp-assign-teacher").value;
    const ids = this.pickedBoys();
    if (!tid) { Toast.error("اختر الخادم أولًا."); return; }
    if (!ids.length) { Toast.error("علّم على ولد واحد على الأقل."); return; }
    try {
      const r = await this.service.assign(tid, ids);
      Toast.success(`اتوزع ${r.assigned} على ${r.teacher_name}.`);
      await this.reloadBase();
    } catch (err) {
      Toast.error(err.message);
    }
  }

  async unassignBoy(boyId, boyName) {
    try {
      await this.service.unassign([boyId]);
      Toast.success(`اتلغى توزيع ${boyName}.`);
      await this.reloadBase();
    } catch (err) {
      Toast.error(err.message);
    }
  }
  async importFile(file) {
    if (!file) return;
    const btn = document.getElementById("grp-import");
    btn.disabled = true;
    btn.textContent = "جارٍ الاستيراد...";
    try {
      const result = await this.service.importGroups(file);
      const failed = Array.isArray(result.failed) ? result.failed : [];
      const failRows = failed.length
        ? `<div class="details" style="margin-top:8px;max-height:220px;overflow:auto;">${failed.map((f) =>
            `<div class="detail-row"><span>${escapeHtml(f.boy_name || "؟")} ← ${escapeHtml(f.teacher_name || "؟")}</span><span>${escapeHtml(f.error || "تم التخطي")}</span></div>`
          ).join("")}</div>`
        : `<p class="muted">كل الصفوف اتوزعت بدون أخطاء.</p>`;
      Modal.open({
        title: "انتهى الاستيراد",
        sub: `${file.name} — ${result.assigned_count} اتوزعوا، ${result.failed_count} اتخطوا`,
        body: failRows,
        actions: [{ label: "تمام", kind: "btn-primary" }],
      });
      Toast.success(`اتوزع ${result.assigned_count} من الشيت.`);
      await this.reloadBase();
    } catch (err) {
      Toast.error(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "رفع شيت التوزيع";
    }
  }

  async load() {
    this.box.innerHTML = loadingBlock("جارٍ تحميل المجموعات...");
    try {
      this.data = await this.service.list(this.className || null, this.teacherId || null);
      this.render();
    } catch (err) {
      this.box.innerHTML = `<div class="error-block"><h3>حدث خطأ</h3>
        <p>${escapeHtml(err.message)}</p></div>`;
    }
  }

  boyRow(b) {
    const fu = b.last_followup;
    return `<tr>
      <td><strong>${escapeHtml(b.boy_name)}</strong>${b.issue_flag ? ` <span class="flag-dot" title="محتاج متابعة"></span>` : ""}</td>
      <td dir="ltr">${escapeHtml(b.phone || "—")}</td>
      <td>${b.present}/${b.total} (${b.percent}%)</td>
      <td>${fu ? escapeHtml(formatDate(fu.action_date)) : "—"}</td>
      <td>${fu ? badge(STATUS_LABEL[fu.status] || fu.status || "—", "yellow") : "—"}</td>
      <td>${b.note ? `<span class="note-indicator" title="${escapeHtml(b.note)}">عرض</span>` : "—"}</td>
      <td class="cell-actions"><button class="btn-link" data-boy="${b.boy_id}">عرض الملف</button><button class="btn-link danger" data-unassign="${b.boy_id}" data-name="${escapeHtml(b.boy_name)}">إلغاء التوزيع</button></td>
    </tr>`;
  }

  render() {
    const d = this.data;
    let html = "";
    const groups = this.teacherId ? d.groups.filter((g) => g.teacher_id === this.teacherId) : d.groups;
    if (!groups.length && !d.unassigned.length) {
      html = emptyState("لا توجد مجموعات", "سجّل خدامًا وأولادًا ثم وزّع المجموعات من الأعلى.");
    } else {
      html = groups.map((g) => `
        <div class="dash-section">
          <div class="group-head"><h3>مجموعة الخادم: ${escapeHtml(g.teacher_name)}</h3>
            <span class="muted small">${escapeHtml(classLabel(g.class_name))} • ${g.boys_count} أولاد${g.phone ? ` • ${escapeHtml(g.phone)}` : ""}</span>
            <button class="btn btn-secondary btn-sm" data-edit-group="${g.teacher_id}">تعديل المجموعة</button>
          </div>
          ${g.boys.length ? table(
            ["الاسم", "التليفون", "الحضور", "آخر افتقاد", "الطريقة", "ملاحظات", ""],
            g.boys.map((b) => this.boyRow(b)).join("")
          ) : `<p class="muted">لا يوجد أولاد في هذه المجموعة بعد.</p>`}
        </div>`).join("");
      if (d.unassigned.length && !this.teacherId) {
        html += `
        <div class="dash-section">
          <div class="group-head"><h3>بدون مجموعة</h3>
            <span class="muted small">${d.unassigned_count} أولاد</span></div>
          ${table(
            ["الاسم", "التليفون", "الحضور", "آخر افتقاد", "الطريقة", "ملاحظات", ""],
            d.unassigned.map((b) => this.boyRow(b)).join("")
          )}
        </div>`;
      }
    }
    this.box.innerHTML = html;
    this.box.querySelectorAll("[data-boy]").forEach((btn) => {
      btn.addEventListener("click", () => openBoyModal(this.drill, btn.dataset.boy));
    });
    this.box.querySelectorAll("[data-unassign]").forEach((btn) => {
      btn.addEventListener("click", () => this.unassignBoy(btn.dataset.unassign, btn.dataset.name));
    });
    this.box.querySelectorAll("[data-edit-group]").forEach((btn) => {
      btn.addEventListener("click", () => this.openGroupEditor(btn.dataset.editGroup));
    });
  }

  async openGroupEditor(teacherId) {
    const teacher = this.allTeachers.find((t) => t.id === teacherId);
    if (!teacher) { Toast.error("الخادم غير موجود."); return; }
    const { body } = Modal.open({
      title: `مجموعة ${teacher.teacher_name}`,
      sub: "إضافة من غير الموزعين أو حذف من المجموعة — يحفظ فورًا.",
      body: `<div id="grp-editor"></div>`,
      actions: [{ label: "إغلاق", kind: "btn-primary" }],
    });
    const paint = () => {
      const el = body.querySelector("#grp-editor");
      const grp = (this.data?.groups || []).find((g) => g.teacher_id === teacherId);
      const members = grp ? grp.boys : [];
      const free = this.allBoys.filter((b) => !b.follow_teacher_id);
      el.innerHTML = `
        <h3 style="margin:0 0 8px">الأولاد الحاليون (${members.length})</h3>
        ${members.length ? `<ul class="name-list">${members.map((b) => `
          <li><strong>${escapeHtml(b.boy_name)}</strong>
            <button class="btn-link danger" data-ed-del="${b.boy_id}">حذف</button></li>`).join("")}</ul>`
          : `<p class="muted">لا يوجد أولاد في المجموعة بعد.</p>`}
        <h3 style="margin:14px 0 8px">إضافة ولد جديد</h3>
        ${free.length ? `
        <div style="display:flex;gap:8px">
          <select class="input" id="grp-ed-add" style="flex:1">
            ${free.map((b) => `<option value="${b.id}">${escapeHtml(b.boy_name)}</option>`).join("")}
          </select>
          <button class="btn btn-primary btn-sm" id="grp-ed-add-btn">إضافة</button>
        </div>` : `<p class="muted">لا يوجد أولاد بدون مجموعة.</p>`}`;
      el.querySelectorAll("[data-ed-del]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          btn.disabled = true;
          try {
            await this.service.unassign([btn.dataset.edDel]);
            await this.reloadBase();
            paint();
          } catch (err) {
            Toast.error(err.message);
            btn.disabled = false;
          }
        });
      });
      el.querySelector("#grp-ed-add-btn")?.addEventListener("click", async (e) => {
        const btn = e.currentTarget;
        const sel = el.querySelector("#grp-ed-add");
        if (!sel?.value) return;
        btn.disabled = true;
        try {
          await this.service.assign(teacherId, [sel.value]);
          Toast.success("اتضاف للمجموعة.");
          await this.reloadBase();
          paint();
        } catch (err) {
          Toast.error(err.message);
          btn.disabled = false;
        }
      });
    };
    paint();
  }
}
