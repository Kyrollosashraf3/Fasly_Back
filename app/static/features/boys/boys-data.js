/** Data-access layer for the boys master data. UI code must go through here. */
export class BoyService {
  constructor(api) {
    this.api = api;
  }

  list(className, issueFlag = null) {
    return this.api.get("/boys", { class_name: className, issue_flag: issueFlag });
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
}
