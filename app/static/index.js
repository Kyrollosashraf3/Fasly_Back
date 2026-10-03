import { ApiClient } from "./shared/api.js";
import { AuthService } from "./shared/auth.js";
import { Router } from "./shared/router.js";
import { storage } from "./shared/storage.js";
import { ROLES, classLabel } from "./shared/constants.js";
import { escapeHtml } from "./shared/utils.js";

const outlet = document.getElementById("view");
const sidebar = document.getElementById("sidebar");
const topbar = document.getElementById("topbar");
const menuToggle = document.getElementById("menu-toggle");

const api = new ApiClient({
  getBaseUrl: () => storage.getApiBase(),
  getToken: () => storage.getToken(),
  onUnauthorized: () => {
    auth.logout();
    router.navigate("/login");
  },
});

const auth = new AuthService({ api, storage });
const router = new Router();

function setLayout(mode) {
  document.body.dataset.layout = mode;
  document.body.classList.remove("sidebar-open");
  menuToggle.hidden = mode === "auth";
}

async function partial(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Cannot load view: ${path}`);
  return res.text();
}

function setView(html) {
  outlet.innerHTML = html;
  window.scrollTo(0, 0);
  outlet.focus({ preventScroll: true });
}

function displayName(user) {
  if (!user) return "";
  return user.display_name || user.email || "";
}

function setTopbar(title) {
  const user = auth.currentUser();
  topbar.innerHTML = `
    <div class="topbar-title">${escapeHtml(title)}</div>
    <div class="user-chip">
      ${user ? `<span>أهلًا، <strong>${escapeHtml(displayName(user))}</strong></span>` : ""}
    </div>`;
}

function navLink(href, label, active) {
  return `<a class="nav-link${active ? " active" : ""}" href="#${href}">${escapeHtml(label)}</a>`;
}

function renderSidebar(ctx) {
  const user = auth.currentUser();
  if (!user) {
    sidebar.innerHTML = "";
    return;
  }
  const path = ctx.path;
  const role = user.role;
  const isBoy = role === ROLES.USER;
  const isTeacher = role === ROLES.TEACHER;
  const manager = auth.isManager();

  const classes = auth.accessibleClasses();
  const inClass = ctx.params.classId;
  const cls = (c) => `/class/${c}`;

  let html = `<div class="brand"><a href="#/home">فصلي</a></div><hr />`;
  html += navLink("/home", "الرئيسية", path === "/home");

  if (!isBoy) {
    html += navLink("/groups", "المجموعات", path === "/groups");
    html += navLink("/reveal", "اكشفلي", path === "/reveal");
  }
  if (manager) {
    html += navLink("/dashboard/boys", "أداء الأولاد", path === "/dashboard/boys");
    html += navLink("/dashboard/teachers", "أداء الخدام", path === "/dashboard/teachers");
  }

  if (inClass && auth.canAccess(inClass)) {
    const label = classLabel(inClass);
    html += `<hr />
      <a class="nav-link nav-back" href="#/home">&rarr; الفصول</a>
      <div class="class-title">${escapeHtml(label)}</div>
      <div class="nav-label">إدارة</div>`;
    html += navLink(cls(inClass), "نظرة عامة", path === cls(inClass));
    html += navLink(`${cls(inClass)}/boys`, "بيانات الأولاد", path === `${cls(inClass)}/boys`);
    html += navLink(`${cls(inClass)}/boys/attendance`, "الحضور", path === `${cls(inClass)}/boys/attendance`);
    if (manager) {
      html += navLink(`${cls(inClass)}/teachers`, "الخدام", path === `${cls(inClass)}/teachers`);
      html += navLink(`${cls(inClass)}/teachers/check`, "متابعة الخدام", path === `${cls(inClass)}/teachers/check`);
    }
    html += navLink(`${cls(inClass)}/follow-up`, "الافتقاد", path === `${cls(inClass)}/follow-up`);
  } else {
    html += `<div class="nav-label">الفصول</div>`;
    if (!classes.length) {
      html += `<div class="muted small" style="padding:6px 10px">لا توجد فصول مسندة لحسابك.</div>`;
    }
    for (const c of classes) {
      html += navLink(cls(c.id), classLabel(c), path.startsWith(cls(c.id)));
    }
  }

  html += `<hr /><div class="spacer"></div>`;
  html += navLink("/profile", "الحساب", path === "/profile");
  html += `<a class="nav-link" href="#/login" id="logout-link">تسجيل الخروج</a>`;
  sidebar.innerHTML = html;

  const logout = document.getElementById("logout-link");
  if (logout) {
    logout.addEventListener("click", (e) => {
      e.preventDefault();
      auth.logout();
      router.navigate("/login");
    });
  }
}

menuToggle.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});
sidebar.addEventListener("click", (e) => {
  if (e.target.closest("a")) document.body.classList.remove("sidebar-open");
});

const app = {
  outlet, api, auth, router, storage,
  partial, setView, setTopbar, renderSidebar, setLayout,
};

router.beforeEach = async (ctx) => {
  if (ctx.meta.public) {
    if (auth.isAuthenticated()) return "/home";
    setLayout("auth");
    sidebar.innerHTML = "";
    topbar.innerHTML = "";
    return null;
  }
  setLayout("app");
  if (!auth.isAuthenticated()) return "/login";
  try {
    await auth.me();
    await auth.syncClasses();
  } catch {
    auth.logout();
    return "/login";
  }
  if (ctx.params.classId && !auth.canAccess(ctx.params.classId)) return "/home";
  return null;
};

const { LoginPage } = await import("./features/auth/login.js");
const { HomePage } = await import("./features/home/home.js");
const { ClassPage } = await import("./features/classes/class.js");
const { BoysPage } = await import("./features/boys/boys.js");
const { AttendancePage } = await import("./features/boys/attendance.js");
const { TeachersPage } = await import("./features/teachers/teachers.js");
const { TeacherCheckPage } = await import("./features/teachers/teacher-check.js");
const { FollowUpPage } = await import("./features/follow-up/follow-up.js");
const { BoysPerformancePage } = await import("./features/dashboard/boys-performance.js");
const { TeachersPerformancePage } = await import("./features/dashboard/teachers-performance.js");
const { RevealPage } = await import("./features/reveal/reveal.js");
const { GroupsPage } = await import("./features/groups/groups.js");
const { ProfilePage } = await import("./features/profile/profile.js");

function mount(Page, title) {
  return async (ctx) => {
    renderSidebar(ctx);
    setTopbar(typeof title === "function" ? title(ctx) : title);
    await new Page(app).mount(ctx);
  };
}

const classTitle = (ctx) => classLabel(ctx.params.classId);

router
  .add("/login", mount(LoginPage, "تسجيل الدخول"), { public: true })
  .add("/home", mount(HomePage, "الرئيسية"))
  .add("/dashboard", mount(BoysPerformancePage, "أداء الأولاد"))
  .add("/dashboard/boys", mount(BoysPerformancePage, "أداء الأولاد"))
  .add("/dashboard/teachers", mount(TeachersPerformancePage, "أداء الخدام"))
  .add("/reveal", mount(RevealPage, "اكشفلي"))
  .add("/groups", mount(GroupsPage, "المجموعات"))
  .add("/class/:classId", mount(ClassPage, classTitle))
  .add("/class/:classId/boys", mount(BoysPage, (c) => `${classLabel(c.params.classId)} / بيانات الأولاد`))
  .add("/class/:classId/boys/attendance", mount(AttendancePage, (c) => `${classLabel(c.params.classId)} / الحضور`))
  .add("/class/:classId/teachers", mount(TeachersPage, (c) => `${classLabel(c.params.classId)} / الخدام`))
  .add("/class/:classId/teachers/check", mount(TeacherCheckPage, (c) => `${classLabel(c.params.classId)} / متابعة الخدام`))
  .add("/class/:classId/follow-up", mount(FollowUpPage, (c) => `${classLabel(c.params.classId)} / الافتقاد`))
  .add("/profile", mount(ProfilePage, "الحساب"));

router.start();
