/* Code shared by every page of the ManageEAT UI: calling the two services, the login session, the
 * sidebar, safe HTML, number formats and the notices for a service that is down or starting up.
 *
 * The UI is static files. Each page loads config.js (the services' addresses), this file and its own
 * script, then asks the services for JSON and draws it. Nothing here knows any business rule: every
 * figure comes already calculated from the services.
 */
"use strict";

const SERVICES = {
  personnel: (window.MANAGEEAT_CONFIG || {}).PERSONNEL_URL,
  sales: (window.MANAGEEAT_CONFIG || {}).SALES_URL,
};
const SERVICE_NAMES = { personnel: "personnel", sales: "sales" };

// A cold start on Azure: the container takes about 30 s to start and the database up to a minute to
// resume, so a request may wait that long before it is answered.
const REQUEST_TIMEOUT_MS = 60000;
const RETRY_WAIT_MS = 5000;
const SESSION_KEY = "manageeat.session";
const REFRESH_EVERY_MS = 10 * 60 * 1000;      // the token lasts 15 minutes (ADR-6)


// ---------- Safe HTML ----------
// Every value written into a page goes through escapeHtml, so a dish called <script> is shown as text.
// html`...` escapes what it interpolates; raw() marks a string that is already safe HTML.

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

class SafeHtml {
  constructor(text) { this.text = text; }
  toString() { return this.text; }
}

function raw(text) {
  return new SafeHtml(text);
}

function piece(value) {
  if (value instanceof SafeHtml) return value.text;
  if (Array.isArray(value)) return value.map(piece).join("");
  if (value === null || value === undefined || value === false) return "";
  return escapeHtml(value);
}

function html(strings, ...values) {
  return raw(strings.reduce((out, text, i) => out + text + (i < values.length ? piece(values[i]) : ""), ""));
}


// ---------- Formats ----------

function eur(value) {
  if (value === null || value === undefined) return "–";
  return "€" + Number(value).toLocaleString("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(value, digits = 1) {
  return value === null || value === undefined ? "–" : Number(value).toFixed(digits) + "%";
}

function num(value, digits = 0) {
  if (value === null || value === undefined) return "–";
  return Number(value).toLocaleString("en", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function capitalize(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

function whenText(isoTime) {
  const moment = new Date(isoTime);
  return isNaN(moment) ? isoTime : moment.toLocaleString("en", { dateStyle: "medium", timeStyle: "short" });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function queryParam(name) {
  return new URLSearchParams(location.search).get(name);
}


// ---------- Login session ----------
// The token is kept in sessionStorage: it survives reloading the page but not closing the tab. Storage
// can be unavailable (private mode, blocked cookies), so every access is wrapped.

const session = {
  get() {
    try {
      return JSON.parse(sessionStorage.getItem(SESSION_KEY));
    } catch (error) {
      return null;
    }
  },
  save(answer) {
    const saved = {
      token: answer.token,
      expiresAt: Date.now() + answer.expires_in * 1000,
      user: answer.user,
      restaurant: answer.restaurant,
    };
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(saved));
    } catch (error) {
      // Without storage the session lasts until the next page is opened
    }
    return saved;
  },
  clear() {
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch (error) {
      // nothing to remove
    }
  },
};

// Thrown to stop a page's script while the browser goes to the login page; it is not a real error
class RedirectingToLogin extends Error {}
window.addEventListener("error", (event) => {
  if (event.error instanceof RedirectingToLogin) event.preventDefault();
});

function goToLogin() {
  const here = location.pathname.split("/").pop() || "index.html";
  location.href = "login.html?next=" + encodeURIComponent(here + location.search);
}


// ---------- Calling the services ----------

class ApiError extends Error {
  constructor(message, status, service) {
    super(message);
    this.status = status;
    this.service = service;
  }
}

// The service did not answer at all, or Azure answered for it (502/503/504): it is down or still starting
class ServiceUnavailable extends ApiError {}

// The token was refused, so the page is already going to the login page: nothing else to show
class SessionExpired extends ApiError {}

function errorMessage(data, status) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI's field errors: [{loc: ["body", "price"], msg: "Input should be greater than 0"}, ...]
    return detail.map((e) => {
      const field = (e.loc || []).filter((part) => typeof part === "string" && part !== "body").pop();
      const message = String(e.msg || "").replace(/^Value error, /, "");
      return field ? `${capitalize(field.replace(/_/g, " "))}: ${message}` : message;
    }).join("\n");
  }
  return `The request failed (${status})`;
}

/* Calls one of the services and returns its JSON.
 * A GET that finds the service down or starting is tried up to 3 times, 5 s apart, so a cold start is
 * usually invisible; a POST, PUT or DELETE is tried once, so nothing is ever saved twice. */
async function api(service, path, { method = "GET", body, attempts } = {}) {
  const base = SERVICES[service];
  if (!base) throw new ApiError(`The address of the ${service} service is missing from config.js`, 0, service);
  const current = session.get();
  const headers = {};
  if (current) headers.Authorization = `Bearer ${current.token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const tries = attempts || (method === "GET" ? 3 : 1);

  for (let attempt = 1; ; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    let response = null;
    try {
      response = await fetch(base + path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (error) {
      response = null;           // refused, offline, timed out, or blocked by CORS
    } finally {
      clearTimeout(timer);
    }

    if (response === null || [502, 503, 504].includes(response.status)) {
      if (attempt < tries) {
        await sleep(RETRY_WAIT_MS);
        continue;
      }
      throw new ServiceUnavailable(
        `The ${SERVICE_NAMES[service]} service is not answering. It sleeps when nobody uses it and can take ` +
        "up to a minute to start: try again in a few seconds.", response ? response.status : 0, service);
    }
    if (response.status === 401 && current && !path.startsWith("/auth/")) {
      session.clear();
      goToLogin();
      throw new SessionExpired("Your session has expired. Please log in again.", 401, service);
    }
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(errorMessage(data, response.status), response.status, service);
    return data;
  }
}

async function refreshSession() {
  if (!session.get()) return;
  try {
    session.save(await api("personnel", "/auth/refresh", { method: "POST" }));
  } catch (error) {
    if (error.status === 401) {          // the manager was removed: personnel will not renew the token
      session.clear();
      goToLogin();
    }
    // If personnel is down the current token keeps working until it expires (ADR-6)
  }
}


// ---------- Notices ----------

function notice(kind, message) {
  return html`<div class="notice ${kind}">${String(message).split("\n").map((line) => html`<div>${line}</div>`)}</div>`;
}

/* What a figure that comes from the other service is based on: {"source": "live" | "snapshot" | "unavailable"}. */
function sourceNotice(source, texts) {
  if (!source || source.source === "live") return "";
  if (source.source === "snapshot") {
    return notice("warning", texts.snapshot.replace("{when}", whenText(source.as_of)));
  }
  return notice("error", texts.unavailable);
}

const WAGES_NOTICES = {
  snapshot: "The personnel service is not answering, so wages are the last figures it sent ({when}). " +
            "They may be out of date.",
  unavailable: "The personnel service is not answering and has never sent these figures, so wages, " +
               "labour cost and net profit are not shown. Everything else is up to date.",
};

const DEMAND_NOTICES = {
  snapshot: "The sales service is not answering, so the schedule uses the last diners it sent ({when}). " +
            "They may be out of date.",
  unavailable: "The sales service is not answering and has never sent the diners per hour, so the " +
               "recommended staff cannot be calculated. Payroll and staff still work.",
};


// ---------- Sections that load data ----------

/* Fills `element` with what `load()` returns: {html, after}. While it loads it says so; if a service is
 * down it explains why and offers to try again, and the rest of the page keeps working. */
async function mount(element, load) {
  element.innerHTML = '<p class="muted loading">Loading…</p>';
  try {
    const result = await load();
    element.innerHTML = piece(result.html);
    if (result.after) result.after(element);
  } catch (error) {
    if (error instanceof SessionExpired) return;
    const kind = error instanceof ServiceUnavailable ? "warning" : "error";
    element.innerHTML = piece(html`${notice(kind, error.message)}<button type="button" class="retry">Try again</button>`);
    element.querySelector(".retry").addEventListener("click", () => mount(element, load));
  }
}

/* Sends a form as JSON. `build(form)` turns the fields into the request body; `done(answer)` runs on
 * success. Errors from the service are shown above the form and nothing is cleared. */
function handleForm(form, { send, build, done }) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    const box = form.querySelector(".form-message") || form.insertAdjacentElement("afterbegin", document.createElement("div"));
    box.className = "form-message";
    box.innerHTML = "";
    button.disabled = true;
    try {
      const answer = await send(build(form));
      done(answer);
    } catch (error) {
      if (!(error instanceof SessionExpired)) {
        box.innerHTML = piece(notice(error instanceof ServiceUnavailable ? "warning" : "error", error.message));
      }
    } finally {
      button.disabled = false;
    }
  });
}

/* A message that stays after reloading the page (e.g. "Dish added"), shown once by the next page load. */
function flash(message) {
  try {
    sessionStorage.setItem("manageeat.flash", message);
  } catch (error) {
    // the page still works without the message
  }
}

function takeFlash() {
  try {
    const message = sessionStorage.getItem("manageeat.flash");
    sessionStorage.removeItem("manageeat.flash");
    return message;
  } catch (error) {
    return null;
  }
}

function numberOrNull(value) {
  return value === "" || value === null ? null : Number(value);
}

function textOrNull(value) {
  const text = (value || "").trim();
  return text === "" ? null : text;
}


// ---------- Page layout ----------

const ICONS = {
  overview: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  recipes: '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/><path d="M9 7h7M9 11h5"/>',
  menu: '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
  inventory: '<path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  profit: '<path d="M3 3v18h18"/><path d="M7 16v-4M12 16V8M17 16v-7"/>',
  staff: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
  schedule: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  payroll: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
  warning: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
  money: '<path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
  trend: '<path d="M22 7 13.5 15.5 8.5 10.5 2 17"/><path d="M16 7h6v6"/>',
  pie: '<path d="M21.2 15.9A10 10 0 1 1 8 2.8"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  person: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
  cart: '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2 2h3l2.7 12.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6"/>',
  out: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>',
  truck: '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.7a1 1 0 0 0-.2-.6l-3.5-4.4A1 1 0 0 0 17.5 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
  star: '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
};

function icon(name) {
  return raw(`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`);
}

const NAVIGATION = [
  { href: "index.html", label: "Overview", icon: "overview" },
  { group: "Sales" },
  { href: "dishes.html", label: "Menu & recipes", icon: "recipes", also: ["dish.html"] },
  { href: "menu.html", label: "Menu performance", icon: "menu" },
  { href: "inventory.html", label: "Inventory", icon: "inventory", also: ["supplier.html", "ingredient.html"] },
  { href: "profit-loss.html", label: "Profit & loss", icon: "profit" },
  { group: "Personnel" },
  { href: "staff.html", label: "Staff", icon: "staff" },
  { href: "schedule.html", label: "Schedule", icon: "schedule" },
  { href: "payroll.html", label: "Payroll", icon: "payroll" },
];

/* Draws the sidebar and the page header, and returns the element the page fills.
 * Without a session it sends the visitor to the login page first. */
function startPage({ title, intro }) {
  const current = session.get();
  if (!current) {
    goToLogin();
    throw new RedirectingToLogin("Not logged in");
  }
  const here = location.pathname.split("/").pop() || "index.html";
  document.title = `${title} · ManageEAT`;

  const links = NAVIGATION.map((item) => {
    if (item.group) return html`<p class="nav-group">${item.group}</p>`;
    const active = item.href === here || (item.also || []).includes(here);
    return html`<a href="${item.href}" class="${active ? "active" : ""}">${icon(item.icon)}${item.label}</a>`;
  });

  document.body.innerHTML = piece(html`
    <aside class="sidebar">
      <a class="brand" href="index.html">Manage<span>EAT</span></a>
      <p class="brand-sub">Restaurant management</p>
      <nav>${links}</nav>
      <div class="account">
        <p class="account-restaurant">${current.restaurant.name}</p>
        <p class="account-user">${current.user.name}</p>
        <a href="managers.html" class="${here === "managers.html" ? "active" : ""}">Managers</a>
        <button type="button" id="log-out">Log out</button>
      </div>
    </aside>
    <main class="content">
      <header class="page-header">
        <h1 id="page-title">${title}</h1>
        <p class="page-intro" id="page-intro">${intro || ""}</p>
      </header>
      <div id="page-flash"></div>
      <div id="page"></div>
    </main>`);

  document.getElementById("log-out").addEventListener("click", () => {
    session.clear();                     // the token is forgotten; it expires by itself (ADR-6)
    location.href = "login.html";
  });
  const message = takeFlash();
  if (message) document.getElementById("page-flash").innerHTML = piece(notice("success", message));

  if (current.expiresAt - Date.now() < 5 * 60 * 1000) refreshSession();
  setInterval(refreshSession, REFRESH_EVERY_MS);
  return document.getElementById("page");
}

function setHeading(title, intro) {
  document.getElementById("page-title").textContent = title;
  document.title = `${title} · ManageEAT`;
  if (intro !== undefined) document.getElementById("page-intro").innerHTML = piece(intro);
}

/* The key figures row at the top of most pages. */
function kpis(items) {
  return html`<section class="kpis">${items.map((item, i) => html`
    <div class="kpi ${i === 0 ? "highlight" : ""}">
      <div class="label">${icon(item.icon)}${item.label}</div>
      <div class="value" ${item.small ? raw('style="font-size:19px"') : ""}>${item.value}</div>
      <div class="note">${item.note || ""}</div>
    </div>`)}</section>`;
}

/* Tabs that show one panel at a time; `onShow(key)` runs the first time a panel is shown (charts need it). */
function setUpTabs(root, onShow) {
  const shown = new Set();
  const show = (key) => {
    root.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.key === key));
    root.querySelectorAll("[data-panel]").forEach((p) => p.classList.toggle("active", p.dataset.panel === key));
    if (onShow && !shown.has(key)) {
      shown.add(key);
      onShow(key);
    }
  };
  root.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => show(t.dataset.key)));
  const first = root.querySelector(".tab");
  if (first) show(first.dataset.key);
}