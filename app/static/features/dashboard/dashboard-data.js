/** Data-access layer for dashboard analytics (single-request summary). */
export class DashboardService {
  constructor(api) {
    this.api = api;
  }

  summary({ className = null, streakN = 4, absentN = 4, topN = 5 } = {}) {
    const query = { streak_n: streakN, absent_n: absentN, top_n: topN };
    if (className) query.class_name = className;
    return this.api.get("/dashboard/summary", query);
  }

  boyProfile(boyId) {
    return this.api.get(`/dashboard/boys/${boyId}`);
  }
}
