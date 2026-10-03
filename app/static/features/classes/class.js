import { classLabel } from "../../shared/constants.js";
import { errorBlock, loadingBlock } from "../../shared/components.js";
import { escapeHtml } from "../../shared/utils.js";

export class ClassPage {
  constructor(app) {
    this.app = app;
  }

  async mount(ctx) {
    const classId = ctx.params.classId;
    const label = classLabel(classId);
    const html = await this.app.partial("features/classes/class.html");
    this.app.setView(html);
    document.getElementById("class-title").textContent = label;

    const box = document.getElementById("class-content");
    box.innerHTML = loadingBlock("جارٍ تحميل بيانات الفصل...");

    try {
      const [boys, teachers] = await Promise.all([
        this.app.api.get("/boys", { class_id: classId }),
        this.app.auth.isBoy()
          ? Promise.resolve([])
          : this.app.api.get("/teachers", { class_id: classId }),
      ]);
      const boyCount = Array.isArray(boys) ? boys.length : 0;
      const teacherCount = Array.isArray(teachers) ? teachers.length : 0;
      const base = `/class/${encodeURIComponent(classId)}`;
      box.innerHTML = `
        <div class="card-grid overview-grid">
          <a class="card stat-card" href="#${base}/boys">
            <div class="stat-num">${boyCount}</div>
            <div class="stat-label">الأولاد</div>
          </a>
          <a class="card stat-card" href="#${base}/teachers">
            <div class="stat-num">${teacherCount}</div>
            <div class="stat-label">الخدام</div>
          </a>
        </div>
        <div class="overview-links">
          <a class="btn btn-secondary" href="#${base}/boys/attendance">تسجيل الحضور</a>
          <a class="btn btn-secondary" href="#${base}/follow-up">الافتقاد الأسبوعي</a>
          <a class="btn btn-secondary" href="#${base}/teachers/check">متابعة الخدام</a>
        </div>`;
    } catch (err) {
      box.innerHTML = errorBlock(
        err.message,
        `<button class="btn btn-secondary" id="retry">حاول مجددًا</button>`
      );
      document.getElementById("retry")?.addEventListener("click", () => this.mount(ctx));
    }
  }
}
