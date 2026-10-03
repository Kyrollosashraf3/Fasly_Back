import { BoyService } from "./boys-data.js";
import { GENDER_OPTIONS, GENDER_LABELS, classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, compact, emptyState, errorBlock,
  field, formValues, skeletonTable, table,
} from "../../shared/components.js";
import { calcAge, debounce, escapeHtml } from "../../shared/utils.js";

export class BoysPage {
  constructor(app) {
    this.app = app;
    this.service = new BoyService(app.api);
    this.boys = [];
    this.search = "";
    this.flaggedOnly = false;
  }

  async mount(ctx) {
    this.classId = ctx.params.classId;
    this.canWrite = this.app.auth.canWriteDirectory();
    const html = await this.app.partial("features/boys/boys.html");
    this.app.setView(html);

    const label = classLabel(this.classId);
    document.querySelector("[data-crumb-class]").textContent = label;
    document.querySelector("[data-crumb-class]").href = `#/class/${this.classId}`;
    document.querySelector("[data-attendance-link]").href =
      `#/class/${this.classId}/boys/attendance`;

    if (!this.canWrite) {
      for (const id of ["add-boy", "import-boys", "boys-template", "boys-export"]) {
        const el = document.getElementById(id);
        if (el) el.hidden = true;
      }
    }

    document.getElementById("add-boy")?.addEventListener("click", () => this.openForm());
    document.getElementById("boys-template")?.addEventListener("click", (e) =>
      this.download(e.currentTarget, () => this.service.downloadTemplate()));
    document.getElementById("boys-export")?.addEventListener("click", (e) =>
      this.download(e.currentTarget, () => this.service.downloadExport(this.classId)));
    document.getElementById("import-boys")?.addEventListener("click", () =>
      document.getElementById("import-boys-file").click());
    document.getElementById("import-boys-file")?.addEventListener("change", (e) =>
      this.importFile(e.target.files[0]).finally(() => { e.target.value = ""; }));
    document.getElementById("boys-search").addEventListener(
      "input", debounce((e) => { this.search = e.target.value.trim().toLowerCase(); this.render(); }, 200)
    );
    document.getElementById("boys-flag-tabs").addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      this.flaggedOnly = btn.dataset.flag === "true";
      document.querySelectorAll("#boys-flag-tabs button").forEach((b) =>
        b.classList.toggle("active", b === btn));
      this.render();
    });

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
    const box = document.getElementById("boys-content");
    box.innerHTML = skeletonTable(6);
    try {
      const data = await this.service.list(this.classId);
      this.boys = Array.isArray(data) ? data : [];
      this.render();
    } catch (err) {
      box.innerHTML = errorBlock(err.message, `<button class="btn btn-secondary" id="retry">حاول مجددًا</button>`);
      document.getElementById("retry")?.addEventListener("click", () => this.load());
    }
  }

  filtered() {
    return this.boys.filter((b) => {
      if (this.flaggedOnly && !b.issue_flag) return false;
      if (!this.search) return true;
      const hay = `${b.boy_name || ""} ${b.phone || ""} ${b.address || ""}`.toLowerCase();
      return hay.includes(this.search);
    });
  }

  render() {
    const box = document.getElementById("boys-content");
    const rows = this.filtered();
    if (!rows.length) {
      box.innerHTML = this.boys.length
        ? emptyState("لا توجد نتائج", "جرّب بحثًا مختلفًا.")
        : emptyState(
            "لا يوجد أولاد",
            "لم يتم تسجيل أي أولاد في هذا الفصل بعد.",
            this.canWrite
              ? `<button class="btn btn-primary" id="empty-add">+ إضافة ولد</button>`
              : ""
          );
      document.getElementById("empty-add")?.addEventListener("click", () => this.openForm());
      return;
    }
    box.innerHTML = table(
      ["الاسم", "النوع", "السن", "التليفون", "ملاحظة", "إجراءات"],
      rows.map((b) => `
        <tr>
          <td><strong>${b.issue_flag ? `<span class="flag-dot" title="محتاج متابعة"></span>` : ""}${escapeHtml(b.boy_name)}</strong></td>
          <td>${escapeHtml(GENDER_LABELS[b.gender] || b.gender || "—")}</td>
          <td>${escapeHtml(calcAge(b.birth_date, b.age))}</td>
          <td>${escapeHtml(b.phone || "—")}</td>
          <td>${b.note
            ? `<span class="note-indicator" title="${escapeHtml(b.note)}">يوجد ملاحظة</span>`
            : `<span class="muted">—</span>`}</td>
          <td class="cell-actions">
            <button class="btn-link" data-act="view" data-id="${b.id}">عرض</button>
            ${this.canWrite ? `
            <button class="btn-link" data-act="edit" data-id="${b.id}">تعديل</button>
            <button class="btn-link danger" data-act="del" data-id="${b.id}">حذف</button>` : ""}
          </td>
        </tr>`).join("")
    );
    box.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const boy = this.boys.find((x) => String(x.id) === String(btn.dataset.id));
        if (!boy) return;
        if (btn.dataset.act === "view") this.openView(boy);
        if (btn.dataset.act === "edit") this.openForm(boy);
        if (btn.dataset.act === "del") this.remove(boy);
      });
    });
  }

  openView(b) {
    const row = (k, v) =>
      `<div class="detail-row"><span>${k}</span><span>${v || "—"}</span></div>`;
    Modal.open({
      title: b.boy_name,
      sub: `${classLabel(b.class_id)}${b.issue_flag ? " • محتاج متابعة" : ""}`,
      body: `<div class="details">
        ${row("النوع", escapeHtml(GENDER_LABELS[b.gender] || b.gender || "—"))}
        ${row("تاريخ الميلاد", escapeHtml(b.birth_date || "—"))}
        ${row("السن", escapeHtml(calcAge(b.birth_date, b.age)))}
        ${row("التليفون", escapeHtml(b.phone || "—"))}
        ${row("تليفون آخر", escapeHtml(b.phone_2 || "—"))}
        ${row("المنطقة", escapeHtml(b.zone || "—"))}
        ${row("العنوان", escapeHtml(b.address || "—"))}
        ${row("الموقع", b.location ? `<a href="${escapeHtml(b.location)}" target="_blank" rel="noopener">فتح الخريطة</a>` : "—")}
        ${row("ملاحظة", escapeHtml(b.note || "—"))}
      </div>`,
      actions: [
        { label: "إغلاق" },
        ...(this.canWrite
          ? [{ label: "تعديل", kind: "btn-primary", onClick: ({ close }) => { close(); this.openForm(b); } }]
          : []),
      ],
    });
  }

  openForm(boy = null) {
    const isEdit = Boolean(boy);
    const v = boy || {};
    const classes = this.app.auth.accessibleClasses();
    const body = document.createElement("form");
    body.id = "boy-form";
    body.innerHTML = `
      ${field({ name: "boy_name", label: "الاسم بالكامل", value: v.boy_name || "", required: true })}
      <div class="form-grid">
        ${field({ name: "gender", label: "النوع", value: v.gender || "m", options: GENDER_OPTIONS })}
        ${field({ name: "birth_date", label: "تاريخ الميلاد (السن بيتحسب تلقائي)", type: "date", value: v.birth_date || "" })}
      </div>
      <div class="form-grid">
        ${field({ name: "class_id", label: "الفصل", value: String(v.class_id ?? this.classId),
          options: classes.map((c) => ({ value: String(c.id), label: c.name })) })}
        ${field({ name: "phone", label: "التليفون", type: "tel", value: v.phone || "" })}
      </div>
      <div class="form-grid">
        ${field({ name: "phone_2", label: "تليفون آخر", type: "tel", value: v.phone_2 || "" })}
        ${field({ name: "zone", label: "المنطقة", value: v.zone || "" })}
      </div>
      ${field({ name: "address", label: "العنوان", value: v.address || "" })}
      ${field({ name: "location", label: "الموقع (لينك الخريطة)", value: v.location || "" })}
      ${field({ name: "note", label: "ملاحظة", type: "textarea", value: v.note || "" })}
      <div class="field check-field">
        <label><input type="checkbox" class="check" name="issue_flag"${v.issue_flag ? " checked" : ""} /> محتاج متابعة</label>
      </div>`;
    Modal.open({
      title: isEdit ? "تعديل بيانات ولد" : "إضافة ولد",
      sub: classLabel(this.classId),
      body,
      actions: [
        { label: "إلغاء" },
        {
          label: isEdit ? "حفظ التعديلات" : "إضافة",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            const form = document.getElementById("boy-form");
            if (!form.reportValidity()) return;
            const values = formValues(form);
            values.issue_flag = form.issue_flag.checked;
            values.class_id = Number(values.class_id);
            button.disabled = true;
            try {
              if (isEdit) {
                await this.service.update(boy.id, compact(values));
                Toast.success("تم تعديل البيانات.");
              } else {
                await this.service.create(compact(values));
                Toast.success("تمت إضافة الولد.");
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

  async remove(boy) {
    const ok = await Modal.confirm({
      title: "حذف الولد؟",
      message: `"${boy.boy_name}" سيتم حذفه نهائيًا.`,
    });
    if (!ok) return;
    try {
      await this.service.remove(boy.id);
      Toast.success("تم حذف الولد.");
      await this.load();
    } catch (err) {
      Toast.error(err.message);
    }
  }

  async importFile(file) {
    if (!file) return;
    const btn = document.getElementById("import-boys");
    btn.disabled = true;
    btn.textContent = "جارٍ الاستيراد...";
    try {
      const result = await this.service.importExcel(file);
      const failed = Array.isArray(result.failed) ? result.failed : [];
      const failRows = failed.length
        ? `<div class="details" style="margin-top:8px;max-height:220px;overflow:auto;">${failed.map((f) =>
            `<div class="detail-row"><span>${escapeHtml(f.boy_name || `صف ${f.row || "؟"}`)}</span><span>${escapeHtml(f.error || "تم التخطي")}</span></div>`
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
