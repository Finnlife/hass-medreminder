import { createTranslator, resolveLanguage } from "./localize.js";
import { PANEL_STYLES } from "./styles.js";

const DAY_KEYS = [
  "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
];
const PACKAGE_NICKNAMES = [
  "Apollo", "Bumblebee", "Comet", "Daisy", "Echo", "Foxy", "Kiwi", "Mochi",
  "Nova", "Pebble", "Pixel", "Rocket", "Sunny", "Tango", "Yoshi", "Ziggy",
];
const OPEN_STATUSES = ["pending", "partial"];
const CLOSED_STATUSES = ["taken", "skipped", "missed"];
const POLL_INTERVAL = 20000;
const EXPIRY_WARNING_DAYS = 30;

const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

const localDateValue = (date) =>
  new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const localDateTimeValue = (date) =>
  new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

class MedicationReminderPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.state = null;
    this.activeTab = "overview";
    this.modal = null;
    this.renderedModalKey = null;
    this.loading = false;
    this.lastLoad = null;
    this.toast = null;
    this.language = "en";
    this.locale = "en-US";
    this.t = createTranslator("en");
    this.historyStatus = "all";
    this.historySearch = "";
    this.highlightId = null;
    const today = new Date();
    const monthAgo = new Date(today);
    monthAgo.setDate(monthAgo.getDate() - 29);
    this.historyFrom = localDateValue(monthAgo);
    this.historyTo = localDateValue(today);
    this.buildSkeleton();
    this.shadowRoot.addEventListener("click", (event) => this.onClick(event));
    this.shadowRoot.addEventListener("submit", (event) => this.onSubmit(event));
    this.shadowRoot.addEventListener("change", (event) => this.onChange(event));
    this.shadowRoot.addEventListener("input", (event) => this.onInput(event));
    this.shadowRoot.addEventListener("keydown", (event) => this.onKeydown(event));
  }

  // ---------------------------------------------------------------- lifecycle

  set hass(value) {
    this._hass = value;
    const language = resolveLanguage(value);
    if (language !== this.language) {
      this.language = language;
      this.locale = language === "de" ? "de-DE" : "en-US";
      this.t = createTranslator(language);
      this.renderAll();
    }
    if (!this.state && !this.loading) this.load();
  }

  get hass() { return this._hass; }
  set panel(value) { this._panel = value; }
  set narrow(value) { this._narrow = value; }

  connectedCallback() {
    this.renderAll();
    this.poller = window.setInterval(() => this.load(false), POLL_INTERVAL);
  }

  disconnectedCallback() {
    window.clearInterval(this.poller);
    window.clearTimeout(this.toastTimer);
  }

  buildSkeleton() {
    this.shadowRoot.innerHTML = `<style>${PANEL_STYLES}</style>
      <div class="app">
        <header id="app-header"></header>
        <nav id="app-nav"></nav>
        <main id="app-main"></main>
        <footer id="app-footer"></footer>
      </div>
      <div id="app-overlay"></div>
      <div id="app-toast"></div>`;
    this.$header = this.shadowRoot.getElementById("app-header");
    this.$nav = this.shadowRoot.getElementById("app-nav");
    this.$main = this.shadowRoot.getElementById("app-main");
    this.$footer = this.shadowRoot.getElementById("app-footer");
    this.$overlay = this.shadowRoot.getElementById("app-overlay");
    this.$toast = this.shadowRoot.getElementById("app-toast");
  }

  async call(type, payload = {}) {
    if (!this.hass) throw new Error("Home Assistant is not connected yet.");
    return this.hass.connection.sendMessagePromise({
      type: `medication_reminder/${type}`, ...payload,
    });
  }

  async load(showSpinner = true) {
    if (this.loading || !this.hass) return;
    this.loading = true;
    if (showSpinner && !this.state) this.renderMain();
    try {
      const next = await this.call("get_state");
      this.state = next;
      this.lastLoad = Date.now();
      this.applyDeepLink();
      this.renderAll();
    } catch (error) {
      this.showToast(this.errorText(error), true);
    } finally {
      this.loading = false;
    }
  }

  /** Resolve ?occurrence=<id> and ?scan=<code> deep links into a tab and highlight. */
  applyDeepLink() {
    const params = new URLSearchParams(window.location.search);
    const occurrenceId = params.get("occurrence");
    if (occurrenceId && this.state.occurrences.some((item) => item.id === occurrenceId)) {
      this.activeTab = "overview";
      this.highlightId = occurrenceId;
      return;
    }
    const scan = params.get("scan");
    if (!scan) return;
    const code = scan.includes(":") ? scan.split(":").pop() : scan;
    const match = this.resolveScanCode(code);
    if (!match) return;
    this.activeTab = match.kind === "occurrence" ? "overview" : "medications";
    this.highlightId = match.item.id;
  }

  resolveScanCode(code) {
    const groups = [
      ["medication", this.state.medications],
      ["package", this.state.packages || []],
      ["occurrence", this.state.occurrences],
    ];
    for (const [kind, items] of groups) {
      const item = items.find((entry) => entry.scan_code === code);
      if (item) return { kind, item };
    }
    return null;
  }

  // ------------------------------------------------------------------ helpers

  medication(id) { return this.state?.medications.find((item) => item.id === id); }
  package(id) { return this.state?.packages?.find((item) => item.id === id); }
  regimen(id) { return this.state?.regimens.find((item) => item.id === id); }

  packagesFor(medicationId) {
    return (this.state?.packages || [])
      .filter((item) => item.medication_id === medicationId)
      .sort((a, b) => (a.expires_on || "9999-12-31").localeCompare(b.expires_on || "9999-12-31"));
  }

  openOccurrences() {
    return this.state.occurrences
      .filter((item) => OPEN_STATUSES.includes(item.status))
      .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
  }

  isDue(item) {
    if (new Date(item.scheduled_at) > new Date()) return false;
    return !item.snoozed_until || new Date(item.snoozed_until) <= new Date();
  }

  days(short = false) {
    return DAY_KEYS.map((day) => this.t(short ? `day.short.${day}` : `day.${day}`));
  }

  status(status) { return this.t(`status.${status}`); }

  formatNumber(value) {
    return new Intl.NumberFormat(this.locale, { maximumFractionDigits: 3 }).format(value ?? 0);
  }

  formatDate(value) {
    return value ? new Intl.DateTimeFormat(this.locale).format(new Date(`${value}T00:00:00`)) : "–";
  }

  formatDateTime(value) {
    if (!value) return "–";
    return new Intl.DateTimeFormat(this.locale, {
      weekday: "short", day: "2-digit", month: "2-digit",
      hour: "2-digit", minute: "2-digit",
    }).format(new Date(value));
  }

  formatTime(value) {
    if (!value) return "–";
    return new Intl.DateTimeFormat(this.locale, {
      hour: "2-digit", minute: "2-digit",
    }).format(new Date(value));
  }

  relative(value) {
    if (!value) return this.t("common.none");
    const diff = new Date(value).getTime() - Date.now();
    const past = diff < 0;
    const minutes = Math.round(Math.abs(diff) / 60000);
    if (minutes < 1) return this.t("relative.now");
    if (minutes < 60) return this.t(past ? "relative.before_minutes" : "relative.in_minutes", { minutes });
    const hours = Math.round(minutes / 60);
    if (hours < 24) return this.t(past ? "relative.before_hours" : "relative.in_hours", { hours });
    const days = Math.round(hours / 24);
    return this.t(past ? "relative.before_days" : "relative.in_days", { days });
  }

  packagePlanText(plan, unit) {
    return (plan || []).map((part) => {
      const details = [
        part.lot_number ? this.t("package.lot", { lot: part.lot_number }) : "",
        part.expires_on ? this.t("package.expires", { date: this.formatDate(part.expires_on) }) : "",
      ].filter(Boolean).join(", ");
      return `${part.nickname} (${this.formatNumber(part.amount)} ${unit}${details ? ` · ${details}` : ""})`;
    }).join(" + ");
  }

  errorText(error) {
    const message = error?.body?.message || error?.message;
    if (!message) return this.t("error.generic");
    const known = {
      "Medication Reminder is not configured": "error.not_configured",
      "Medication is still used by an intake": "error.medication_in_use",
      "Medication is still used by an open intake": "error.medication_in_open_intake",
      "Taken dose exceeds the remaining planned dose": "error.dose_exceeds",
      "No dose was selected": "error.no_dose",
      "Snooze time must be in the future": "error.future_snooze",
      "Only open intakes can be snoozed": "error.only_open_snooze",
      "Name is required": "error.name_required",
      "Unknown medication": "error.unknown_medication",
      "Medication occurs more than once": "error.medication_duplicate",
      "At least one medication is required": "error.medication_required",
      "At least one weekday is required": "error.select_weekday",
      "repeat_minutes must be between 5 and 1440": "error.repeat_range",
      "reminder_window_minutes must be between 0 and 10080": "error.window_range",
      "auto_miss_after_minutes must be between 0 and 43200": "error.auto_miss_range",
      "auto_miss_after_minutes must not be below repeat_minutes": "error.auto_miss_below_repeat",
      "every_days must be between 1 and 365": "error.every_days_range",
      "Unsupported schedule type": "error.schedule_type",
      "Invalid snooze time": "error.invalid_snooze",
      "Time must use HH:MM": "error.invalid_time_generic",
      "Invalid time": "error.invalid_time_generic",
      "Package quantity must be greater than zero": "error.package_quantity",
      "Package nickname must be unique per medication": "error.package_nickname",
      "Intake time must not be in the future": "error.unplanned_future",
      "Only untouched open intakes can shift their cycle": "error.interval_only",
      "Only interval schedules can shift their cycle": "error.interval_only",
      "Only due intakes can shift to tomorrow": "error.interval_only",
      "Invalid delete confirmation": "error.delete_confirmation",
      "Start date must not be after end date": "error.export_range",
    };
    if (known[message]) return this.t(known[message]);
    if (message.startsWith("Not enough stock for ")) {
      return this.t("error.not_enough_stock", { medication: message.slice(21) });
    }
    if (/ is too long$/.test(message)) return this.t("error.text_too_long");
    if (/ must (not be negative|be greater than zero|be a number)$/.test(message)) {
      return this.t("error.invalid_value");
    }
    return message;
  }

  showToast(message, error = false) {
    this.toast = { message, error };
    this.renderToast();
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => {
      this.toast = null;
      this.renderToast();
    }, 4500);
  }

  /** True while the user is typing inside the main area, which must not be replaced. */
  mainHasFocus() {
    const active = this.shadowRoot.activeElement;
    return Boolean(active && this.$main.contains(active)
      && active.matches("input, textarea, select"));
  }

  // ----------------------------------------------------------------- rendering

  renderAll() {
    this.renderHeader();
    this.renderNav();
    this.renderMain();
    this.renderFooter();
    this.renderOverlay();
  }

  renderHeader() {
    this.$header.innerHTML = `
      <div class="brand">
        <img src="/medication_reminder_frontend/logo.png" alt="">
        <div><h1>${this.t("app.title")}</h1><p>${this.t("app.subtitle")}</p></div>
      </div>
      <div class="header-actions">
        <button class="ghost" data-action="new-unplanned">
          <ha-icon icon="mdi:pill-plus"></ha-icon><span>${this.t("app.record_unplanned")}</span>
        </button>
        <button class="primary" data-action="new-regimen">
          <ha-icon icon="mdi:plus"></ha-icon><span>${this.t("regimens.create")}</span>
        </button>
        <button class="icon" data-action="refresh" title="${this.t("app.refresh")}">
          <ha-icon icon="mdi:refresh"></ha-icon>
        </button>
        <button class="icon" data-action="data-management" title="${this.t("app.data_management")}">
          <ha-icon icon="mdi:database-cog-outline"></ha-icon>
        </button>
        <button class="icon danger" data-action="delete-all-data" title="${this.t("app.delete_all_data")}">
          <ha-icon icon="mdi:delete-sweep-outline"></ha-icon>
        </button>
      </div>`;
  }

  renderNav() {
    const open = this.state ? this.openOccurrences().length : 0;
    const tabs = [
      ["overview", "mdi:view-dashboard-outline", this.t("nav.overview"), open],
      ["medications", "mdi:pill-multiple", this.t("nav.medications"), 0],
      ["regimens", "mdi:calendar-clock", this.t("nav.regimens"), 0],
      ["history", "mdi:history", this.t("nav.history"), 0],
    ];
    this.$nav.innerHTML = tabs.map(([id, icon, label, count]) =>
      `<button data-tab="${id}" class="${this.activeTab === id ? "active" : ""}">
        <ha-icon icon="${icon}"></ha-icon><span>${label}</span>
        ${count ? `<i class="count">${count}</i>` : ""}
      </button>`).join("");
  }

  renderMain() {
    if (!this.state) {
      this.$main.innerHTML = `<div class="loading">
        <div class="loader"></div>
        <h2>${this.t("app.loading_title")}</h2><p>${this.t("app.loading_text")}</p>
      </div>`;
      return;
    }
    if (this.mainHasFocus()) return;
    if (this.activeTab === "medications") this.$main.innerHTML = this.renderMedications();
    else if (this.activeTab === "regimens") this.$main.innerHTML = this.renderRegimens();
    else if (this.activeTab === "history") this.$main.innerHTML = this.renderHistory();
    else this.$main.innerHTML = this.renderOverview();
    if (this.highlightId) {
      const target = this.$main.querySelector(`[data-highlight="${this.highlightId}"]`);
      target?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  renderFooter() {
    this.$footer.innerHTML = `<span><i class="live"></i>${this.t("app.local_storage")}</span>
      <span>${this.lastLoad ? this.t("app.last_synced", { time: this.formatTime(this.lastLoad) }) : ""}</span>`;
  }

  renderToast() {
    this.$toast.innerHTML = this.toast
      ? `<div class="toast ${this.toast.error ? "error" : ""}">
          <ha-icon icon="${this.toast.error ? "mdi:alert-circle-outline" : "mdi:check-circle-outline"}"></ha-icon>
          <span>${esc(this.toast.message)}</span>
        </div>`
      : "";
  }

  /** The overlay is only rebuilt when the dialog identity changes, never on refresh. */
  renderOverlay(force = false) {
    const key = this.modal
      ? `${this.modal.type}:${this.modal.item?.id || this.modal.medicationId || ""}:${this.modal.stepTwo ? 1 : 0}`
      : null;
    if (!force && key === this.renderedModalKey) return;
    this.renderedModalKey = key;
    if (!this.modal || !this.state) {
      this.$overlay.innerHTML = "";
      return;
    }
    const views = {
      medication: () => this.medicationModal(this.modal.item || {}),
      package: () => this.packageModal(this.modal.item || {}),
      regimen: () => this.regimenModal(this.modal.item || {}),
      unplanned: () => this.unplannedModal(),
      code: () => this.codeModal(this.modal.item),
      data: () => this.dataModal(),
    };
    this.$overlay.innerHTML = (views[this.modal.type] || (() => ""))();
    this.$overlay.querySelector("input, select, textarea, button")?.focus({ preventScroll: true });
  }

  openModal(modal) {
    this.modal = modal;
    this.renderOverlay(true);
  }

  closeModal() {
    this.modal = null;
    this.renderOverlay(true);
  }

  // ------------------------------------------------------------------ overview

  renderOverview() {
    const open = this.openOccurrences();
    const due = open.filter((item) => this.isDue(item));
    const later = open.filter((item) => !this.isDue(item));
    const adherence = this.state.adherence || {};
    const warnings = this.warnings();
    return `
      ${this.metrics(open, due, adherence)}
      <section class="block">
        <div class="block-head"><h2>${this.t("overview.due_now")}</h2>
          ${due.length > 1 ? `<span class="muted">${due.length}</span>` : ""}</div>
        ${due.length
          ? `<div class="stack">${due.map((item) => this.ticket(item)).join("")}</div>`
          : this.empty("mdi:check-circle-outline", this.t("overview.no_due_title"), this.t("overview.no_due_text"))}
      </section>
      ${later.length ? `<section class="block">
        <div class="block-head"><h2>${this.t("overview.due_later")}</h2></div>
        <div class="stack">${later.map((item) => this.ticket(item)).join("")}</div>
      </section>` : ""}
      ${warnings.length ? `<section class="block">
        <div class="block-head"><h2>${this.t("overview.warnings")}</h2></div>
        <div class="card list">${warnings.map((warning) =>
          `<div class="row warning-row ${warning.level}">
            <ha-icon icon="${warning.icon}"></ha-icon><span>${esc(warning.text)}</span>
          </div>`).join("")}</div>
      </section>` : ""}
      <section class="block">
        <div class="block-head"><h2>${this.t("overview.upcoming")}</h2></div>
        ${(this.state.upcoming || []).length
          ? `<div class="card list">${this.state.upcoming.slice(0, 6).map((entry) =>
              `<div class="row">
                <div class="row-main">
                  <strong>${esc(entry.regimen_name)}</strong>
                  <small>${esc((entry.items || []).map((item) =>
                    `${this.formatNumber(item.dose)} × ${item.medication_name}`).join(", "))}</small>
                </div>
                <div class="row-side">
                  <span>${this.formatDateTime(entry.scheduled_at)}</span>
                  <small>${this.relative(entry.scheduled_at)}</small>
                </div>
              </div>`).join("")}</div>`
          : `<div class="card"><p class="muted pad">${this.t("overview.no_upcoming")}</p></div>`}
      </section>`;
  }

  metrics(open, due, adherence) {
    const low = this.state.medications.filter((item) => item.stock <= item.low_stock_threshold);
    const cells = [
      [this.t("overview.metric_open"), open.length, ""],
      [this.t("overview.metric_due"), due.length, due.length ? "attention" : ""],
      [this.t("overview.metric_low"), low.length, low.length ? "attention" : ""],
      [
        this.t("overview.metric_adherence", { days: adherence.window_days ?? 30 }),
        adherence.rate === null || adherence.rate === undefined ? "–" : `${this.formatNumber(adherence.rate)} %`,
        "",
      ],
    ];
    return `<section class="metrics card">${cells.map(([label, value, tone]) =>
      `<div class="metric ${tone}"><span>${label}</span><strong>${esc(value)}</strong></div>`).join("")}</section>`;
  }

  warnings() {
    const result = [];
    const today = localDateValue(new Date());
    const limit = localDateValue(new Date(Date.now() + EXPIRY_WARNING_DAYS * 86400000));
    for (const medication of this.state.medications) {
      if (medication.stock <= medication.low_stock_threshold) {
        result.push({
          level: "warn", icon: "mdi:package-variant-remove",
          text: this.t("overview.low_stock_warning", {
            name: medication.name, stock: this.formatNumber(medication.stock),
            unit: medication.unit, threshold: this.formatNumber(medication.low_stock_threshold),
          }),
        });
      }
      for (const pack of this.packagesFor(medication.id)) {
        if (!pack.expires_on || pack.remaining_quantity <= 0 || pack.expires_on > limit) continue;
        const expired = pack.expires_on < today;
        result.push({
          level: expired ? "error" : "warn",
          icon: expired ? "mdi:alert-octagon-outline" : "mdi:clock-alert-outline",
          text: this.t(expired ? "overview.expired_warning" : "overview.expiry_warning", {
            name: medication.name, package: pack.nickname,
            date: this.formatDate(pack.expires_on),
          }),
        });
      }
    }
    return result;
  }

  ticket(item) {
    const regimen = this.regimen(item.regimen_id);
    const title = item.unplanned
      ? this.t("ticket.unplanned")
      : regimen?.name || item.regimen_name || this.t("ticket.orphan_plan");
    const snoozed = item.snoozed_until && new Date(item.snoozed_until) > new Date();
    const overdue = this.isDue(item) && Date.now() - new Date(item.scheduled_at) > 3600000;
    return `<article class="card ticket ${this.highlightId === item.id ? "highlight" : ""}"
        data-occurrence="${item.id}" data-highlight="${item.id}">
      <div class="ticket-head">
        <div>
          <div class="badges">
            <span class="badge ${item.status}">${this.status(item.status)}</span>
            ${item.ad_hoc ? `<span class="badge partial">${this.t("ticket.ad_hoc")}</span>` : ""}
            ${overdue ? `<span class="badge missed">${this.t("ticket.overdue")}</span>` : ""}
            ${snoozed ? `<span class="badge snoozed">${this.t("ticket.snoozed_until", { time: this.formatTime(item.snoozed_until) })}</span>` : ""}
          </div>
          <h3>${esc(title)}</h3>
          <p class="muted">${this.t("ticket.due", { time: this.formatDateTime(item.scheduled_at) })} · ${this.relative(item.scheduled_at)}</p>
        </div>
        <div class="ticket-time">${this.formatTime(item.scheduled_at)}</div>
      </div>
      ${item.reason ? `<p class="hint"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon>${this.t("ticket.reason", { reason: esc(item.reason) })}</p>` : ""}
      ${regimen?.instructions ? `<p class="hint"><ha-icon icon="mdi:information-outline"></ha-icon>${esc(regimen.instructions)}</p>` : ""}
      <div class="doses">${item.items.map((dose) => this.doseLine(dose)).join("")}</div>
      <div class="ticket-actions">
        <button class="primary" data-action="take-selected" data-id="${item.id}">
          <ha-icon icon="mdi:check"></ha-icon>${this.t("ticket.take_selection")}
        </button>
        <div class="chips">
          <span class="chip-label">${this.t("ticket.snooze")}</span>
          <button class="chip" data-action="snooze" data-id="${item.id}" data-minutes="30">${this.t("ticket.snooze_30")}</button>
          <button class="chip" data-action="snooze" data-id="${item.id}" data-minutes="60">${this.t("ticket.snooze_60")}</button>
          <button class="chip" data-action="snooze" data-id="${item.id}" data-minutes="120">${this.t("ticket.snooze_120")}</button>
          <input class="chip-input" type="datetime-local" data-snooze-time="${item.id}">
          <button class="chip" data-action="snooze-custom" data-id="${item.id}" title="${this.t("ticket.custom_snooze")}">
            <ha-icon icon="mdi:clock-edit-outline"></ha-icon>
          </button>
        </div>
        <div class="spacer"></div>
        ${regimen?.schedule?.type === "interval" && item.status === "pending"
          ? `<button class="ghost" data-action="postpone-interval" data-id="${item.id}">
              <ha-icon icon="mdi:calendar-arrow-right"></ha-icon>${this.t("ticket.postpone_tomorrow")}</button>`
          : ""}
        <button class="icon" data-action="show-code" data-kind="intake" data-id="${item.id}"
          data-label="${esc(title)}" title="${this.t("ticket.qr")}"><ha-icon icon="mdi:qrcode"></ha-icon></button>
        <button class="text danger" data-action="skip" data-id="${item.id}">${this.t("ticket.skip")}</button>
      </div>
    </article>`;
  }

  doseLine(dose) {
    const med = this.medication(dose.medication_id);
    const remaining = Math.round((dose.planned_dose - dose.taken_dose) * 1000) / 1000;
    const detail = [med?.strength, med?.form].filter(Boolean).join(" · ");
    return `<label class="dose ${remaining <= 0 ? "done" : ""}">
      <input type="checkbox" data-medication="${dose.medication_id}" ${remaining > 0 ? "checked" : "disabled"}>
      <span class="dose-main">
        <strong>${esc(med?.name || this.t("ticket.deleted_medication"))}</strong>
        ${detail ? `<small>${esc(detail)}</small>` : ""}
        ${dose.package_plan?.length
          ? `<small class="plan">${this.t("ticket.take_from", { packages: esc(this.packagePlanText(dose.package_plan, med?.unit || "")) })}</small>`
          : ""}
        ${dose.taken_dose ? `<small>${this.t("ticket.already_taken", { amount: this.formatNumber(dose.taken_dose) })}</small>` : ""}
      </span>
      <span class="dose-amount">
        <input type="number" data-dose="${dose.medication_id}" min="0" max="${remaining}"
          step="0.001" value="${remaining}" ${remaining > 0 ? "" : "disabled"}>
        <small>${esc(med?.unit || "")}</small>
      </span>
    </label>`;
  }

  // --------------------------------------------------------------- medications

  renderMedications() {
    return `<div class="page-head">
        <div><h2>${this.t("medications.title")}</h2><p class="muted">${this.t("medications.subtitle")}</p></div>
        <button class="primary" data-action="new-medication"><ha-icon icon="mdi:plus"></ha-icon>${this.t("medications.create")}</button>
      </div>
      <section class="grid">${this.state.medications.length
        ? this.state.medications.map((item) => this.medicationCard(item)).join("")
        : this.empty("mdi:pill-off", this.t("medications.empty_title"), this.t("medications.empty_text"))}</section>`;
  }

  medicationCard(item) {
    const low = item.stock <= item.low_stock_threshold;
    const packages = this.packagesFor(item.id);
    const capacity = packages.reduce((sum, pack) => sum + Number(pack.initial_quantity || 0), 0);
    const percentage = capacity > 0 ? Math.min(100, (item.stock / capacity) * 100) : 0;
    const supply = item.days_of_supply === null || item.days_of_supply === undefined
      ? this.t("stock.supply_unknown")
      : this.t("stock.supply", { days: this.formatNumber(item.days_of_supply) });
    const detail = [item.manufacturer, item.strength, item.form].filter(Boolean).map(esc).join(" · ");
    return `<article class="card medication ${low ? "is-low" : ""} ${this.highlightId === item.id ? "highlight" : ""}"
        data-highlight="${item.id}">
      <div class="med-head">
        <div>
          <h3>${esc(item.name)}</h3>
          <p class="muted">${detail || this.t("stock.no_details")}</p>
        </div>
        <span class="badge ${item.stock <= 0 ? "missed" : low ? "pending" : "taken"}">
          ${this.t(item.stock <= 0 ? "stock.empty" : low ? "stock.reorder" : "stock.available")}
        </span>
      </div>
      <div class="stock-value"><strong>${this.formatNumber(item.stock)}</strong><span>${esc(item.unit)}</span>
        <small class="muted">${supply}</small></div>
      <div class="bar"><i style="width:${percentage}%"></i></div>
      <small class="muted">${this.t("stock.warning_at", { amount: this.formatNumber(item.low_stock_threshold), unit: esc(item.unit) })}</small>
      <div class="packages">
        <div class="packages-head"><b>${this.t("stock.packages")}</b><span class="muted">${packages.filter((p) => p.remaining_quantity > 0).length}</span></div>
        ${packages.length
          ? packages.map((pack) => this.packageRow(pack, item)).join("")
          : `<small class="muted">${this.t("stock.no_packages")}</small>`}
      </div>
      <div class="card-actions">
        <button class="ghost" data-action="new-package" data-id="${item.id}">
          <ha-icon icon="mdi:package-variant-plus"></ha-icon>${this.t("stock.add_package")}</button>
        <button class="icon" data-action="show-code" data-kind="medication" data-id="${item.id}"
          data-label="${esc(item.name)}" title="${this.t("package.code")}"><ha-icon icon="mdi:qrcode"></ha-icon></button>
        <div class="spacer"></div>
        <button class="text" data-action="edit-medication" data-id="${item.id}">${this.t("common.edit")}</button>
        <button class="text danger" data-action="delete-medication" data-id="${item.id}">${this.t("common.delete")}</button>
      </div>
    </article>`;
  }

  packageRow(pack, medication) {
    const today = localDateValue(new Date());
    const expired = pack.expires_on && pack.expires_on < today;
    const meta = [
      pack.lot_number ? this.t("package.lot", { lot: esc(pack.lot_number) }) : "",
      pack.expires_on
        ? this.t(expired ? "package.expired" : "package.expires", { date: this.formatDate(pack.expires_on) })
        : this.t("package.no_expiry"),
    ].filter(Boolean).join(" · ");
    return `<div class="package ${pack.remaining_quantity <= 0 ? "empty" : ""} ${expired ? "expired" : ""} ${this.highlightId === pack.id ? "highlight" : ""}"
        data-highlight="${pack.id}">
      <ha-icon icon="mdi:package-variant-closed"></ha-icon>
      <div class="package-main">
        <strong>${esc(pack.nickname)}</strong>
        <small>${this.t("package.remaining", {
          amount: this.formatNumber(pack.remaining_quantity),
          initial: this.formatNumber(pack.initial_quantity),
          unit: esc(medication.unit),
        })}</small>
        <small class="muted">${meta}</small>
      </div>
      <div class="package-actions">
        <button class="icon small" data-action="show-code" data-kind="package" data-id="${pack.id}"
          data-label="${esc(pack.nickname)}" title="${this.t("package.code")}"><ha-icon icon="mdi:qrcode"></ha-icon></button>
        <button class="icon small" data-action="edit-package" data-id="${pack.id}"
          title="${this.t("package.edit")}"><ha-icon icon="mdi:pencil-outline"></ha-icon></button>
        <button class="icon small danger" data-action="delete-package" data-id="${pack.id}"
          title="${this.t("package.delete")}"><ha-icon icon="mdi:delete-outline"></ha-icon></button>
      </div>
    </div>`;
  }

  // ------------------------------------------------------------------- regimens

  renderRegimens() {
    return `<div class="page-head">
        <div><h2>${this.t("regimens.title")}</h2><p class="muted">${this.t("regimens.subtitle")}</p></div>
        <button class="primary" data-action="new-regimen"><ha-icon icon="mdi:plus"></ha-icon>${this.t("regimens.create")}</button>
      </div>
      <section class="stack">${this.state.regimens.length
        ? this.state.regimens.map((item) => this.regimenCard(item)).join("")
        : this.empty("mdi:calendar-blank-outline", this.t("regimens.empty_title"), this.t("regimens.empty_text"))}</section>`;
  }

  regimenCard(item) {
    const next = (this.state.upcoming || []).find((entry) => entry.regimen_id === item.id);
    const reminders = item.notify_services.length || item.scripts.length
      ? this.t("regimens.reminder_summary", {
          targets: item.notify_services.length + item.scripts.length,
          minutes: item.repeat_minutes,
        })
      : this.t("regimens.reminder_none");
    const limits = [
      item.reminder_window_minutes ? this.t("regimens.window", { minutes: item.reminder_window_minutes }) : "",
      item.auto_miss_after_minutes ? this.t("regimens.auto_miss", { minutes: item.auto_miss_after_minutes }) : "",
    ].filter(Boolean).join(" · ");
    return `<article class="card regimen ${item.active ? "" : "inactive"}">
      <div class="regimen-main">
        <div class="badges">
          <span class="badge ${item.active ? "taken" : "skipped"}">${this.t(item.active ? "common.active" : "common.paused")}</span>
        </div>
        <h3>${esc(item.name)}</h3>
        <p class="muted schedule"><ha-icon icon="mdi:clock-outline"></ha-icon>${esc(this.scheduleText(item.schedule))}</p>
        <div class="chips">${item.items.map((dose) => {
          const med = this.medication(dose.medication_id);
          return `<span class="chip static">${this.formatNumber(dose.dose)} ${esc(med?.unit || "")} ${esc(med?.name || this.t("ticket.deleted_medication"))}</span>`;
        }).join("")}</div>
        <small class="muted">${reminders}${limits ? ` · ${limits}` : ""}</small>
        <small class="muted">${next ? this.t("regimens.next", { time: this.formatDateTime(next.scheduled_at) }) : this.t("regimens.no_next")}</small>
      </div>
      <div class="regimen-actions">
        <button class="icon" data-action="edit-regimen" data-id="${item.id}" title="${this.t("common.edit")}">
          <ha-icon icon="mdi:pencil-outline"></ha-icon></button>
        <button class="icon danger" data-action="delete-regimen" data-id="${item.id}" title="${this.t("common.delete")}">
          <ha-icon icon="mdi:delete-outline"></ha-icon></button>
      </div>
    </article>`;
  }

  scheduleText(schedule) {
    if (schedule.type === "interval") {
      return this.t(schedule.every_days === 1 ? "schedule.every_day" : "schedule.every_days", {
        days: schedule.every_days, date: this.formatDate(schedule.start_date), time: schedule.time,
      });
    }
    const short = this.days(true);
    const groups = new Map();
    Object.entries(schedule.days).forEach(([day, times]) => {
      const key = times.join(", ");
      groups.set(key, [...(groups.get(key) || []), short[Number(day)]]);
    });
    return [...groups.entries()]
      .map(([times, days]) => this.t("schedule.weekly_group", { days: days.join(", "), times }))
      .join("  |  ");
  }

  // -------------------------------------------------------------------- history

  renderHistory() {
    const adherence = this.state.adherence || {};
    const search = this.historySearch.trim().toLowerCase();
    const rows = this.state.occurrences
      .filter((item) => CLOSED_STATUSES.includes(item.status))
      .filter((item) => this.historyStatus === "all" || item.status === this.historyStatus)
      .filter((item) => !search || this.historyMatches(item, search))
      .sort((a, b) => (b.taken_at || b.scheduled_at).localeCompare(a.taken_at || a.scheduled_at));
    const statuses = ["all", ...CLOSED_STATUSES];
    return `<div class="page-head">
        <div><h2>${this.t("history.title")}</h2><p class="muted">${this.t("history.subtitle")}</p></div>
      </div>
      <section class="card pad adherence">
        <strong>${adherence.rate === null || adherence.rate === undefined
          ? this.t("history.adherence_none")
          : this.t("history.adherence", {
              days: adherence.window_days, rate: this.formatNumber(adherence.rate), total: adherence.total,
            })}</strong>
        <small class="muted">${this.t("history.counts", {
          taken: adherence.taken ?? 0, partial: adherence.partial ?? 0,
          skipped: adherence.skipped ?? 0, missed: adherence.missed ?? 0,
        })}</small>
      </section>
      <section class="card pad export">
        <div class="export-fields">
          <label class="field"><span>${this.t("history.export_from")}</span>
            <input type="date" name="history_from" value="${esc(this.historyFrom)}"></label>
          <label class="field"><span>${this.t("history.export_to")}</span>
            <input type="date" name="history_to" value="${esc(this.historyTo)}"></label>
          <div class="field"><span>${this.t("history.export_title")}</span>
            <div class="export-actions">
              <button class="ghost" data-action="export-history" data-format="json">
                <ha-icon icon="mdi:code-json"></ha-icon>${this.t("history.export_json")}</button>
              <button class="ghost" data-action="export-history" data-format="csv">
                <ha-icon icon="mdi:file-delimited-outline"></ha-icon>${this.t("history.export_csv")}</button>
            </div>
          </div>
        </div>
        <small class="muted">${this.t("history.export_help")}</small>
      </section>
      <section class="filters">
        <div class="chips">${statuses.map((value) =>
          `<button class="chip ${this.historyStatus === value ? "on" : ""}" data-action="history-status" data-value="${value}">
            ${value === "all" ? this.t("common.all") : this.status(value)}</button>`).join("")}</div>
        <input class="search" type="search" name="history_search" value="${esc(this.historySearch)}"
          placeholder="${this.t("history.filter_search")}">
      </section>
      ${rows.length ? `<div class="card table-wrap"><table>
        <thead><tr>
          <th>${this.t("history.status")}</th><th>${this.t("history.intake")}</th>
          <th>${this.t("history.scheduled")}</th><th>${this.t("history.actual")}</th>
          <th>${this.t("history.deviation")}</th><th>${this.t("history.doses")}</th>
        </tr></thead>
        <tbody>${rows.map((item) => this.historyRow(item)).join("")}</tbody>
      </table></div>` : this.empty("mdi:history", this.t("history.empty_title"), this.t("history.empty_text"))}`;
  }

  historyMatches(item, search) {
    const names = item.items.map((dose) => this.medication(dose.medication_id)?.name || "").join(" ");
    return `${item.regimen_name || ""} ${names}`.toLowerCase().includes(search);
  }

  historyRow(item) {
    const actual = item.taken_at ? new Date(item.taken_at) : null;
    const planned = new Date(item.scheduled_at);
    const deviation = actual && item.status === "taken"
      ? Math.round((actual - planned) / 60000) : null;
    const name = item.unplanned ? this.t("unplanned.history_name")
      : this.regimen(item.regimen_id)?.name || item.regimen_name || this.t("history.deleted_schedule");
    const doses = item.items.map((dose) => {
      const medication = this.medication(dose.medication_id);
      const allocations = dose.allocations?.length
        ? `<small class="muted">${this.t("history.packages", {
            packages: esc(this.packagePlanText(dose.allocations, medication?.unit || "")),
          })}</small>` : "";
      return `<div>${this.formatNumber(dose.taken_dose)}/${this.formatNumber(dose.planned_dose)} ${esc(medication?.name || "")}${allocations}</div>`;
    }).join("");
    return `<tr>
      <td><span class="badge ${item.status}">${this.status(item.status)}</span></td>
      <td><strong>${esc(name)}</strong>${item.note || item.reason ? `<small class="muted">${esc(item.note || item.reason)}</small>` : ""}</td>
      <td>${item.unplanned ? "–" : this.formatDateTime(item.scheduled_at)}</td>
      <td>${item.status === "taken" ? this.formatDateTime(item.taken_at) : "–"}</td>
      <td>${deviation === null || item.unplanned ? "–" : `${deviation > 0 ? "+" : ""}${deviation} ${this.t("common.minutes_short")}`}</td>
      <td>${doses}</td>
    </tr>`;
  }

  empty(icon, title, text) {
    return `<div class="empty card"><ha-icon icon="${icon}"></ha-icon><h3>${title}</h3><p class="muted">${text}</p></div>`;
  }

  // --------------------------------------------------------------------- modals

  dialog(label, title, body, extraClass = "") {
    return `<div class="modal-backdrop"><section class="modal ${extraClass}" role="dialog"
        aria-modal="true" aria-label="${label}" data-modal-stop>
      <div class="modal-head"><h2>${title}</h2>
        <button class="icon" data-action="close-modal" title="${this.t("common.cancel")}">
          <ha-icon icon="mdi:close"></ha-icon></button>
      </div>${body}</section></div>`;
  }

  actions(saveLabel, disabled = false) {
    return `<div class="modal-actions">
      <button type="button" class="ghost" data-action="close-modal">${this.t("common.cancel")}</button>
      <button class="primary" type="submit" ${disabled ? "disabled" : ""}>
        <ha-icon icon="mdi:content-save-outline"></ha-icon>${saveLabel}</button>
    </div>`;
  }

  field(name, label, value = "", options = {}) {
    const { required = false, placeholder = "", type = "text", min = "", max = "", step = "", hint = "" } = options;
    return `<label class="field"><span>${label}${required ? " *" : ""}</span>
      <input name="${name}" type="${type}" value="${esc(value ?? "")}" placeholder="${esc(placeholder)}"
        ${required ? "required" : ""} ${min !== "" ? `min="${min}"` : ""} ${max !== "" ? `max="${max}"` : ""}
        ${step ? `step="${step}"` : ""}>
      ${hint ? `<small class="muted">${hint}</small>` : ""}</label>`;
  }

  medicationModal(item) {
    const body = `<form data-form="medication">
      <input type="hidden" name="id" value="${esc(item.id || "")}">
      <div class="form-grid">
        ${this.field("name", this.t("med_form.name"), item.name, { required: true, placeholder: this.t("med_form.name_placeholder") })}
        ${this.field("manufacturer", this.t("med_form.manufacturer"), item.manufacturer, { placeholder: this.t("med_form.manufacturer_placeholder") })}
        ${this.field("strength", this.t("med_form.strength"), item.strength, { placeholder: this.t("med_form.strength_placeholder") })}
        ${this.field("form", this.t("med_form.form"), item.form, { placeholder: this.t("med_form.form_placeholder") })}
        ${this.field("unit", this.t("med_form.unit"), item.unit || this.t("med_form.unit_default"), { required: true, placeholder: this.t("med_form.unit_placeholder") })}
        ${this.field("low_stock_threshold", this.t("med_form.threshold"), item.low_stock_threshold ?? 0, { required: true, type: "number", min: "0", step: "0.001" })}
        ${this.field("barcode", this.t("med_form.barcode"), item.barcode, { placeholder: this.t("med_form.barcode_placeholder") })}
        <div class="field"><span>${this.t("med_form.stock_calculated")}</span>
          <small class="muted">${this.t(item.id ? "med_form.stock_calculated_help" : "med_form.package_next")}</small></div>
        <label class="field full"><span>${this.t("med_form.notes")}</span>
          <textarea name="notes" rows="3" placeholder="${this.t("med_form.notes_placeholder")}">${esc(item.notes || "")}</textarea></label>
      </div>
      ${this.actions(this.t("common.save"))}</form>`;
    return this.dialog(this.t("med_form.dialog_label"),
      this.t(item.id ? "med_form.edit_title" : "med_form.new_title"), body);
  }

  packageModal(item) {
    const medicationId = item.medication_id || this.modal.medicationId || this.state.medications[0]?.id || "";
    const medication = this.medication(medicationId);
    const unit = esc(medication?.unit || "");
    const body = `<form data-form="package">
      <input type="hidden" name="id" value="${esc(item.id || "")}">
      <div class="form-grid">
        ${this.modal.stepTwo ? `<div class="field full note"><strong>${this.t("package_form.step_two")}</strong>
          <small>${this.t("package_form.step_two_help")}</small></div>` : ""}
        <label class="field full"><span>${this.t("package_form.medication")} *</span>
          <select name="medication_id" required ${item.id ? "disabled" : ""}>
            ${this.state.medications.map((med) =>
              `<option value="${med.id}" ${med.id === medicationId ? "selected" : ""}>${esc(med.name)} (${esc(med.unit)})</option>`).join("")}
          </select>
          ${item.id ? `<input type="hidden" name="medication_id" value="${esc(medicationId)}">` : ""}</label>
        <label class="field"><span>${this.t("package_form.nickname")}</span>
          <input name="nickname" list="package-nicknames" value="${esc(item.nickname || "")}">
          <datalist id="package-nicknames">${PACKAGE_NICKNAMES.map((name) => `<option value="${name}"></option>`).join("")}</datalist>
          <small class="muted">${this.t("package_form.nickname_help")}</small></label>
        ${item.id
          ? this.field("remaining_quantity", `${this.t("package_form.remaining")} (${unit})`, item.remaining_quantity, { required: true, type: "number", min: "0", step: "0.001" })
          : this.field("quantity", `${this.t("package_form.quantity")} (${unit})`, 1, { required: true, type: "number", min: "0.001", step: "0.001" })}
        ${this.field("lot_number", this.t("package_form.lot"), item.lot_number)}
        ${this.field("expires_on", this.t("package_form.expiry"), item.expires_on, { type: "date" })}
        <label class="field full"><span>${this.t("package_form.external_code")}</span>
          <input name="external_code" value="${esc(item.external_code || "")}">
          <small class="muted">${this.t("package_form.external_code_help")}</small></label>
      </div>
      ${this.actions(this.t("package_form.save"))}</form>`;
    return this.dialog(this.t("package_form.dialog_label"),
      this.t(item.id ? "package_form.edit_title" : "package_form.new_title"), body);
  }

  regimenModal(item) {
    const schedule = item.schedule || {
      type: "weekly",
      days: { 0: ["08:00"], 1: ["08:00"], 2: ["08:00"], 3: ["08:00"], 4: ["08:00"], 5: ["09:00"], 6: ["09:00"] },
    };
    const doses = item.items?.length ? item.items : [{ medication_id: this.state.medications[0]?.id || "", dose: 1 }];
    const days = this.days();
    const body = `<form data-form="regimen">
      <input type="hidden" name="id" value="${esc(item.id || "")}">
      <div class="form-grid">
        ${this.field("name", this.t("reg_form.name"), item.name, { required: true, placeholder: this.t("reg_form.name_placeholder") })}
        <label class="field"><span>${this.t("reg_form.status")}</span>
          <select name="active">
            <option value="true" ${item.active !== false ? "selected" : ""}>${this.t("common.active")}</option>
            <option value="false" ${item.active === false ? "selected" : ""}>${this.t("common.paused")}</option>
          </select></label>
        <div class="field full"><span>${this.t("reg_form.medications_dose")}</span>
          <div class="item-editor">${doses.map((dose, index) => this.doseRow(dose, index)).join("")}</div>
          <button type="button" class="text add-dose" data-action="add-dose">
            <ha-icon icon="mdi:plus"></ha-icon>${this.t("reg_form.add_medication")}</button></div>
        <label class="field full"><span>${this.t("reg_form.rhythm")}</span>
          <select name="schedule_type">
            <option value="weekly" ${schedule.type === "weekly" ? "selected" : ""}>${this.t("reg_form.weekly")}</option>
            <option value="interval" ${schedule.type === "interval" ? "selected" : ""}>${this.t("reg_form.interval")}</option>
          </select></label>
        <div class="field full schedule-weekly ${schedule.type === "weekly" ? "" : "hidden"}">
          <span>${this.t("reg_form.weekdays_times")}</span>
          <div class="week-grid">${days.map((day, index) => {
            const times = schedule.type === "weekly"
              ? schedule.days?.[index] || schedule.days?.[String(index)] || [] : [];
            return `<label class="week-row">
              <input type="checkbox" name="day_${index}" ${times.length ? "checked" : ""}>
              <b>${day}</b>
              <input type="text" name="times_${index}" value="${esc(times.join(", ") || "08:00")}" placeholder="08:00, 20:00">
            </label>`;
          }).join("")}</div>
          <small class="muted">${this.t("reg_form.multiple_times_help")}</small></div>
        <div class="field full schedule-interval ${schedule.type === "interval" ? "" : "hidden"}">
          <span>${this.t("reg_form.interval_title")}</span>
          <div class="inline-fields">
            ${this.field("every_days", this.t("reg_form.every_days"), schedule.every_days || 2, { required: true, type: "number", min: "1", max: "365", step: "1" })}
            ${this.field("start_date", this.t("reg_form.start_date"), schedule.start_date || localDateValue(new Date()), { required: true, type: "date" })}
            ${this.field("interval_time", this.t("reg_form.time"), schedule.time || "08:00", { required: true, type: "time" })}
          </div></div>
        <label class="field full"><span>${this.t("reg_form.notify_services")}</span>
          <input name="notify_services" list="notify-services" value="${esc((item.notify_services || []).join(", "))}"
            placeholder="${this.t("reg_form.notify_placeholder")}">
          <datalist id="notify-services">${this.state.notify_services.map((service) => `<option value="${esc(service)}"></option>`).join("")}</datalist>
          <small class="muted">${this.t("reg_form.notify_help")}</small></label>
        <label class="field full"><span>${this.t("reg_form.scripts")}</span>
          <input name="scripts" list="scripts" value="${esc((item.scripts || []).join(", "))}"
            placeholder="${this.t("reg_form.script_placeholder")}">
          <datalist id="scripts">${this.state.scripts.map((script) => `<option value="${esc(script)}"></option>`).join("")}</datalist></label>
        <label class="field full"><span>${this.t("reg_form.instructions")}</span>
          <textarea name="instructions" rows="2" placeholder="${this.t("reg_form.instructions_placeholder")}">${esc(item.instructions || "")}</textarea></label>
        <details class="field full advanced" ${item.reminder_window_minutes === 0 || item.auto_miss_after_minutes ? "open" : ""}>
          <summary>${this.t("common.advanced")}</summary>
          <div class="inline-fields">
            ${this.field("repeat_minutes", this.t("reg_form.repeat"), item.repeat_minutes ?? 30, { required: true, type: "number", min: "5", max: "1440", step: "1" })}
            ${this.field("reminder_window_minutes", this.t("reg_form.window"), item.reminder_window_minutes ?? 180, { required: true, type: "number", min: "0", max: "10080", step: "1", hint: this.t("reg_form.window_help") })}
            ${this.field("auto_miss_after_minutes", this.t("reg_form.auto_miss"), item.auto_miss_after_minutes ?? 0, { required: true, type: "number", min: "0", max: "43200", step: "1", hint: this.t("reg_form.auto_miss_help") })}
          </div>
        </details>
      </div>
      ${this.actions(this.t("reg_form.save"), !this.state.medications.length)}</form>`;
    return this.dialog(this.t("reg_form.dialog_label"),
      this.t(item.id ? "reg_form.edit_title" : "reg_form.new_title"), body, "wide");
  }

  doseRow(dose, index) {
    return `<div class="dose-row">
      <select name="medication_${index}" required>
        <option value="">${this.t("reg_form.choose_medication")}</option>
        ${this.state.medications.map((med) =>
          `<option value="${med.id}" ${med.id === dose.medication_id ? "selected" : ""}>${esc(med.name)} (${esc(med.unit)})</option>`).join("")}
      </select>
      <input name="dose_${index}" type="number" min="0.001" step="0.001" value="${dose.dose}" required>
      <button type="button" class="icon" data-action="remove-dose" title="${this.t("reg_form.remove")}">
        <ha-icon icon="mdi:close"></ha-icon></button>
    </div>`;
  }

  unplannedModal() {
    const body = `<form data-form="unplanned"><div class="form-grid">
        ${this.field("taken_at", this.t("unplanned.taken_at"), localDateTimeValue(new Date()), { required: true, type: "datetime-local" })}
        ${this.field("note", this.t("unplanned.note"), "", { placeholder: this.t("unplanned.note_placeholder") })}
        <div class="field full"><span>${this.t("unplanned.medications")}</span>
          <div class="item-editor">${this.doseRow({ medication_id: this.state.medications[0]?.id || "", dose: 1 }, 0)}</div>
          <button type="button" class="text add-dose" data-action="add-dose">
            <ha-icon icon="mdi:plus"></ha-icon>${this.t("reg_form.add_medication")}</button></div>
      </div>${this.actions(this.t("unplanned.save"))}</form>`;
    return this.dialog(this.t("unplanned.dialog_label"), this.t("unplanned.title"), body);
  }

  codeModal(item) {
    const body = `<div class="code-content">
      <h3>${esc(item.label)}</h3>
      <img src="${esc(item.dataUri)}" alt="${this.t("code.dialog_label")}">
      <code>${esc(item.code)}</code>
      <p class="muted">${this.t("code.help")}</p>
      <div class="modal-actions">
        <button class="ghost" data-action="copy-code" data-value="${esc(item.code)}">
          <ha-icon icon="mdi:content-copy"></ha-icon>${this.t("code.copy")}</button>
        <button class="primary" data-action="close-modal">${this.t("common.close")}</button>
      </div></div>`;
    return this.dialog(this.t("code.dialog_label"),
      this.t("code.title", { object: this.t(`code.${item.kind}`) }), body);
  }

  dataModal() {
    const body = `<div class="data-management">
      <section class="card pad">
        <div><h3>${this.t("data.export_title")}</h3><p class="muted">${this.t("data.export_help")}</p></div>
        <button class="primary" data-action="export-backup">
          <ha-icon icon="mdi:download"></ha-icon>${this.t("data.export_button")}</button>
      </section>
      <form class="card pad" data-form="import-backup">
        <div><h3>${this.t("data.import_title")}</h3><p class="muted">${this.t("data.import_help")}</p></div>
        <label class="field full"><span>${this.t("data.import_file")}</span>
          <input type="file" name="backup_file" accept="application/json,.json" required></label>
        <p class="warning-row warn"><ha-icon icon="mdi:alert-outline"></ha-icon>${this.t("data.import_warning")}</p>
        <div class="modal-actions">
          <button type="button" class="ghost" data-action="close-modal">${this.t("common.cancel")}</button>
          <button class="primary" type="submit">
            <ha-icon icon="mdi:database-import-outline"></ha-icon>${this.t("data.import_button")}</button>
        </div>
      </form></div>`;
    return this.dialog(this.t("data.dialog_label"), this.t("data.title"), body);
  }

  // -------------------------------------------------------------------- actions

  async mutate(operation, success, afterSuccess = null) {
    try {
      const result = await operation();
      this.modal = null;
      await this.load(false);
      if (afterSuccess) afterSuccess(result);
      this.renderOverlay(true);
      this.showToast(success);
    } catch (error) {
      this.showToast(this.errorText(error), true);
    }
  }

  async openCode(kind, id, label) {
    try {
      const target = kind === "medication" ? this.medication(id)
        : kind === "package" ? this.package(id)
        : this.state.occurrences.find((item) => item.id === id);
      const scanCode = target?.scan_code;
      if (!scanCode) throw new Error("Missing scan code");
      const result = await this.call("generate_qr", { value: scanCode });
      this.openModal({ type: "code", item: { kind, id, label, code: scanCode, dataUri: result.data_uri } });
    } catch (error) {
      this.showToast(this.t("error.qr_failed"), true);
    }
  }

  async copyCode(value) {
    try {
      await navigator.clipboard.writeText(value);
      this.showToast(this.t("code.copied"));
    } catch (error) {
      this.showToast(this.t("error.qr_failed"), true);
    }
  }

  async exportHistory(format) {
    if (!this.historyFrom || !this.historyTo || this.historyFrom > this.historyTo) {
      return this.showToast(this.t("error.export_range"), true);
    }
    try {
      const result = await this.call("export_history", {
        start_date: this.historyFrom, end_date: this.historyTo, format,
      });
      if (!result.count) return this.showToast(this.t("history.export_empty"), true);
      this.downloadResult(result);
      this.showToast(this.t("history.export_done", { count: result.count }));
    } catch (error) {
      this.showToast(this.errorText(error), true);
    }
  }

  downloadResult(result) {
    const blob = new Blob([result.content], { type: result.mime_type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = result.filename;
    link.style.display = "none";
    this.shadowRoot.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async exportBackup() {
    try {
      this.downloadResult(await this.call("export_backup"));
      this.showToast(this.t("data.export_done"));
    } catch (error) {
      this.showToast(this.errorText(error), true);
    }
  }

  async importBackup(form) {
    const file = form.elements.backup_file.files?.[0];
    if (!file) return this.showToast(this.t("error.backup_file"), true);
    let backup;
    try {
      backup = JSON.parse(await file.text());
    } catch (error) {
      return this.showToast(this.t("error.backup_invalid"), true);
    }
    if (!window.confirm(this.t("confirm.import_backup"))) return;
    try {
      await this.call("import_backup", { backup });
      this.closeModal();
      await this.load(false);
      this.showToast(this.t("data.import_done"));
    } catch (error) {
      this.showToast(this.errorText(error), true);
    }
  }

  onKeydown(event) {
    if (event.key === "Escape" && this.modal) {
      event.preventDefault();
      this.closeModal();
    }
  }

  onClick(event) {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.tab) {
      this.activeTab = button.dataset.tab;
      this.highlightId = null;
      this.renderNav();
      this.renderMain();
      return;
    }
    const action = button.dataset.action;
    const id = button.dataset.id;
    if (action === "refresh") return this.load();
    if (action === "close-modal") return this.closeModal();
    if (action === "data-management") return this.openModal({ type: "data" });
    if (action === "new-medication") return this.openModal({ type: "medication", item: {} });
    if (action === "edit-medication") return this.openModal({ type: "medication", item: this.medication(id) });
    if (action === "new-package") return this.openModal({ type: "package", medicationId: id, item: {} });
    if (action === "edit-package") return this.openModal({ type: "package", item: this.package(id) });
    if (action === "new-unplanned" || action === "new-regimen") {
      if (!this.state?.medications.length) {
        this.showToast(this.t("error.create_medication_first"), true);
        return this.openModal({ type: "medication", item: {} });
      }
      return this.openModal(action === "new-unplanned" ? { type: "unplanned" } : { type: "regimen", item: {} });
    }
    if (action === "edit-regimen") return this.openModal({ type: "regimen", item: this.regimen(id) });
    if (action === "history-status") {
      this.historyStatus = button.dataset.value;
      return this.renderMain();
    }
    if (action === "delete-all-data") {
      if (!window.confirm(this.t("confirm.delete_all_data"))) return;
      const confirmation = window.prompt(this.t("prompt.delete_all_data"));
      if (confirmation === null) return;
      if (confirmation !== "DELETE") return this.showToast(this.t("error.delete_confirmation"), true);
      return this.mutate(() => this.call("delete_all_data", { confirmation }), this.t("action.all_data_deleted"));
    }
    if (action === "delete-medication") {
      if (!window.confirm(this.t("confirm.delete_medication"))) return;
      return this.mutate(() => this.call("delete_medication", { medication_id: id }), this.t("action.medication_deleted"));
    }
    if (action === "delete-regimen") {
      if (!window.confirm(this.t("confirm.delete_regimen"))) return;
      return this.mutate(() => this.call("delete_regimen", { regimen_id: id }), this.t("action.regimen_deleted"));
    }
    if (action === "delete-package") {
      if (!window.confirm(this.t("confirm.delete_package"))) return;
      return this.mutate(() => this.call("delete_package", { package_id: id }), this.t("action.package_deleted"));
    }
    if (action === "take-selected") return this.takeSelected(id, button.closest(".ticket"));
    if (action === "snooze") {
      return this.mutate(
        () => this.call("snooze", { occurrence_id: id, minutes: Number(button.dataset.minutes) }),
        this.t("action.reminder_snoozed"));
    }
    if (action === "snooze-custom") {
      const input = this.shadowRoot.querySelector(`[data-snooze-time="${id}"]`);
      if (!input?.value) return this.showToast(this.t("error.select_time"), true);
      const until = new Date(input.value);
      if (until <= new Date()) return this.showToast(this.t("error.future_snooze"), true);
      return this.mutate(
        () => this.call("snooze", { occurrence_id: id, until: until.toISOString() }),
        this.t("action.reminder_snoozed_until"));
    }
    if (action === "skip") {
      if (!window.confirm(this.t("confirm.skip"))) return;
      return this.mutate(() => this.call("skip", { occurrence_id: id }), this.t("action.intake_skipped"));
    }
    if (action === "postpone-interval") {
      if (!window.confirm(this.t("confirm.postpone_interval"))) return;
      return this.mutate(() => this.call("postpone_interval", { occurrence_id: id }), this.t("action.interval_postponed"));
    }
    if (action === "show-code") return this.openCode(button.dataset.kind, id, button.dataset.label);
    if (action === "copy-code") return this.copyCode(button.dataset.value);
    if (action === "export-history") return this.exportHistory(button.dataset.format);
    if (action === "export-backup") return this.exportBackup();
    if (action === "add-dose") return this.addDoseRow(button);
    if (action === "remove-dose") {
      const editor = button.closest(".item-editor");
      if (editor.children.length > 1) button.closest(".dose-row").remove();
      return;
    }
  }

  takeSelected(id, ticket) {
    const doses = {};
    ticket.querySelectorAll("[data-medication]").forEach((checkbox) => {
      if (!checkbox.checked) return;
      const amount = Number(ticket.querySelector(`[data-dose="${checkbox.dataset.medication}"]`).value);
      if (Number.isFinite(amount) && amount > 0) doses[checkbox.dataset.medication] = amount;
    });
    if (!Object.keys(doses).length) return this.showToast(this.t("error.select_dose"), true);
    return this.mutate(() => this.call("record_intake", { occurrence_id: id, doses }), this.t("action.intake_recorded"));
  }

  addDoseRow(button) {
    const editor = button.parentElement.querySelector(".item-editor");
    const index = Math.max(-1, ...[...editor.querySelectorAll("select")]
      .map((element) => Number(element.name.split("_")[1]))) + 1;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = this.doseRow({ medication_id: "", dose: 1 }, index);
    editor.append(wrapper.firstElementChild);
  }

  onInput(event) {
    if (event.target.name === "history_search") {
      this.historySearch = event.target.value;
      window.clearTimeout(this.searchTimer);
      this.searchTimer = window.setTimeout(() => {
        const active = this.shadowRoot.activeElement;
        const caret = active?.selectionStart ?? null;
        this.$main.innerHTML = this.renderHistory();
        const field = this.$main.querySelector('[name="history_search"]');
        if (field) {
          field.focus({ preventScroll: true });
          if (caret !== null) field.setSelectionRange(caret, caret);
        }
      }, 250);
    }
  }

  onChange(event) {
    if (event.target.name === "history_from") { this.historyFrom = event.target.value; return; }
    if (event.target.name === "history_to") { this.historyTo = event.target.value; return; }
    if (event.target.name === "schedule_type") {
      const form = event.target.form;
      form.querySelector(".schedule-weekly").classList.toggle("hidden", event.target.value !== "weekly");
      form.querySelector(".schedule-interval").classList.toggle("hidden", event.target.value !== "interval");
    }
  }

  onSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const data = new FormData(form);
    if (form.dataset.form === "medication") {
      const medication = Object.fromEntries(data.entries());
      medication.low_stock_threshold = Number(medication.low_stock_threshold);
      const isNew = !medication.id;
      if (isNew) delete medication.id;
      return this.mutate(
        () => this.call("save_medication", { medication }),
        this.t("action.medication_saved"),
        isNew ? (saved) => { this.modal = { type: "package", medicationId: saved.id, item: {}, stepTwo: true }; } : null,
      );
    }
    if (form.dataset.form === "import-backup") return this.importBackup(form);
    if (form.dataset.form === "package") {
      const packageData = Object.fromEntries(data.entries());
      if (packageData.id) packageData.remaining_quantity = Number(packageData.remaining_quantity);
      else {
        delete packageData.id;
        packageData.quantity = Number(packageData.quantity);
      }
      return this.mutate(() => this.call("save_package", { package: packageData }), this.t("action.package_saved"));
    }
    if (form.dataset.form === "unplanned") {
      let items;
      try {
        items = this.doseItems(form);
      } catch (error) {
        return this.showToast(error.message, true);
      }
      const takenAt = new Date(data.get("taken_at"));
      if (takenAt > new Date()) return this.showToast(this.t("error.unplanned_future"), true);
      return this.mutate(
        () => this.call("record_unplanned_intake", {
          items, taken_at: takenAt.toISOString(), note: data.get("note") || "",
        }),
        this.t("action.unplanned_saved"));
    }
    if (form.dataset.form === "regimen") {
      try {
        const regimen = this.regimenFromForm(form, data);
        return this.mutate(() => this.call("save_regimen", { regimen }), this.t("action.regimen_saved"));
      } catch (error) {
        this.showToast(error.message, true);
      }
    }
  }

  doseItems(form) {
    const items = [...form.querySelectorAll(".dose-row")].map((row) => ({
      medication_id: row.querySelector("select").value,
      dose: Number(row.querySelector("input").value),
    }));
    if (new Set(items.map((item) => item.medication_id)).size !== items.length) {
      throw new Error(this.t("error.medication_duplicate"));
    }
    return items;
  }

  regimenFromForm(form, data) {
    const items = this.doseItems(form);
    let schedule;
    if (data.get("schedule_type") === "weekly") {
      const days = {};
      const dayNames = this.days();
      dayNames.forEach((_, index) => {
        if (!form.elements[`day_${index}`].checked) return;
        const times = form.elements[`times_${index}`].value.split(",").map((value) => value.trim()).filter(Boolean);
        if (!times.length || times.some((time) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))) {
          throw new Error(this.t("error.invalid_time", { day: dayNames[index] }));
        }
        days[index] = times;
      });
      if (!Object.keys(days).length) throw new Error(this.t("error.select_weekday"));
      schedule = { type: "weekly", days };
    } else {
      schedule = {
        type: "interval",
        every_days: Number(data.get("every_days")),
        start_date: data.get("start_date"),
        time: data.get("interval_time"),
      };
    }
    const split = (name) => String(data.get(name) || "").split(",").map((value) => value.trim()).filter(Boolean);
    const regimen = {
      id: data.get("id") || undefined,
      name: data.get("name"),
      active: data.get("active") === "true",
      items,
      schedule,
      repeat_minutes: Number(data.get("repeat_minutes")),
      reminder_window_minutes: Number(data.get("reminder_window_minutes")),
      auto_miss_after_minutes: Number(data.get("auto_miss_after_minutes")),
      notify_services: split("notify_services"),
      scripts: split("scripts"),
      instructions: data.get("instructions"),
    };
    if (!regimen.id) delete regimen.id;
    return regimen;
  }
}

if (!customElements.get("medication-reminder-panel")) {
  customElements.define("medication-reminder-panel", MedicationReminderPanel);
}
