import { classLabel } from "../../shared/constants.js";
import { errorBlock, loadingBlock } from "../../shared/components.js";
import { escapeHtml } from "../../shared/utils.js";

export class ClassPage {
  constructor(app) {
    this.app = app;
  }

  async mount(ctx) {
    const { className } = ctx.params;
    const html = await this.app.partial("features/classes/class.html");
    this.app.setView(html);
    document.getElementById("class-title").textContent = classLabel(className);

    const box = document.getElementById("class-content");
    box.innerHTML = loadingBlock("جارٍ تحميل بيانات الفصل...");

    try {
      const [boys, teachers] = await Promise.all([
        this.app.api.get("/boys", { class_name: className }),
        this.app.api.get("/teachers", { class_name: className }),
      ]);
      const boyCount = Array.isArray(boys) ? boys.length : 0;
      const teacherCount = Array.isArray(teachers) ? teachers.length : 0;
      box.innerHTML = `
        <div class="card-grid overview-grid">
          <a class="card stat-card" href="#/class/${escapeHtml(className)}/boys">
            <div class="stat-num">${boyCount}</div>
            <div class="stat-label">الأولاد</div>
          </a>
          <a class="card stat-card" href="#/class/${escapeHtml(className)}/teachers">
            <div class="stat-num">${teacherCount}</div>
            <div class="stat-label">الخدام</div>
          </a>
        </div>
        <div class="overview-links">
          <a class="btn btn-secondary" href="#/class/${escapeHtml(className)}/boys/attendance">تسجيل الحضور</a>
          <a class="btn btn-secondary" href="#/class/${escapeHtml(className)}/follow-up">الافتقاد الأسبوعي</a>
          <a class="btn btn-secondary" href="#/class/${escapeHtml(className)}/teachers/check">متابعة الخدام</a>
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
