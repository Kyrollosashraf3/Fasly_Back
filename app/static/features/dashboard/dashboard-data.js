/** Data-access layer for dashboard analytics (single-request summary). */
export class DashboardService {
  constructor(api) {
    this.api = api;
  }

  summary({ classId = null, streakN = 4, absentN = 4, topN = 5, trendN = 8, teacherTrendN = 8 } = {}) {
    const query = { streak_n: streakN, absent_n: absentN, top_n: topN, trend_n: trendN, teacher_trend_n: teacherTrendN };
    if (classId !== null && classId !== undefined && classId !== "") query.class_id = classId;
    return this.api.get("/dashboard/summary", query);
  }

  boyProfile(boyId) {
    return this.api.get(`/dashboard/boys/${boyId}`);
  }
}
