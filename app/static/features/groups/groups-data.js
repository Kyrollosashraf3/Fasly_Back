/** Data-access layer for servant follow-up groups. */
export class GroupsService {
  constructor(api) {
    this.api = api;
  }

  list(classId = null, teacherId = null) {
    const query = {};
    if (classId !== null && classId !== undefined && classId !== "") query.class_id = classId;
    if (teacherId) query.teacher_id = teacherId;
    return this.api.get("/groups", query);
  }

  assign(teacherId, boyIds) {
    return this.api.post("/groups/assign", { teacher_id: Number(teacherId), boy_ids: boyIds.map(Number) });
  }

  unassign(boyIds) {
    return this.api.post("/groups/unassign", { boy_ids: boyIds.map(Number) });
  }

  importGroups(file) {
    return this.api.upload("/groups/import", file);
  }

  exportFile(classId = null) {
    const query = classId ? { class_id: classId } : null;
    return this.api.download("/groups/export", query, "follow_up_groups.xlsx");
  }
}
