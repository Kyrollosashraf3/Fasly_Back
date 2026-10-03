import { TeacherService } from "./teachers-data.js";
import { classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, compact, emptyState, errorBlock,
  field, formValues, skeletonTable, table,
} from "../../shared/components.js";
import { debounce, escapeHtml, formatDate } from "../../shared/utils.js";

export class TeachersPage {
  constructor(app) {
    this.app = app;
    this.service = new TeacherService(app.api);
    this.teachers = [];
    this.search = "";
  }

  async mount(ctx) {
    this.classId = ctx.params.classId;
    this.canWrite = this.app.auth.canWriteDirectory();
    const html = await this.app.partial("features/teachers/teachers.html");
    this.app.setView(html);

    const label = classLabel(this.classId);
    document.querySelector("[data-crumb-class]").textContent = label;
    document.querySelector("[data-crumb-class]").href = `#/class/${this.classId}`;
    document.querySelector("[data-check-link]").href =
      `#/class/${this.classId}/teachers/check`;

    if (!this.canWrite) {
      for (const id of ["add-teacher", "import-teachers", "teachers-template", "teachers-export"]) {
        const el = document.getElementById(id);
        if (el) el.hidden = true;
      }
    }

    document.getElementById("add-teacher")?.addEventListener("click", () => this.openForm());
    document.getElementById("teachers-template")?.addEventListener("click", (e) =>
      this.download(e.currentTarget, () => this.service.downloadTemplate()));
    document.getElementById("teachers-export")?.addEventListener("click", (e) =>
      this.download(e.currentTarget, () => this.service.downloadExport(this.classId)));
    document.getElementById("import-teachers")?.addEventListener("click", () =>
      document.getElementById("import-teachers-file").click());
    document.getElementById("import-teachers-file")?.addEventListener("change", (e) =>
      this.importFile(e.target.files[0]).finally(() => { e.target.value = ""; }));
    document.getElementById("teachers-search").addEventListener(
      "input", debounce((e) => { this.search = e.target.value.trim().toLowerCase(); this.render(); }, 200)
    );
    await this.load();
  }

  async download(btn, run) {
    btn.disabled = true;
    try {
      await run();
    } catch (err) {
      Toast.error(err.message);
    } finally {
      btn.disabled = false;
    }
  }

  async load() {
    const box = document.getElementById("teachers-content");
    box.innerHTML = skeletonTable(5);
    try {
      const data = await this.service.list(this.classId);
      this.teachers = Array.isArray(data) ? data : [];
      this.render();
    } catch (err) {
      box.innerHTML = errorBlock(err.message, `<button class="btn btn-secondary" id="retry">حاول مجددًا</button>`);
      document.getElementById("retry")?.addEventListener("click", () => this.load());
    }
  }

  render() {
    const box = document.getElementById("teachers-content");
    const rows = this.teachers.filter((t) => {
      if (!this.search) return true;
      return `${t.teacher_name || ""} ${t.phone || ""} ${t.note || ""}`.toLowerCase().includes(this.search);
    });
    if (!rows.length) {
      box.innerHTML = this.teachers.length
        ? emptyState("لا توجد نتائج", "جرّب بحثًا مختلفًا.")
        : emptyState(
            "لا يوجد خدام",
            "لم يتم تسجيل أي خدام في هذا الفصل بعد.",
            this.canWrite
              ? `<button class="btn btn-primary" id="empty-add">+ إضافة خادم</button>`
              : ""
          );
      document.getElementById("empty-add")?.addEventListener("click", () => this.openForm());
      return;
    }
    box.innerHTML = table(
      ["الاسم", "التليفون", "آخر اعتراف/زيارة", "ملاحظة", "إجراءات"],
      rows.map((t) => `
        <tr>
          <td><strong>${escapeHtml(t.teacher_name)}</strong></td>
          <td dir="ltr">${escapeHtml(t.phone || "—")}</td>
          <td>${t.last_visit_date ? escapeHtml(formatDate(t.last_visit_date)) : `<span class="muted">—</span>`}</td>
          <td>${t.note
            ? `<span class="note-indicator" title="${escapeHtml(t.note)}">يوجد ملاحظة</span>`
            : `<span class="muted">—</span>`}</td>
          <td class="cell-actions">
            ${this.canWrite ? `
            <button class="btn-link" data-act="edit" data-id="${t.id}">تعديل</button>
            <button class="btn-link danger" data-act="del" data-id="${t.id}">حذف</button>` : `<span class="muted">—</span>`}
          </td>
        </tr>`).join("")
    );
    box.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const teacher = this.teachers.find((x) => String(x.id) === String(btn.dataset.id));
        if (!teacher) return;
        if (btn.dataset.act === "edit") this.openForm(teacher);
        if (btn.dataset.act === "del") this.remove(teacher);
      });
    });
  }

  openForm(teacher = null) {
    const isEdit = Boolean(teacher);
    const v = teacher || {};
    const classes = this.app.auth.accessibleClasses();
    const body = document.createElement("form");
    body.id = "teacher-form";
    body.innerHTML = `
      ${field({ name: "teacher_name", label: "الاسم بالكامل", value: v.teacher_name || "", required: true })}
      <div class="form-grid">
        ${field({ name: "class_id", label: "الفصل", value: String(v.class_id ?? this.classId),
          options: classes.map((c) => ({ value: String(c.id), label: c.name })) })}
        ${field({ name: "phone", label: "التليفون", type: "tel", value: v.phone || "" })}
      </div>
      ${field({ name: "last_visit_date", label: "آخر اعتراف/زيارة للأب", type: "date", value: v.last_visit_date || "" })}
      ${field({ name: "note", label: "ملاحظة", type: "textarea", value: v.note || "" })}`;
    Modal.open({
      title: isEdit ? "تعديل بيانات خادم" : "إضافة خادم",
      sub: classLabel(this.classId),
      body,
      actions: [
        { label: "إلغاء" },
        {
          label: isEdit ? "حفظ التعديلات" : "إضافة",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            const form = document.getElementById("teacher-form");
            if (!form.reportValidity()) return;
            const values = compact(formValues(form));
            if (values.class_id) values.class_id = Number(values.class_id);
            button.disabled = true;
            try {
              if (isEdit) {
                await this.service.update(teacher.id, values);
                Toast.success("تم تعديل بيانات الخادم.");
              } else {
                await this.service.create(values);
                Toast.success("تمت إضافة الخادم.");
              }
              close();
              await this.load();
            } catch (err) {
              Toast.error(err.message);
              button.disabled = false;
            }
          },
        },
      ],
    });
  }

  async remove(teacher) {
    const ok = await Modal.confirm({
      title: "حذف الخادم؟",
      message: `"${teacher.teacher_name}" سيتم حذفه نهائيًا.`,
    });
    if (!ok) return;
    try {
      await this.service.remove(teacher.id);
      Toast.success("تم حذف الخادم.");
      await this.load();
    } catch (err) {
      Toast.error(err.message);
    }
  }

  async importFile(file) {
    if (!file) return;
    const btn = document.getElementById("import-teachers");
    btn.disabled = true;
    btn.textContent = "جارٍ الاستيراد...";
    try {
      const result = await this.service.importExcel(file);
      const failed = Array.isArray(result.failed) ? result.failed : [];
      const failRows = failed.length
        ? `<div class="details" style="margin-top:8px;max-height:220px;overflow:auto;">${failed.map((f) =>
            `<div class="detail-row"><span>${escapeHtml(f.teacher_name || `صف ${f.row || "؟"}`)}</span><span>${escapeHtml(f.error || "تم التخطي")}</span></div>`
          ).join("")}</div>`
        : `<p class="muted">كل الصفوف اتسجلت بدون أخطاء.</p>`;
      Modal.open({
        title: "انتهى الاستيراد",
        sub: `${file.name} — ${result.created_count} اتضافوا، ${result.failed_count} اتخطوا`,
        body: failRows,
        actions: [{ label: "تمام", kind: "btn-primary" }],
      });
      Toast.success(`اتضاف ${result.created_count} من ملف الإكسل.`);
      await this.load();
    } catch (err) {
      Toast.error(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "استيراد إكسل";
    }
  }
}
