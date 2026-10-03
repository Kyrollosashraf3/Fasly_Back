/** Data-access layer for teachers (servants). */
export class TeacherService {
  constructor(api) {
    this.api = api;
  }

  list(classId) {
    const query = {};
    if (classId !== null && classId !== undefined && classId !== "") query.class_id = classId;
    return this.api.get("/teachers", query);
  }

  get(teacherId) {
    return this.api.get(`/teachers/${teacherId}`);
  }

  create(data) {
    return this.api.post("/teachers", data);
  }

  update(teacherId, data) {
    return this.api.patch(`/teachers/${teacherId}`, data);
  }

  remove(teacherId) {
    return this.api.delete(`/teachers/${teacherId}`);
  }

  importExcel(file) {
    return this.api.upload("/teachers/import", file);
  }

  downloadTemplate() {
    return this.api.download("/teachers/template", null, "teachers.xlsx");
  }

  downloadExport(classId = null) {
    const query = classId ? { class_id: classId } : null;
    return this.api.download("/teachers/export", query, "teachers.xlsx");
  }
}
