/** Data-access layer for the boys master data. UI code must go through here. */
export class BoyService {
  constructor(api) {
    this.api = api;
  }

  list(classId, issueFlag = null) {
    const query = {};
    if (classId !== null && classId !== undefined && classId !== "") {
      query.class_id = classId;
    }
    if (issueFlag !== null && issueFlag !== undefined) query.issue_flag = issueFlag;
    return this.api.get("/boys", query);
  }

  get(boyId) {
    return this.api.get(`/boys/${boyId}`);
  }

  create(data) {
    return this.api.post("/boys", data);
  }

  update(boyId, data) {
    return this.api.patch(`/boys/${boyId}`, data);
  }

  remove(boyId) {
    return this.api.delete(`/boys/${boyId}`);
  }

  importExcel(file) {
    return this.api.upload("/boys/import", file);
  }

  /** Ready-to-upload sample sheet with class_name already filled. */
  downloadTemplate() {
    return this.api.download("/boys/template", null, "boys.xlsx");
  }

  downloadExport(classId = null) {
    const query = classId ? { class_id: classId } : null;
    return this.api.download("/boys/export", query, "boys.xlsx");
  }
}
