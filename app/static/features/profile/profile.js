import { ROLE_LABELS, ROLE_OPTIONS, classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, badge, compact, emptyState, errorBlock,
  field, formValues, skeletonTable, table,
} from "../../shared/components.js";
import { escapeHtml } from "../../shared/utils.js";

const OWNER_ROLES = ["teacher", "admin"];

export class ProfilePage {
  constructor(app) {
    this.app = app;
    this.teachers = [];
    this.boys = [];
  }

  async mount() {
    const html = await this.app.partial("features/profile/profile.html");
    this.app.setView(html);
    const user = this.app.auth.currentUser();
    const box = document.getElementById("profile-content");

    if (this.app.auth.isManager()) {
      await this.loadPeople();
    }

    const linked = this.linkedLabel(user);
    box.innerHTML = `
      <div class="card-grid profile-grid">
        <div class="card">
          <h3 style="margin-bottom:12px">الملف الشخصي</h3>
          <div class="details">
            <div class="detail-row"><span>الاسم</span><span>${escapeHtml(user.display_name || "—")}</span></div>
            <div class="detail-row"><span>البريد الإلكتروني</span><span>${escapeHtml(user.email || "—")}</span></div>
            <div class="detail-row"><span>الصلاحية</span><span>${badge(this.app.auth.roleLabel(user.role), user.role === "super_admin" ? "yellow" : "")}</span></div>
            <div class="detail-row"><span>المسند إليه</span><span>${escapeHtml(linked)}</span></div>
          </div>
        </div>
        <div class="card">
          <h3 style="margin-bottom:12px">تغيير كلمة المرور</h3>
          <form id="pw-form">
            <div class="field">
              <label for="pw-new">كلمة المرور الجديدة (8 حروف على الأقل)</label>
              <input class="input" id="pw-new" name="password" type="password" minlength="8" required autocomplete="new-password" />
            </div>
            <button class="btn btn-secondary" type="submit" id="pw-submit">تحديث كلمة المرور</button>
          </form>
        </div>
      </div>`;

    document.getElementById("pw-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("pw-new");
      if (!input.reportValidity()) return;
      const btn = document.getElementById("pw-submit");
      btn.disabled = true;
      try {
        await this.app.api.patch(`/auth/users/${user.id}`, { password: input.value });
        input.value = "";
        Toast.success("تم تحديث كلمة المرور.");
      } catch (err) {
        Toast.error(err.message);
      } finally {
        btn.disabled = false;
      }
    });

    if (this.app.auth.isManager()) {
      await this.renderUsers();
    }
  }

  async loadPeople() {
    const [teachers, boys] = await Promise.all([
      this.app.api.get("/teachers").catch(() => []),
      this.app.api.get("/boys").catch(() => []),
    ]);
    this.teachers = Array.isArray(teachers) ? teachers : [];
    this.boys = Array.isArray(boys) ? boys : [];
  }

  teacherName(id) {
    const t = this.teachers.find((x) => x.id === id);
    return t ? t.teacher_name : null;
  }

  boyName(id) {
    const b = this.boys.find((x) => x.id === id);
    return b ? b.boy_name : null;
  }

  linkedLabel(user) {
    if (!user) return "—";
    if (user.role === "super_admin") return "كل الفصول";
    if (user.teacher_id) {
      const name = this.teacherName(user.teacher_id) || `خادم #${user.teacher_id}`;
      const classId = (this.teachers.find((t) => t.id === user.teacher_id) || {}).class_id;
      return classId ? `${name} — ${classLabel(classId)}` : name;
    }
    if (user.boy_id) {
      const name = this.boyName(user.boy_id) || `ولد #${user.boy_id}`;
      const classId = (this.boys.find((b) => b.id === user.boy_id) || {}).class_id;
      return classId ? `${name} — ${classLabel(classId)}` : name;
    }
    return "—";
  }

  async renderUsers() {
    const section = document.getElementById("users-section");
    section.innerHTML = `<h2 class="section-title">الحسابات</h2>
      <div class="toolbar"><div class="toolbar-group"></div>
      <div class="toolbar-group"><button class="btn btn-primary" id="add-user">+ إضافة حساب</button></div></div>
      <div id="users-content">${skeletonTable(4)}</div>`;
    document.getElementById("add-user").addEventListener("click", () => this.openUserForm());
    const box = document.getElementById("users-content");
    try {
      const users = await this.app.api.get("/auth/users");
      const list = Array.isArray(users) ? users : [];
      if (!list.length) {
        box.innerHTML = emptyState("لا توجد حسابات", "لا توجد حسابات مسجلة بعد.");
        return;
      }
      box.innerHTML = table(
        ["البريد الإلكتروني", "الصلاحية", "المسند إليه", "إجراءات"],
        list.map((u) => `
          <tr>
            <td><strong>${escapeHtml(u.email)}</strong></td>
            <td>${badge(ROLE_LABELS[u.role] || u.role, u.role === "super_admin" ? "yellow" : "")}</td>
            <td>${escapeHtml(this.linkedLabel(u))}</td>
            <td class="cell-actions">
              <button class="btn-link" data-uact="edit" data-id="${u.id}">تعديل</button>
              <button class="btn-link danger" data-uact="del" data-id="${u.id}">حذف</button>
            </td>
          </tr>`).join("")
      );
      box.querySelectorAll("button[data-uact]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const u = list.find((x) => String(x.id) === String(btn.dataset.id));
          if (!u) return;
          if (btn.dataset.uact === "edit") this.openUserForm(u);
          if (btn.dataset.uact === "del") this.deleteUser(u);
        });
      });
    } catch (err) {
      box.innerHTML = errorBlock(err.message);
    }
  }

  ownerOptions(role, selected) {
    if (OWNER_ROLES.includes(role)) {
      return [{ value: "", label: "— اختر الخادم —" }].concat(
        this.teachers.map((t) => ({
          value: String(t.id),
          label: `${t.teacher_name} (${classLabel(t.class_id)})`,
          _t: t.id === selected,
        }))
      );
    }
    if (role === "user") {
      return [{ value: "", label: "— اختر الولد —" }].concat(
        this.boys.map((b) => ({
          value: String(b.id),
          label: `${b.boy_name} (${classLabel(b.class_id)})`,
          _t: b.id === selected,
        }))
      );
    }
    return [{ value: "", label: "بدون (أدمن عام)" }];
  }

  openUserForm(user = null) {
    const isEdit = Boolean(user);
    const v = user || {};
    const canSuper = this.app.auth.isSuperAdmin();
    const roles = ROLE_OPTIONS.filter((r) => r.value !== "super_admin" || canSuper);
    const role = v.role || "user";

    const body = document.createElement("form");
    body.id = "user-form";
    body.innerHTML = `
      ${field({ name: "email", label: "البريد الإلكتروني", type: "email", value: v.email || "", required: !isEdit })}
      ${isEdit ? "" : field({ name: "password", label: "كلمة المرور", type: "password", value: "", required: true, attrs: 'minlength="8" autocomplete="new-password"' })}
      ${field({ name: "role", label: "الصلاحية", value: role, options: roles })}
      <div id="owner-slot"></div>`;

    const roleSelect = body.querySelector('[name="role"]');
    const slot = body.querySelector("#owner-slot");
    const paintOwner = () => {
      const r = roleSelect.value;
      const selected = r === "user" ? v.boy_id : v.teacher_id;
      slot.innerHTML = field({
        name: r === "user" ? "boy_id" : "teacher_id",
        label: r === "user" ? "الولد" : "الخادم",
        value: selected ? String(selected) : "",
        options: this.ownerOptions(r, selected),
        required: OWNER_ROLES.includes(r),
      });
    };
    roleSelect.addEventListener("change", paintOwner);
    paintOwner();

    Modal.open({
      title: isEdit ? "تعديل حساب" : "إضافة حساب",
      body,
      actions: [
        { label: "إلغاء" },
        {
          label: isEdit ? "حفظ التعديلات" : "إضافة",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            const form = document.getElementById("user-form");
            if (!form.reportValidity()) return;
            const data = compact(formValues(form));
            if (data.role) {
              if (OWNER_ROLES.includes(data.role)) {
                data.teacher_id = Number(data.teacher_id);
                delete data.boy_id;
              } else if (data.role === "user") {
                data.boy_id = Number(data.boy_id);
                delete data.teacher_id;
              } else {
                delete data.teacher_id;
                delete data.boy_id;
              }
            } else {
              delete data.teacher_id;
              delete data.boy_id;
            }
            button.disabled = true;
            try {
              if (isEdit) {
                await this.app.api.patch(`/auth/users/${user.id}`, data);
                Toast.success("تم تعديل الحساب.");
              } else {
                await this.app.api.post("/auth/register", data);
                Toast.success("تم إنشاء الحساب.");
              }
              close();
              await this.renderUsers();
            } catch (err) {
              Toast.error(err.message);
              button.disabled = false;
            }
          },
        },
      ],
    });
  }

  async deleteUser(user) {
    const me = this.app.auth.currentUser();
    if (me && me.id === user.id) {
      Toast.error("لا يمكنك حذف حسابك الخاص.");
      return;
    }
    const ok = await Modal.confirm({
      title: "حذف الحساب؟",
      message: `"${user.email}" سيتم حذفه نهائيًا.`,
    });
    if (!ok) return;
    try {
      await this.app.api.delete(`/auth/users/${user.id}`);
      Toast.success("تم حذف الحساب.");
      await this.renderUsers();
    } catch (err) {
      Toast.error(err.message);
    }
  }
}
