import { classLabel } from "../../shared/constants.js";
import { emptyState, errorBlock, loadingBlock } from "../../shared/components.js";
import { escapeHtml } from "../../shared/utils.js";

export class HomePage {
  constructor(app) {
    this.app = app;
  }

  async mount() {
    const html = await this.app.partial("features/home/home.html");
    this.app.setView(html);
    const box = document.getElementById("home-content");
    const classes = this.app.auth.accessibleClasses();

    if (!classes.length) {
      box.innerHTML = emptyState(
        "No classes assigned",
        "Your account has no class assigned yet. Please contact an administrator."
      );
      return;
    }

    box.innerHTML = loadingBlock("Loading classes...");
    const counts = {};
    await Promise.all(
      classes.map(async (c) => {
        try {
          const boys = await this.app.api.get("/boys", { class_name: c });
          counts[c] = Array.isArray(boys) ? boys.length : 0;
        } catch {
          counts[c] = null;
        }
      })
    );

    box.innerHTML = `
      <div class="card-grid class-grid">
        ${classes
          .map(
            (c) => `
          <a class="card class-card" href="#/class/${c}">
            <div class="class-card-name">${escapeHtml(classLabel(c))}</div>
            <div class="class-card-count">${
              counts[c] === null ? "—" : `${counts[c]} boy${counts[c] === 1 ? "" : "s"}`
            }</div>
          </a>`
          )
          .join("")}
      </div>`;
  }
}
