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
          <h3 style="margin-bottom:12px">Profile</h3>
          <div class="details">
            <div class="detail-row"><span>Name</span><span>${escapeHtml(user.user_name)}</span></div>
            <div class="detail-row"><span>Email</span><span>${escapeHtml(user.mail)}</span></div>
            <div class="detail-row"><span>Phone</span><span>${escapeHtml(user.phone || "—")}</span></div>
            <div class="detail-row"><span>Role</span><span>${badge(user.role === ROLES.ADMIN ? "Admin" : "Class Secretary", user.role === ROLES.ADMIN ? "yellow" : "")}</span></div>
            <div class="detail-row"><span>Class</span><span>${escapeHtml(user.class_name ? classLabel(user.class_name) : user.role === ROLES.ADMIN ? "All classes" : "—")}</span></div>
          </div>
        </div>
        <div class="card">
          <h3 style="margin-bottom:12px">Change password</h3>
          <form id="pw-form">
            <div class="field">
              <label for="pw-new">New password (min 6 characters)</label>
              <input class="input" id="pw-new" name="password" type="password" minlength="6" required autocomplete="new-password" />
            </div>
            <button class="btn btn-secondary" type="submit" id="pw-submit">Update password</button>
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
        Toast.success("Password updated.");
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
    section.innerHTML = `<h2 class="section-title">Users</h2>
      <div class="toolbar"><div class="toolbar-group"></div>
      <div class="toolbar-group"><button class="btn btn-primary" id="add-user">+ Add User</button></div></div>
      <div id="users-content">${skeletonTable(4)}</div>`;
    document.getElementById("add-user").addEventListener("click", () => this.openUserForm());
    const box = document.getElementById("users-content");
    try {
      const users = await this.app.api.get("/auth/users");
      const list = Array.isArray(users) ? users : [];
      if (!list.length) {
        box.innerHTML = emptyState("No users", "No accounts found.");
        return;
      }
      box.innerHTML = table(
        ["Name", "Email", "Role", "Class", "Actions"],
        list.map((u) => `
          <tr>
            <td><strong>${escapeHtml(u.user_name)}</strong></td>
            <td>${escapeHtml(u.mail)}</td>
            <td>${badge(u.role === ROLES.ADMIN ? "Admin" : "Secretary", u.role === ROLES.ADMIN ? "yellow" : "")}</td>
            <td>${escapeHtml(u.class_name ? classLabel(u.class_name) : "—")}</td>
            <td class="cell-actions">
              <button class="btn-link" data-uact="edit" data-id="${u.id}">Edit</button>
              <button class="btn-link danger" data-uact="del" data-id="${u.id}" data-mail="${escapeHtml(u.mail)}">Delete</button>
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
      ${field({ name: "user_name", label: "Name", value: v.user_name || "", required: !isEdit })}
      ${field({ name: "mail", label: "Email", type: "email", value: v.mail || "", required: !isEdit })}
      ${isEdit ? "" : field({ name: "password", label: "Password", type: "password", value: "", required: true, attrs: 'minlength="6" autocomplete="new-password"' })}
      ${field({ name: "phone", label: "Phone", type: "tel", value: v.phone || "" })}
      ${field({ name: "role", label: "Role", value: v.role || "user", options: [
        { value: "user", label: "Class Secretary" }, { value: "admin", label: "Admin" }] })}
      ${field({ name: "class_name", label: "Class", value: v.class_name || "", options: [
        { value: "", label: "None (admin)" },
        ...CLASSES.map((c) => ({ value: c, label: classLabel(c) }))] })}`;
    Modal.open({
      title: isEdit ? "Edit user" : "Add user",
      body,
      actions: [
        { label: "Cancel" },
        {
          label: isEdit ? "Save changes" : "Add user",
          kind: "btn-primary",
          onClick: async ({ close, button }) => {
            const form = document.getElementById("user-form");
            if (!form.reportValidity()) return;
            button.disabled = true;
            try {
              if (isEdit) {
                const data = compact(formValues(form));
                await this.app.api.patch(`/auth/users/${user.id}`, data);
                Toast.success("User updated.");
              } else {
                const data = compact(formValues(form));
                if (!data.class_name) delete data.class_name;
                await this.app.api.post("/auth/register", data);
                Toast.success("User created.");
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
      Toast.error("You cannot delete your own account.");
      return;
    }
    const ok = await Modal.confirm({
      title: "Delete user?",
      message: `"${user.mail}" will be permanently removed.`,
    });
    if (!ok) return;
    try {
      await this.app.api.delete(`/auth/users/${user.id}`);
      Toast.success("User deleted.");
      await this.renderUsers();
    } catch (err) {
      Toast.error(err.message);
    }
  }
}
