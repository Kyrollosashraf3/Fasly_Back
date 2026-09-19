import { TeacherService } from "./teachers-data.js";
import { classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, compact, emptyState, errorBlock,
  field, formValues, skeletonTable, table,
} from "../../shared/components.js";
import { debounce, escapeHtml } from "../../shared/utils.js";

export class TeachersPage {
  constructor(app) {
    this.app = app;
    this.service = new TeacherService(app.api);
    this.teachers = [];
    this.search = "";
  }

  async mount(ctx) {
    this.className = ctx.params.className;
    const html = await this.app.partial("features/teachers/teachers.html");
    this.app.setView(html);

    document.querySelector("[data-crumb-class]").textContent = classLabel(this.className);
    document.querySelector("[data-crumb-class]").href = `#/class/${this.className}`;
    document.querySelector("[data-check-link]").href = `#/class/${this.className}/teachers/check`;

    document.getElementById("add-teacher").addEventListener("click", () => this.openForm());
    document.getElementById("teachers-search").addEventListener(
      "input", debounce((e) => { this.search = e.target.value.trim().toLowerCase(); this.render(); }, 200)
    );
    await this.load();
  }

  async load() {
    const box = document.getElementById("teachers-content");
    box.innerHTML = skeletonTable(5);
    try {
      const data = await this.service.list(this.className);
      this.teachers = Array.isArray(data) ? data : [];
      this.render();
    } catch (err) {
      box.innerHTML = errorBlock(err.message, `<button class="btn btn-secondary" id="retry">Try again</button>`);
      document.getElementById("retry")?.addEventListener("click", () => this.load());
    }
  }

  render() {
    const box = document.getElementById("teachers-content");
    const rows = this.teachers.filter((t) => {
      if (!this.search) return true;
      return `${t.teacher_name || ""} ${t.phone || ""} ${t.duty || ""}`.toLowerCase().includes(this.search);
    });
    if (!rows.length) {
      box.innerHTML = this.teachers.length
        ? emptyState("No teachers match", "Try a different search.")
        : emptyState(
            "No teachers found",
            "There are no teachers registered in this class yet.",
            `<button class="btn btn-primary" id="empty-add">+ Add Teacher</button>`
          );
      document.getElementById("empty-add")?.addEventListener("click", () => this.openForm());
      return;
    }
    box.innerHTML = table(
      ["Name", "Phone", "Duty", "Note", "Actions"],
      rows.map((t) => `
        <tr>
          <td><strong>${escapeHtml(t.teacher_name)}</strong></td>
          <td>${escapeHtml(t.phone || "—")}</td>
          <td>${escapeHtml(t.duty || "—")}</td>
          <td>${t.note
            ? `<span class="note-indicator" title="${escapeHtml(t.note)}">Has note</span>`
            : `<span class="muted">—</span>`}</td>
          <td class="cell-actions">
            <button class="btn-link" data-act="edit" data-id="${t.id}">Edit</button>
            <button class="btn-link danger" data-act="del" data-id="${t.id}">Delete</button>
          </td>
        </tr>`).join("")
    );
    box.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const teacher = this.teachers.find((x) => x.id === btn.dataset.id);
        if (!teacher) return;
        if (btn.dataset.act === "edit") this.openForm(teacher);
        if (btn.dataset.act === "del") this.remove(teacher);
      });
    });
  }

  openForm(teacher = null) {
    const isEdit = Boolean(teacher);
    const v = teacher || {};
    const body = document.createElement("form");
    body.id = "teacher-form";
    body.innerHTML = `
      ${field({ name: "teacher_name", label: "Full name", value: v.teacher_name || "", required: true })}
      ${field({ name: "phone", label: "Phone", type: "tel", value: v.phone || "" })}
      ${field({ name: "duty", label: "Duty", value: v.duty || "", hint: "e.g. class teacher, group leader, assistant" })}
      ${field({ name: "note", label: "Note", type: "textarea", value: v.note || "" })}`;
    Modal.open({
      title: isEdit ? "Edit teacher" : "Add teacher",
      sub: classLabel(this.className),
      body,
      actions: [
        { label: "Cancel" },
        {
          label: isEdit ? "Save changes" : "Add teacher",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            const form = document.getElementById("teacher-form");
            if (!form.reportValidity()) return;
            button.disabled = true;
            try {
              if (isEdit) {
                await this.service.update(teacher.id, compact(formValues(form)));
                Toast.success("Teacher updated.");
              } else {
                await this.service.create({ ...compact(formValues(form)), class_name: this.className });
                Toast.success("Teacher added.");
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
      title: "Delete teacher?",
      message: `"${teacher.teacher_name}" will be permanently removed.`,
    });
    if (!ok) return;
    try {
      await this.service.remove(teacher.id);
      Toast.success("Teacher deleted.");
      await this.load();
    } catch (err) {
      Toast.error(err.message);
    }
  }
}
