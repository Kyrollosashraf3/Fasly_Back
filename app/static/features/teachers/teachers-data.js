/** Data-access layer for teachers (servants). */
export class TeacherService {
  constructor(api) {
    this.api = api;
  }

  list(className) {
    return this.api.get("/teachers", { class_name: className });
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
}
