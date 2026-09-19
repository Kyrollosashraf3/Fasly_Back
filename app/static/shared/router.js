function splitHash() {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const [pathPart, queryPart] = raw.split("?");
  return { pathPart: pathPart || "/", queryPart: queryPart || "" };
}

function matchPattern(pattern, path) {
  const pSegs = pattern.split("/").filter(Boolean);
  const sSegs = path.split("/").filter(Boolean);
  if (pSegs.length !== sSegs.length) return null;
  const params = {};
  for (let i = 0; i < pSegs.length; i += 1) {
    if (pSegs[i].startsWith(":")) {
      params[pSegs[i].slice(1)] = decodeURIComponent(sSegs[i]);
    } else if (pSegs[i] !== sSegs[i]) {
      return null;
    }
  }
  return params;
}

export class Router {
  constructor() {
    this.routes = [];
    this.beforeEach = null;
    this.current = null;
    this._onHash = () => this.resolve();
  }

  add(pattern, handler, meta = {}) {
    this.routes.push({ pattern, handler, meta });
    return this;
  }

  start() {
    window.addEventListener("hashchange", this._onHash);
    if (!window.location.hash) {
      window.location.hash = "#/home";
      return;
    }
    this.resolve();
  }

  navigate(to) {
    if (window.location.hash === `#${to}`) {
      this.resolve();
    } else {
      window.location.hash = `#${to}`;
    }
  }

  parseQuery(queryPart) {
    const query = {};
    if (!queryPart) return query;
    for (const pair of queryPart.split("&")) {
      const [k, v = ""] = pair.split("=");
      if (k) query[decodeURIComponent(k)] = decodeURIComponent(v);
    }
    return query;
  }

  async resolve() {
    const { pathPart, queryPart } = splitHash();
    for (const route of this.routes) {
      const params = matchPattern(route.pattern, pathPart);
      if (!params) continue;
      const ctx = {
        params,
        query: this.parseQuery(queryPart),
        path: pathPart,
        meta: route.meta,
      };
      if (this.beforeEach) {
        const redirect = await this.beforeEach(ctx);
        if (redirect) {
          this.navigate(redirect);
          return;
        }
      }
      this.current = ctx;
      try {
        await route.handler(ctx);
      } catch (err) {
        console.error(err);
      }
      return;
    }
    this.navigate("/home");
  }
}
