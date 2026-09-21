import { CLASSES, ROLES, classLabel } from "../../shared/constants.js";
import {
  Modal, Toast, badge, compact, emptyState, errorBlock,
  field, formValues, loadingBlock, skeletonTable, table,
} from "../../shared/components.js";
import { escapeHtml } from "../../shared/utils.js";

export class ProfilePage {
  constructor(app) {
    this.app = app;
  }

  async mount() {
    const html = await this.app.partial("features/profile/profile.html");
    this.app.setView(html);
    const user = this.app.auth.currentUser();
    const box = document.getElementById("profile-content");

    box.innerHTML = `
      <div class="card-grid profile-grid">
        <div class="card">
          <h3 style="margin-bottom:12px">الملف الشخصي</h3>
          <div class="details">
            <div class="detail-row"><span>الاسم</span><span>${escapeHtml(user.user_name)}</span></div>
            <div class="detail-row"><span>البريد الإلكتروني</span><span>${escapeHtml(user.mail)}</span></div>
            <div class="detail-row"><span>التليفون</span><span>${escapeHtml(user.phone || "—")}</span></div>
            <div class="detail-row"><span>الدور</span><span>${badge(user.role === ROLES.ADMIN ? "أدمن" : "أمين فصل", user.role === ROLES.ADMIN ? "yellow" : "")}</span></div>
            <div class="detail-row"><span>الفصل</span><span>${escapeHtml(user.class_name ? classLabel(user.class_name) : user.role === ROLES.ADMIN ? "كل الفصول" : "—")}</span></div>
          </div>
        </div>
        <div class="card">
          <h3 style="margin-bottom:12px">تغيير كلمة المرور</h3>
          <form id="pw-form">
            <div class="field">
              <label for="pw-new">كلمة المرور الجديدة (6 حروف على الأقل)</label>
              <input class="input" id="pw-new" name="password" type="password" minlength="6" required autocomplete="new-password" />
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

    if (this.app.auth.isAdmin()) {
      await this.renderUsers();
    }
  }

  async renderUsers() {
    const section = document.getElementById("users-section");
    section.innerHTML = `<h2 class="section-title">المستخدمون</h2>
      <div class="toolbar"><div class="toolbar-group"></div>
      <div class="toolbar-group"><button class="btn btn-primary" id="add-user">+ إضافة مستخدم</button></div></div>
      <div id="users-content">${skeletonTable(4)}</div>`;
    document.getElementById("add-user").addEventListener("click", () => this.openUserForm());
    const box = document.getElementById("users-content");
    try {
      const users = await this.app.api.get("/auth/users");
      const list = Array.isArray(users) ? users : [];
      if (!list.length) {
        box.innerHTML = emptyState("لا يوجد مستخدمون", "لا توجد حسابات مسجلة.");
        return;
      }
      box.innerHTML = table(
        ["الاسم", "البريد الإلكتروني", "الدور", "الفصل", "إجراءات"],
        list.map((u) => `
          <tr>
            <td><strong>${escapeHtml(u.user_name)}</strong></td>
            <td>${escapeHtml(u.mail)}</td>
            <td>${badge(u.role === ROLES.ADMIN ? "أدمن" : "أمين فصل", u.role === ROLES.ADMIN ? "yellow" : "")}</td>
            <td>${escapeHtml(u.class_name ? classLabel(u.class_name) : "—")}</td>
            <td class="cell-actions">
              <button class="btn-link" data-uact="edit" data-id="${u.id}">تعديل</button>
              <button class="btn-link danger" data-uact="del" data-id="${u.id}" data-mail="${escapeHtml(u.mail)}">حذف</button>
            </td>
          </tr>`).join("")
      );
      box.querySelectorAll("button[data-uact]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const u = list.find((x) => x.id === btn.dataset.id);
          if (!u) return;
          if (btn.dataset.uact === "edit") this.openUserForm(u);
          if (btn.dataset.uact === "del") this.deleteUser(u);
        });
      });
    } catch (err) {
      box.innerHTML = errorBlock(err.message);
    }
  }

  openUserForm(user = null) {
    const isEdit = Boolean(user);
    const v = user || {};
    const body = document.createElement("form");
    body.id = "user-form";
    body.innerHTML = `
      ${field({ name: "user_name", label: "الاسم", value: v.user_name || "", required: !isEdit })}
      ${field({ name: "mail", label: "البريد الإلكتروني", type: "email", value: v.mail || "", required: !isEdit })}
      ${isEdit ? "" : field({ name: "password", label: "كلمة المرور", type: "password", value: "", required: true, attrs: 'minlength="6" autocomplete="new-password"' })}
      ${field({ name: "phone", label: "التليفون", type: "tel", value: v.phone || "" })}
      ${field({ name: "role", label: "الدور", value: v.role || "user", options: [
        { value: "user", label: "أمين فصل" }, { value: "admin", label: "أدمن" }] })}
      ${field({ name: "class_name", label: "الفصل", value: v.class_name || "", options: [
        { value: "", label: "بدون (أدمن)" },
        ...CLASSES.map((c) => ({ value: c, label: classLabel(c) }))] })}`;
    Modal.open({
      title: isEdit ? "تعديل مستخدم" : "إضافة مستخدم",
      body,
      actions: [
        { label: "إلغاء" },
        {
          label: isEdit ? "حفظ التعديلات" : "إضافة",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            const form = document.getElementById("user-form");
            if (!form.reportValidity()) return;
            button.disabled = true;
            try {
              if (isEdit) {
                const data = compact(formValues(form));
                await this.app.api.patch(`/auth/users/${user.id}`, data);
                Toast.success("تم تعديل المستخدم.");
              } else {
                const data = compact(formValues(form));
                if (!data.class_name) delete data.class_name;
                await this.app.api.post("/auth/register", data);
                Toast.success("تم إنشاء المستخدم.");
              }
              await this.app.auth.me(true);
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
      title: "حذف المستخدم؟",
      message: `"${user.mail}" سيتم حذفه نهائيًا.`,
    });
    if (!ok) return;
    try {
      await this.app.api.delete(`/auth/users/${user.id}`);
      Toast.success("تم حذف المستخدم.");
      await this.renderUsers();
    } catch (err) {
      Toast.error(err.message);
    }
  }
}
