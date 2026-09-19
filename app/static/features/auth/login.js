import { Toast } from "../../shared/components.js";

export class LoginPage {
  constructor(app) {
    this.app = app;
  }

  async mount() {
    const html = await this.app.partial("features/auth/login.html");
    this.app.setView(html);

    const form = document.getElementById("login-form");
    const errorBox = document.getElementById("login-error");
    const submit = document.getElementById("login-submit");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const mail = form.mail.value.trim();
      const password = form.password.value;
      if (!mail || !password) {
        errorBox.innerHTML = `<div class="form-error">Please enter your email and password.</div>`;
        return;
      }
      errorBox.innerHTML = "";
      submit.disabled = true;
      submit.textContent = "Logging in...";
      try {
        await this.app.auth.login(mail, password);
        Toast.success("Welcome back.");
        this.app.router.navigate("/home");
      } catch (err) {
        const message =
          err.status === 401
            ? "Incorrect email or password."
            : err.message || "Login failed. Please try again.";
        errorBox.innerHTML = `<div class="form-error">${message}</div>`;
      } finally {
        submit.disabled = false;
        submit.textContent = "Login";
      }
    });
  }
}
