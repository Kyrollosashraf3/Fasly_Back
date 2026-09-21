/** Data-access layer for servant follow-up groups. */
export class GroupsService {
  constructor(api) {
    this.api = api;
  }

  list(className = null, teacherId = null) {
    const query = {};
    if (className) query.class_name = className;
    if (teacherId) query.teacher_id = teacherId;
    return this.api.get("/groups", query);
  }

  assign(teacherId, boyIds) {
    return this.api.post("/groups/assign", { teacher_id: teacherId, boy_ids: boyIds });
  }

  unassign(boyIds) {
    return this.api.post("/groups/unassign", { boy_ids: boyIds });
  }

  importGroups(file) {
    return this.api.upload("/groups/import", file);
  }

  async exportFile(className = null) {
    const query = className ? { class_name: className } : {};
    const url = this.api.buildUrl("/groups/export", query);
    const headers = {};
    const token = this.api.getToken ? this.api.getToken() : null;
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error("تعذر تنزيل الملف.");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `groups_${className || "all"}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
}
