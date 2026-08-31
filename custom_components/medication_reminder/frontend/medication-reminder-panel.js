import { createTranslator, resolveLanguage } from "./localize.js";

const DAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const PACKAGE_NICKNAMES = ["Apollo", "Bumblebee", "Comet", "Daisy", "Echo", "Foxy", "Kiwi", "Mochi", "Nova", "Pebble", "Pixel", "Rocket", "Sunny", "Tango", "Yoshi", "Ziggy"];

const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
class MedicationReminderPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.state = null;
    this.activeTab = "overview";
    this.modal = null;
    this.loading = false;
    this.lastLoad = 0;
    this.toast = null;
    this.language = "en";
    this.locale = "en-US";
    this.t = createTranslator("en");
    this.shadowRoot.addEventListener("click", (event) => this.onClick(event));
    this.shadowRoot.addEventListener("submit", (event) => this.onSubmit(event));
    this.shadowRoot.addEventListener("change", (event) => this.onChange(event));
  }

  set hass(value) {
    this._hass = value;
    const language = resolveLanguage(value);
    if (language !== this.language) {
      this.language = language;
      this.locale = language === "de" ? "de-DE" : "en-US";
      this.t = createTranslator(language);
      if (this.isConnected) this.render();
    }
    if (!this.state && !this.loading) this.load();
  }
  get hass() { return this._hass; }
  set panel(value) { this._panel = value; }
  set narrow(value) { this._narrow = value; }

  connectedCallback() {
    this.render();
    this.poller = window.setInterval(() => this.load(false), 30000);
  }

  disconnectedCallback() { window.clearInterval(this.poller); }

  async call(type, payload = {}) {
    if (!this.hass) throw new Error("Home Assistant is not connected yet.");
    return this.hass.connection.sendMessagePromise({ type: `medication_reminder/${type}`, ...payload });
  }

  async load(showSpinner = true) {
    if (this.loading || !this.hass) return;
    this.loading = true;
    if (showSpinner) this.render();
    try {
      this.state = await this.call("get_state");
      this.lastLoad = Date.now();
      const requested = new URLSearchParams(window.location.search).get("occurrence");
      if (requested && this.state.occurrences.some((item) => item.id === requested)) this.activeTab = "overview";
      this.applyScanLink();
    } catch (error) {
      this.showToast(this.errorText(error), true);
    } finally {
      this.loading = false;
      this.render();
    }
  }

  errorText(error) {
    const message = error?.body?.message || error?.message;
    if (!message) return this.t("error.generic");
    const translations = {
      "Medication Reminder is not configured": "error.not_configured",
      "Medication is still used by an intake": "error.medication_in_use",
      "Stock cannot become negative": "error.negative_stock",
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
      "every_days must be between 1 and 365": "error.every_days_range",
      "Unsupported schedule type": "error.schedule_type",
      "Invalid snooze time": "error.invalid_snooze",
      "Time must use HH:MM": "error.invalid_time_generic",
      "Invalid time": "error.invalid_time_generic",
      "Package-tracked stock must be adjusted on a package": "error.package_stock_adjust",
      "Package quantity must be greater than zero": "error.package_quantity",
      "Package nickname must be unique per medication": "error.package_nickname",
      "Intake time must not be in the future": "error.unplanned_future",
      "Only untouched open intakes can shift their cycle": "error.interval_only",
      "Only interval schedules can shift their cycle": "error.interval_only",
      "Only due intakes can shift to tomorrow": "error.interval_only",
    };
    if (translations[message]) return this.t(translations[message]);
    if (message.startsWith("Not enough stock for ")) {
      return this.t("error.not_enough_stock", { medication: message.slice(21) });
    }
    if (/ must (not be negative|be greater than zero)$/.test(message)) {
      return this.t("error.invalid_value");
    }
    return message;
  }

  showToast(message, error = false) {
    this.toast = { message, error };
    this.render();
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => { this.toast = null; this.render(); }, 4000);
  }

  medication(id) { return this.state?.medications.find((item) => item.id === id); }
  package(id) { return this.state?.packages?.find((item) => item.id === id); }
  regimen(id) { return this.state?.regimens.find((item) => item.id === id); }
  packagesFor(medicationId) {
    return (this.state?.packages || []).filter((item) => item.medication_id === medicationId)
      .sort((a, b) => (a.expires_on || "9999-12-31").localeCompare(b.expires_on || "9999-12-31"));
  }
  scanUrl(type, id) {
    const url = new URL("/medication_reminder", window.location.origin);
    url.searchParams.set("scan", `${type}:${id}`);
    return url.toString();
  }
  applyScanLink() {
    const value = new URLSearchParams(window.location.search).get("scan");
    if (!value) return;
    const [type, id] = value.split(":", 2);
    if (type === "intake" && this.state.occurrences.some((item) => item.id === id)) this.activeTab = "overview";
    if (type === "medication" && this.medication(id)) this.activeTab = "medications";
    if (type === "package" && this.package(id)) this.activeTab = "medications";
    this.highlightId = id;
  }
  days() { return DAY_KEYS.map((day) => this.t(`day.${day}`)); }
  status(status) { return this.t(`status.${status}`); }
  formatNumber(value) {
    return new Intl.NumberFormat(this.locale, { maximumFractionDigits: 3 }).format(value ?? 0);
  }
  formatDate(value) {
    return value ? new Intl.DateTimeFormat(this.locale).format(new Date(`${value}T00:00:00`)) : "–";
  }
  formatDateTime(value) {
    return value ? new Intl.DateTimeFormat(this.locale, {
      weekday: "short", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"
    }).format(new Date(value)) : "–";
  }
  formatTime(value) {
    return new Intl.DateTimeFormat(this.locale, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
  }
  relative(value) {
    if (!value) return this.t("common.none");
    const diff = new Date(value).getTime() - Date.now();
    const minutes = Math.round(Math.abs(diff) / 60000);
    if (minutes < 1) return this.t("relative.now");
    if (minutes < 60) return this.t(diff < 0 ? "relative.before_minutes" : "relative.in_minutes", { minutes });
    const hours = Math.round(minutes / 60);
    if (hours < 24) return this.t(diff < 0 ? "relative.before_hours" : "relative.in_hours", { hours });
    return this.formatDateTime(value);
  }
  packagePlanText(plan, unit) {
    return (plan || []).map((part) => {
      const details = [part.lot_number ? this.t("package.lot", { lot: part.lot_number }) : "", part.expires_on ? this.t("package.expires", { date: this.formatDate(part.expires_on) }) : ""].filter(Boolean).join(", ");
      return `${part.nickname} (${this.formatNumber(part.amount)} ${unit}${details ? ` · ${details}` : ""})`;
    }).join(" + ");
  }

  render() {
    const content = !this.state
      ? `<div class="loading"><div class="loader"></div><h2>${this.t("app.loading_title")}</h2><p>${this.t("app.loading_text")}</p></div>`
      : this.renderContent();
    this.shadowRoot.innerHTML = `<style>${this.styles()}</style>${content}${this.renderModal()}${this.renderToast()}`;
  }

  renderContent() {
    const tabs = [
      ["overview", "mdi:view-dashboard-outline", this.t("nav.overview")],
      ["medications", "mdi:pill-multiple", this.t("nav.medications")],
      ["regimens", "mdi:calendar-clock", this.t("nav.regimens")],
      ["history", "mdi:history", this.t("nav.history")],
    ];
    return `<div class="app">
      <header>
        <div class="brand"><div class="brand-icon"><img src="/medication_reminder_frontend/logo.png" alt=""></div>
          <div><span>MEDICATION REMINDER</span><h1>${this.t("app.title")}</h1></div></div>
        <div class="header-actions"><button class="ghost" data-action="new-unplanned"><ha-icon icon="mdi:pill-plus"></ha-icon><span>${this.t("app.record_unplanned")}</span></button><button class="ghost icon-only" data-action="refresh" title="${this.t("app.refresh")}"><ha-icon icon="mdi:refresh"></ha-icon></button>
          <button class="primary" data-action="new-regimen"><ha-icon icon="mdi:plus"></ha-icon><span>${this.t("regimens.create")}</span></button></div>
      </header>
      <nav>${tabs.map(([id, icon, label]) => `<button data-tab="${id}" class="${this.activeTab === id ? "active" : ""}"><ha-icon icon="${icon}"></ha-icon>${label}</button>`).join("")}</nav>
      <main>${this.renderTab()}</main>
      <footer><span><i class="live"></i> ${this.t("app.local_storage")}</span><span>${this.t("app.last_synced", { time: this.formatTime(this.lastLoad) })}</span></footer>
    </div>`;
  }

  renderTab() {
    if (this.activeTab === "medications") return this.renderMedications();
    if (this.activeTab === "regimens") return this.renderRegimens();
    if (this.activeTab === "history") return this.renderHistory();
    return this.renderOverview();
  }

  renderOverview() {
    const open = this.state.occurrences.filter((item) => ["pending", "partial"].includes(item.status))
      .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
    const low = this.state.medications.filter((item) => item.stock <= item.low_stock_threshold);
    const next = this.state.upcoming[0];
    const nextRegimen = next ? this.regimen(next.regimen_id) : null;
    return `<section class="hero">
        <div><p class="eyebrow">${this.t("overview.eyebrow")}</p><h2>${open.length ? this.t(open.length === 1 ? "overview.waiting_one" : "overview.waiting_many", { count: open.length }) : this.t("overview.all_done")}</h2>
          <p>${this.t(open.length ? "overview.open_help" : "overview.no_open")}</p></div>
        <div class="hero-orb"><ha-icon icon="${open.length ? "mdi:clock-alert-outline" : "mdi:check-bold"}"></ha-icon></div>
      </section>
      <section class="stats">
        ${this.stat("mdi:calendar-arrow-right", this.t("overview.next_intake"), nextRegimen?.name || this.t("common.none"), next ? this.relative(next.scheduled_at) : "–", "mint")}
        ${this.stat("mdi:clipboard-clock-outline", this.t("overview.open_tickets"), open.length, this.t(open.length ? "overview.check_required" : "overview.up_to_date"), open.length ? "amber" : "blue")}
        ${this.stat("mdi:package-variant", this.t("overview.low_stock"), low.length, low.length ? low.map((m) => esc(m.name)).join(", ") : this.t("overview.well_stocked"), low.length ? "red" : "violet")}
        ${this.stat("mdi:pill", this.t("overview.medications"), this.state.medications.length, this.t("overview.active_plans", { count: this.state.regimens.filter((r) => r.active).length }), "blue")}
      </section>
      <div class="section-heading"><div><p class="eyebrow">${this.t("overview.open_eyebrow")}</p><h2>${this.t("overview.due_intakes")}</h2></div></div>
      <section class="ticket-list">${open.length ? open.map((item) => this.renderTicket(item)).join("") : this.empty("mdi:check-decagram-outline", this.t("overview.no_due_title"), this.t("overview.no_due_text"))}</section>
      <div class="section-heading"><div><p class="eyebrow">${this.t("overview.stock_eyebrow")}</p><h2>${this.t("overview.quick_view")}</h2></div><button class="ghost" data-action="new-medication"><ha-icon icon="mdi:plus"></ha-icon>${this.t("overview.add_medication")}</button></div>
      <section class="stock-grid">${this.state.medications.length ? this.state.medications.slice(0, 6).map((item) => this.stockCard(item, true)).join("") : this.empty("mdi:pill-off", this.t("overview.no_medications_title"), this.t("overview.no_medications_text"))}</section>`;
  }

  stat(icon, label, value, hint, tone) {
    return `<article class="stat"><div class="stat-icon ${tone}"><ha-icon icon="${icon}"></ha-icon></div><div><span>${label}</span><strong>${esc(value)}</strong><small>${hint}</small></div></article>`;
  }

  renderTicket(item) {
    const regimen = this.regimen(item.regimen_id);
    if (!regimen) return "";
    const snoozed = item.snoozed_until && new Date(item.snoozed_until) > new Date();
    return `<article class="ticket ${this.highlightId === item.id ? "highlight" : ""}" data-occurrence="${item.id}">
      <div class="ticket-side ${snoozed ? "snoozed" : ""}"><ha-icon icon="${snoozed ? "mdi:power-sleep" : "mdi:alarm"}"></ha-icon></div>
      <div class="ticket-body"><div class="ticket-head"><div><span class="badge ${item.status}">${this.status(item.status)}</span><h3>${esc(regimen.name)}</h3><p>${this.t("ticket.due", { time: this.formatDateTime(item.scheduled_at) })} · ${snoozed ? this.t("ticket.snoozed_until", { time: this.formatDateTime(item.snoozed_until) }) : this.relative(item.scheduled_at)}</p></div><strong class="time">${this.formatTime(item.scheduled_at)}</strong></div>
        ${regimen.instructions ? `<p class="instructions"><ha-icon icon="mdi:information-outline"></ha-icon>${esc(regimen.instructions)}</p>` : ""}
        <div class="dose-list">${item.items.map((dose) => {
          const med = this.medication(dose.medication_id);
          const remaining = Math.max(0, dose.planned_dose - dose.taken_dose);
          return `<label class="dose ${remaining === 0 ? "done" : ""}"><input type="checkbox" data-medication="${dose.medication_id}" ${remaining ? "checked" : "disabled"}>
            <span class="pill-dot"></span><span class="dose-name"><strong>${esc(med?.name || this.t("ticket.deleted_medication"))}</strong><small>${esc(med?.strength || med?.form || "")}</small>${dose.package_plan?.length ? `<small class="pack-plan">${this.t("ticket.take_from", { packages: esc(this.packagePlanText(dose.package_plan, med?.unit || "")) })}</small>` : ""}</span>
            <span class="dose-amount"><input type="number" data-dose="${dose.medication_id}" min="0" max="${remaining}" step="0.001" value="${remaining}" ${remaining ? "" : "disabled"}> ${esc(med?.unit || "")}${dose.taken_dose ? `<small>${this.t("ticket.already_taken", { amount: this.formatNumber(dose.taken_dose) })}</small>` : ""}</span></label>`;
        }).join("")}</div>
        <div class="ticket-actions"><button class="primary" data-action="take-selected" data-id="${item.id}"><ha-icon icon="mdi:check"></ha-icon>${this.t("ticket.take_selection")}</button>
          <div class="snooze"><button class="ghost" data-action="snooze" data-id="${item.id}" data-minutes="30">${this.t("ticket.snooze_30")}</button><button class="ghost" data-action="snooze" data-id="${item.id}" data-minutes="60">${this.t("ticket.snooze_60")}</button><button class="ghost" data-action="snooze" data-id="${item.id}" data-minutes="120">${this.t("ticket.snooze_120")}</button></div>
          <input class="custom-time" type="datetime-local" data-snooze-time="${item.id}"><button class="ghost icon-only" data-action="snooze-custom" data-id="${item.id}" title="${this.t("ticket.custom_snooze")}"><ha-icon icon="mdi:clock-edit-outline"></ha-icon></button>
          ${regimen.schedule.type === "interval" && item.status === "pending" ? `<button class="ghost" data-action="postpone-interval" data-id="${item.id}"><ha-icon icon="mdi:calendar-arrow-right"></ha-icon>${this.t("ticket.postpone_tomorrow")}</button>` : ""}
          <button class="ghost icon-only" data-action="show-code" data-kind="intake" data-id="${item.id}" data-label="${esc(regimen.name)}" title="${this.t("ticket.qr")}"><ha-icon icon="mdi:qrcode"></ha-icon></button>
          <button class="text danger-text" data-action="skip" data-id="${item.id}">${this.t("ticket.skip")}</button></div>
      </div></article>`;
  }

  renderMedications() {
    return `<div class="page-title"><div><p class="eyebrow">${this.t("medications.eyebrow")}</p><h2>${this.t("medications.title")}</h2><p>${this.t("medications.subtitle")}</p></div><button class="primary" data-action="new-medication"><ha-icon icon="mdi:plus"></ha-icon>${this.t("medications.create")}</button></div>
      <section class="stock-grid large">${this.state.medications.length ? this.state.medications.map((item) => this.stockCard(item, false)).join("") : this.empty("mdi:pill-off", this.t("medications.empty_title"), this.t("medications.empty_text"))}</section>`;
  }

  stockCard(item, compact) {
    const low = item.stock <= item.low_stock_threshold;
    const percentage = item.low_stock_threshold > 0 ? Math.min(100, (item.stock / Math.max(item.low_stock_threshold * 3, 1)) * 100) : 100;
    const packages = this.packagesFor(item.id);
    const openPackages = packages.filter((pack) => pack.remaining_quantity > 0);
    return `<article class="stock-card ${low ? "is-low" : ""} ${this.highlightId === item.id ? "highlight" : ""}"><div class="stock-top"><div class="medicine-icon"><ha-icon icon="mdi:pill"></ha-icon></div><span class="badge ${low ? "warning" : "ok"}">${this.t(low ? "stock.reorder" : "stock.available")}</span></div>
      <h3>${esc(item.name)}</h3><p>${[item.manufacturer, item.strength, item.form].filter(Boolean).map(esc).join(" · ") || this.t("stock.no_details")}</p>
      <div class="stock-value"><strong>${this.formatNumber(item.stock)}</strong><span>${esc(item.unit)}</span></div><div class="progress"><i style="width:${percentage}%"></i></div><small>${this.t("stock.warning_at", { amount: this.formatNumber(item.low_stock_threshold), unit: esc(item.unit) })} · ${this.t(item.stock_mode === "packages" ? "stock.automatic" : "stock.manual")}</small>
      ${!compact ? `<div class="package-section"><div class="package-heading"><b>${this.t("stock.packages")}</b><span>${openPackages.length}</span></div>${packages.length ? packages.map((pack) => this.packageCard(pack, item)).join("") : `<small>${this.t("stock.no_packages")}</small>`}</div>` : openPackages.length ? `<p class="next-package">${this.t("stock.next_package", { package: esc(openPackages[0].nickname) })}</p>` : ""}
      <div class="card-actions">${item.stock_mode !== "packages" ? `<button class="ghost" data-action="adjust-stock" data-id="${item.id}"><ha-icon icon="mdi:plus-minus-variant"></ha-icon>${this.t("stock.adjust")}</button>` : ""}<button class="ghost" data-action="new-package" data-id="${item.id}"><ha-icon icon="mdi:package-variant-plus"></ha-icon>${this.t("stock.add_package")}</button><button class="ghost icon-only" data-action="show-code" data-kind="medication" data-id="${item.id}" data-label="${esc(item.name)}" title="${this.t("package.code")}"><ha-icon icon="mdi:qrcode"></ha-icon></button>${compact ? `<button class="text" data-tab="medications">${this.t("common.details")}</button>` : `<button class="text" data-action="edit-medication" data-id="${item.id}">${this.t("common.edit")}</button><button class="text danger-text" data-action="delete-medication" data-id="${item.id}">${this.t("common.delete")}</button>`}</div></article>`;
  }

  packageCard(pack, medication) {
    const empty = pack.remaining_quantity <= 0;
    return `<div class="package-row ${empty ? "empty-package" : ""} ${this.highlightId === pack.id ? "highlight" : ""}"><div class="package-mark"><ha-icon icon="mdi:package-variant-closed"></ha-icon></div><div><strong>${esc(pack.nickname)}</strong><small>${this.t("package.remaining", { amount: this.formatNumber(pack.remaining_quantity), unit: esc(medication.unit) })}</small><small>${[pack.lot_number ? this.t("package.lot", { lot: esc(pack.lot_number) }) : "", pack.expires_on ? this.t("package.expires", { date: this.formatDate(pack.expires_on) }) : this.t("package.no_expiry")].filter(Boolean).join(" · ")}</small></div><div class="package-actions"><button class="text icon-only" data-action="show-code" data-kind="package" data-id="${pack.id}" data-label="${esc(pack.nickname)}" title="${this.t("package.code")}"><ha-icon icon="mdi:qrcode"></ha-icon></button><button class="text icon-only" data-action="edit-package" data-id="${pack.id}" title="${this.t("package.edit")}"><ha-icon icon="mdi:pencil-outline"></ha-icon></button><button class="text icon-only danger-text" data-action="delete-package" data-id="${pack.id}" title="${this.t("package.delete")}"><ha-icon icon="mdi:delete-outline"></ha-icon></button></div></div>`;
  }

  renderRegimens() {
    return `<div class="page-title"><div><p class="eyebrow">${this.t("regimens.eyebrow")}</p><h2>${this.t("regimens.title")}</h2><p>${this.t("regimens.subtitle")}</p></div><button class="primary" data-action="new-regimen"><ha-icon icon="mdi:plus"></ha-icon>${this.t("regimens.create")}</button></div>
      <section class="regimen-list">${this.state.regimens.length ? this.state.regimens.map((item) => this.regimenCard(item)).join("") : this.empty("mdi:calendar-blank-outline", this.t("regimens.empty_title"), this.t("regimens.empty_text"))}</section>`;
  }

  regimenCard(item) {
    return `<article class="regimen-card ${item.active ? "" : "inactive"}"><div class="regimen-icon"><ha-icon icon="mdi:calendar-clock"></ha-icon></div><div class="regimen-main"><div class="regimen-title"><span class="badge ${item.active ? "ok" : "muted"}">${this.t(item.active ? "common.active" : "common.paused")}</span><h3>${esc(item.name)}</h3></div>
      <p class="schedule"><ha-icon icon="mdi:clock-outline"></ha-icon>${esc(this.scheduleText(item.schedule))}</p><div class="chips">${item.items.map((dose) => { const med = this.medication(dose.medication_id); return `<span>${this.formatNumber(dose.dose)} ${esc(med?.unit || "")} ${esc(med?.name || this.t("ticket.deleted_medication"))}</span>`; }).join("")}</div>
      <small>${this.t("regimens.reminder_summary", { targets: item.notify_services.length, minutes: item.repeat_minutes })}</small></div>
      <div class="vertical-actions"><button class="ghost icon-only" data-action="edit-regimen" data-id="${item.id}" title="${this.t("common.edit")}"><ha-icon icon="mdi:pencil-outline"></ha-icon></button><button class="ghost icon-only danger-text" data-action="delete-regimen" data-id="${item.id}" title="${this.t("common.delete")}"><ha-icon icon="mdi:delete-outline"></ha-icon></button></div></article>`;
  }

  scheduleText(schedule) {
    if (schedule.type === "interval") return this.t(schedule.every_days === 1 ? "schedule.every_day" : "schedule.every_days", { days: schedule.every_days, date: this.formatDate(schedule.start_date), time: schedule.time });
    const groups = new Map();
    const days = this.days();
    Object.entries(schedule.days).forEach(([day, times]) => {
      const key = times.join(", ");
      groups.set(key, [...(groups.get(key) || []), days[Number(day)].slice(0, 2)]);
    });
    return [...groups.entries()].map(([times, groupedDays]) => this.t("schedule.weekly_group", { days: groupedDays.join(", "), times })).join(" | ");
  }

  renderHistory() {
    const rows = this.state.occurrences.filter((item) => ["taken", "skipped"].includes(item.status)).sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at));
    return `<div class="page-title"><div><p class="eyebrow">${this.t("history.eyebrow")}</p><h2>${this.t("history.title")}</h2><p>${this.t("history.subtitle")}</p></div></div>
      ${rows.length ? `<div class="table-wrap"><table><thead><tr><th>${this.t("history.status")}</th><th>${this.t("history.intake")}</th><th>${this.t("history.scheduled")}</th><th>${this.t("history.actual")}</th><th>${this.t("history.deviation")}</th><th>${this.t("history.doses")}</th></tr></thead><tbody>${rows.map((item) => {
        const regimen = this.regimen(item.regimen_id); const actual = item.taken_at ? new Date(item.taken_at) : null; const planned = new Date(item.scheduled_at);
        const diff = actual && item.status !== "skipped" ? Math.round((actual - planned) / 60000) : null;
        const intakeName = item.unplanned ? this.t("unplanned.history_name") : regimen?.name || item.regimen_name || this.t("history.deleted_schedule");
        const doses = item.items.map((dose) => {
          const medication = this.medication(dose.medication_id);
          const allocations = dose.allocations?.length ? `<small class="history-packages">${this.t("history.packages", { packages: esc(this.packagePlanText(dose.allocations, medication?.unit || "")) })}</small>` : "";
          return `${this.formatNumber(dose.taken_dose)}/${this.formatNumber(dose.planned_dose)} ${esc(medication?.name || "")}${allocations}`;
        }).join("<br>");
        return `<tr><td><span class="badge ${item.status}">${this.status(item.status)}</span></td><td><strong>${esc(intakeName)}</strong></td><td>${item.unplanned ? "–" : this.formatDateTime(item.scheduled_at)}</td><td>${item.status === "skipped" ? this.status("skipped") : this.formatDateTime(item.taken_at)}</td><td>${item.unplanned || diff === null ? "–" : `${diff > 0 ? "+" : ""}${diff} ${this.t("common.minutes_short")}`}</td><td>${doses}</td></tr>`;
      }).join("")}</tbody></table></div>` : this.empty("mdi:history", this.t("history.empty_title"), this.t("history.empty_text"))}`;
  }

  empty(icon, title, text) { return `<div class="empty"><ha-icon icon="${icon}"></ha-icon><h3>${title}</h3><p>${text}</p></div>`; }

  renderModal() {
    if (!this.modal || !this.state) return "";
    if (this.modal.type === "medication") return this.medicationModal(this.modal.item);
    if (this.modal.type === "regimen") return this.regimenModal(this.modal.item);
    if (this.modal.type === "package") return this.packageModal(this.modal.item);
    if (this.modal.type === "unplanned") return this.unplannedModal();
    if (this.modal.type === "code") return this.codeModal(this.modal.item);
    return "";
  }

  medicationModal(item = {}) {
    return `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${this.t("med_form.dialog_label")}" data-modal-stop>
      <div class="modal-head"><div><p class="eyebrow">${this.t("med_form.eyebrow")}</p><h2>${this.t(item.id ? "med_form.edit_title" : "med_form.new_title")}</h2></div><button class="ghost icon-only" data-action="close-modal" title="${this.t("common.cancel")}"><ha-icon icon="mdi:close"></ha-icon></button></div>
      <form data-form="medication"><input type="hidden" name="id" value="${esc(item.id || "")}"><div class="form-grid">
        ${this.field("name", this.t("med_form.name"), item.name, true, this.t("med_form.name_placeholder"))}${this.field("manufacturer", this.t("med_form.manufacturer"), item.manufacturer, false, this.t("med_form.manufacturer_placeholder"))}
        ${this.field("barcode", this.t("med_form.barcode"), item.barcode, false, this.t("med_form.barcode_placeholder"))}${this.field("strength", this.t("med_form.strength"), item.strength, false, this.t("med_form.strength_placeholder"))}
        ${this.field("form", this.t("med_form.form"), item.form, false, this.t("med_form.form_placeholder"))}${this.field("unit", this.t("med_form.unit"), item.unit || this.t("med_form.unit_default"), true, this.t("med_form.unit_placeholder"))}
        ${this.field("stock", this.t("med_form.stock"), item.stock ?? 0, true, "", "number", "0", "0.001")}${this.field("low_stock_threshold", this.t("med_form.threshold"), item.low_stock_threshold ?? 0, true, "", "number", "0", "0.001")}
        <label class="field full"><span>${this.t("med_form.notes")}</span><textarea name="notes" rows="3" placeholder="${this.t("med_form.notes_placeholder")}">${esc(item.notes || "")}</textarea></label>
      </div><div class="modal-actions"><button type="button" class="ghost" data-action="close-modal">${this.t("common.cancel")}</button><button class="primary" type="submit"><ha-icon icon="mdi:content-save-outline"></ha-icon>${this.t("common.save")}</button></div></form>
    </section></div>`;
  }

  packageModal(item = {}) {
    const medicationId = item.medication_id || this.modal.medicationId || this.state.medications[0]?.id || "";
    const medication = this.medication(medicationId);
    return `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${this.t("package_form.dialog_label")}" data-modal-stop>
      <div class="modal-head"><div><p class="eyebrow">${this.t("package_form.eyebrow")}</p><h2>${this.t(item.id ? "package_form.edit_title" : "package_form.new_title")}</h2></div><button class="ghost icon-only" data-action="close-modal" title="${this.t("common.cancel")}"><ha-icon icon="mdi:close"></ha-icon></button></div>
      <form data-form="package"><input type="hidden" name="id" value="${esc(item.id || "")}"><div class="form-grid">
        <label class="field full"><span>${this.t("package_form.medication")} *</span><select name="medication_id" required ${item.id ? "disabled" : ""}>${this.state.medications.map((med) => `<option value="${med.id}" ${med.id === medicationId ? "selected" : ""}>${esc(med.name)} (${esc(med.unit)})</option>`).join("")}</select>${item.id ? `<input type="hidden" name="medication_id" value="${esc(medicationId)}">` : ""}</label>
        <label class="field"><span>${this.t("package_form.nickname")}</span><input name="nickname" list="package-nicknames" value="${esc(item.nickname || "")}"><datalist id="package-nicknames">${PACKAGE_NICKNAMES.map((name) => `<option value="${name}"></option>`).join("")}</datalist><small>${this.t("package_form.nickname_help")}</small></label>
        ${item.id ? this.field("remaining_quantity", `${this.t("package_form.remaining")} (${esc(medication?.unit || "")})`, item.remaining_quantity, true, "", "number", "0", "0.001") : this.field("quantity", `${this.t("package_form.quantity")} (${esc(medication?.unit || "")})`, 1, true, "", "number", "0.001", "0.001")}
        ${this.field("lot_number", this.t("package_form.lot"), item.lot_number)}${this.field("expires_on", this.t("package_form.expiry"), item.expires_on, false, "", "date")}
        <label class="field full"><span>${this.t("package_form.external_code")}</span><input name="external_code" value="${esc(item.external_code || "")}"><small>${this.t("package_form.external_code_help")}</small></label>
      </div><div class="modal-actions"><button type="button" class="ghost" data-action="close-modal">${this.t("common.cancel")}</button><button class="primary" type="submit"><ha-icon icon="mdi:content-save-outline"></ha-icon>${this.t("package_form.save")}</button></div></form>
    </section></div>`;
  }

  unplannedModal() {
    const localNow = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    return `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${this.t("unplanned.dialog_label")}" data-modal-stop>
      <div class="modal-head"><div><p class="eyebrow">${this.t("unplanned.eyebrow")}</p><h2>${this.t("unplanned.title")}</h2></div><button class="ghost icon-only" data-action="close-modal" title="${this.t("common.cancel")}"><ha-icon icon="mdi:close"></ha-icon></button></div>
      <form data-form="unplanned"><div class="form-grid">
        ${this.field("taken_at", this.t("unplanned.taken_at"), localNow, true, "", "datetime-local")}
        <div class="field full"><span>${this.t("unplanned.medications")}</span><div class="item-editor">${this.doseRow({ medication_id: this.state.medications[0]?.id || "", dose: 1 }, 0)}</div><button type="button" class="text add-dose" data-action="add-dose"><ha-icon icon="mdi:plus"></ha-icon>${this.t("reg_form.add_medication")}</button></div>
      </div><div class="modal-actions"><button type="button" class="ghost" data-action="close-modal">${this.t("common.cancel")}</button><button class="primary" type="submit"><ha-icon icon="mdi:check"></ha-icon>${this.t("unplanned.save")}</button></div></form>
    </section></div>`;
  }

  codeModal(item) {
    return `<div class="modal-backdrop"><section class="modal code-modal" role="dialog" aria-modal="true" aria-label="${this.t("code.dialog_label")}" data-modal-stop>
      <div class="modal-head"><div><p class="eyebrow">${this.t("code.eyebrow")}</p><h2>${this.t("code.title", { object: this.t(`code.${item.kind}`) })}</h2></div><button class="ghost icon-only" data-action="close-modal" title="${this.t("common.cancel")}"><ha-icon icon="mdi:close"></ha-icon></button></div>
      <div class="code-content"><h3>${esc(item.label)}</h3><img src="${esc(item.dataUri)}" alt="${this.t("code.dialog_label")}"><p>${this.t("code.help")}</p><code>${esc(item.url)}</code><div class="modal-actions"><button class="ghost" data-action="copy-code" data-value="${esc(item.url)}"><ha-icon icon="mdi:content-copy"></ha-icon>${this.t("code.copy")}</button><button class="primary" data-action="close-modal">${this.t("common.close")}</button></div></div>
    </section></div>`;
  }

  regimenModal(item = {}) {
    const schedule = item.schedule || { type: "weekly", days: {0:["13:00"],1:["13:00"],2:["13:00"],3:["13:00"],4:["13:00"],5:["11:00"],6:["11:00"]} };
    const items = item.items?.length ? item.items : [{ medication_id: this.state.medications[0]?.id || "", dose: 1 }];
    const days = this.days();
    return `<div class="modal-backdrop"><section class="modal wide" role="dialog" aria-modal="true" aria-label="${this.t("reg_form.dialog_label")}" data-modal-stop>
      <div class="modal-head"><div><p class="eyebrow">${this.t("reg_form.eyebrow")}</p><h2>${this.t(item.id ? "reg_form.edit_title" : "reg_form.new_title")}</h2></div><button class="ghost icon-only" data-action="close-modal" title="${this.t("common.cancel")}"><ha-icon icon="mdi:close"></ha-icon></button></div>
      <form data-form="regimen"><input type="hidden" name="id" value="${esc(item.id || "")}"><div class="form-grid">
        ${this.field("name", this.t("reg_form.name"), item.name, true, this.t("reg_form.name_placeholder"))}<label class="field"><span>${this.t("reg_form.status")}</span><select name="active"><option value="true" ${item.active !== false ? "selected" : ""}>${this.t("common.active")}</option><option value="false" ${item.active === false ? "selected" : ""}>${this.t("common.paused")}</option></select></label>
        <div class="field full"><span>${this.t("reg_form.medications_dose")}</span><div class="item-editor">${items.map((dose, index) => this.doseRow(dose, index)).join("")}</div><button type="button" class="text add-dose" data-action="add-dose"><ha-icon icon="mdi:plus"></ha-icon>${this.t("reg_form.add_medication")}</button></div>
        <label class="field"><span>${this.t("reg_form.rhythm")}</span><select name="schedule_type"><option value="weekly" ${schedule.type === "weekly" ? "selected" : ""}>${this.t("reg_form.weekly")}</option><option value="interval" ${schedule.type === "interval" ? "selected" : ""}>${this.t("reg_form.interval")}</option></select></label>
        ${this.field("repeat_minutes", this.t("reg_form.repeat"), item.repeat_minutes ?? 30, true, "", "number", "5", "1")}
        <div class="field full schedule-weekly ${schedule.type === "weekly" ? "" : "hidden"}"><span>${this.t("reg_form.weekdays_times")}</span><div class="week-grid">${days.map((day, index) => { const times = schedule.type === "weekly" ? schedule.days?.[index] || schedule.days?.[String(index)] || [] : []; return `<label><input type="checkbox" name="day_${index}" ${times.length ? "checked" : ""}><b>${day}</b><input type="text" name="times_${index}" value="${esc(times.join(", ") || (index < 5 ? "13:00" : "11:00"))}" placeholder="13:00, 20:00"></label>`; }).join("")}</div><small>${this.t("reg_form.multiple_times_help")}</small></div>
        <div class="field full schedule-interval ${schedule.type === "interval" ? "" : "hidden"}"><span>${this.t("reg_form.interval_title")}</span><div class="inline-fields">${this.field("every_days", this.t("reg_form.every_days"), schedule.every_days || 2, true, "", "number", "1", "1")}${this.field("start_date", this.t("reg_form.start_date"), schedule.start_date || new Date().toISOString().slice(0,10), true, "", "date")}${this.field("interval_time", this.t("reg_form.time"), schedule.time || "13:00", true, "", "time")}</div></div>
        <label class="field full"><span>${this.t("reg_form.notify_services")}</span><input name="notify_services" list="notify-services" value="${esc((item.notify_services || []).join(", "))}" placeholder="${this.t("reg_form.notify_placeholder")}"><datalist id="notify-services">${this.state.notify_services.map((service) => `<option value="${esc(service)}"></option>`).join("")}</datalist><small>${this.t("reg_form.notify_help")}</small></label>
        <label class="field full"><span>${this.t("reg_form.scripts")}</span><input name="scripts" list="scripts" value="${esc((item.scripts || []).join(", "))}" placeholder="${this.t("reg_form.script_placeholder")}"><datalist id="scripts">${this.state.scripts.map((script) => `<option value="${esc(script)}"></option>`).join("")}</datalist></label>
        <label class="field full"><span>${this.t("reg_form.instructions")}</span><textarea name="instructions" rows="2" placeholder="${this.t("reg_form.instructions_placeholder")}">${esc(item.instructions || "")}</textarea></label>
      </div><div class="modal-actions"><button type="button" class="ghost" data-action="close-modal">${this.t("common.cancel")}</button><button class="primary" type="submit" ${this.state.medications.length ? "" : "disabled"}><ha-icon icon="mdi:content-save-outline"></ha-icon>${this.t("reg_form.save")}</button></div></form>
    </section></div>`;
  }

  doseRow(dose, index) {
    return `<div class="dose-row"><select name="medication_${index}" required><option value="">${this.t("reg_form.choose_medication")}</option>${this.state.medications.map((med) => `<option value="${med.id}" ${med.id === dose.medication_id ? "selected" : ""}>${esc(med.name)} (${esc(med.unit)})</option>`).join("")}</select><input name="dose_${index}" type="number" min="0.001" step="0.001" value="${dose.dose}" required><button type="button" class="ghost icon-only" data-action="remove-dose" title="${this.t("reg_form.remove")}"><ha-icon icon="mdi:close"></ha-icon></button></div>`;
  }

  field(name, label, value = "", required = false, placeholder = "", type = "text", min = "", step = "") {
    return `<label class="field"><span>${label}${required ? " *" : ""}</span><input name="${name}" type="${type}" value="${esc(value ?? "")}" placeholder="${esc(placeholder)}" ${required ? "required" : ""} ${min !== "" ? `min="${min}"` : ""} ${step ? `step="${step}"` : ""}></label>`;
  }

  renderToast() { return this.toast ? `<div class="toast ${this.toast.error ? "error" : ""}"><ha-icon icon="${this.toast.error ? "mdi:alert-circle-outline" : "mdi:check-circle-outline"}"></ha-icon>${esc(this.toast.message)}</div>` : ""; }

  async mutate(operation, success) {
    try {
      await operation();
      this.modal = null;
      await this.load(false);
      this.showToast(success);
    } catch (error) { this.showToast(this.errorText(error), true); }
  }

  async openCode(kind, id, label) {
    try {
      const url = this.scanUrl(kind, id);
      const result = await this.call("generate_qr", { value: url });
      this.modal = { type: "code", item: { kind, id, label, url, dataUri: result.data_uri } };
      this.render();
    } catch (error) { this.showToast(this.t("error.qr_failed"), true); }
  }

  async copyCode(value) {
    try {
      await navigator.clipboard.writeText(value);
      this.showToast(this.t("code.copied"));
    } catch (error) { this.showToast(this.t("error.qr_failed"), true); }
  }

  onClick(event) {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.tab) { this.activeTab = button.dataset.tab; this.render(); return; }
    const action = button.dataset.action;
    const id = button.dataset.id;
    if (action === "refresh") return this.load();
    if (action === "close-modal") { this.modal = null; this.render(); return; }
    if (action === "new-medication") { this.modal = { type: "medication", item: {} }; this.render(); return; }
    if (action === "edit-medication") { this.modal = { type: "medication", item: this.medication(id) }; this.render(); return; }
    if (action === "new-package") { this.modal = { type: "package", medicationId: id, item: {} }; this.render(); return; }
    if (action === "edit-package") { this.modal = { type: "package", item: this.package(id) }; this.render(); return; }
    if (action === "new-unplanned") {
      if (!this.state.medications.length) { this.showToast(this.t("error.create_medication_first"), true); this.modal = { type: "medication", item: {} }; this.render(); return; }
      this.modal = { type: "unplanned" }; this.render(); return;
    }
    if (action === "new-regimen") {
      if (!this.state.medications.length) { this.showToast(this.t("error.create_medication_first"), true); this.modal = { type: "medication", item: {} }; this.render(); return; }
      this.modal = { type: "regimen", item: {} }; this.render(); return;
    }
    if (action === "edit-regimen") { this.modal = { type: "regimen", item: this.regimen(id) }; this.render(); return; }
    if (action === "delete-medication" && confirm(this.t("confirm.delete_medication"))) return this.mutate(() => this.call("delete_medication", { medication_id: id }), this.t("action.medication_deleted"));
    if (action === "delete-regimen" && confirm(this.t("confirm.delete_regimen"))) return this.mutate(() => this.call("delete_regimen", { regimen_id: id }), this.t("action.regimen_deleted"));
    if (action === "delete-package" && confirm(this.t("confirm.delete_package"))) return this.mutate(() => this.call("delete_package", { package_id: id }), this.t("action.package_deleted"));
    if (action === "adjust-stock") {
      const value = prompt(this.t("prompt.stock"), "1");
      if (value !== null && Number.isFinite(Number(value)) && Number(value) !== 0) return this.mutate(() => this.call("adjust_stock", { medication_id: id, delta: Number(value) }), this.t("action.stock_updated"));
      return;
    }
    if (action === "take-selected") return this.takeSelected(id, button.closest(".ticket"));
    if (action === "snooze") return this.mutate(() => this.call("snooze", { occurrence_id: id, minutes: Number(button.dataset.minutes) }), this.t("action.reminder_snoozed"));
    if (action === "snooze-custom") {
      const input = this.shadowRoot.querySelector(`[data-snooze-time="${id}"]`);
      if (!input?.value) return this.showToast(this.t("error.select_time"), true);
      const until = new Date(input.value);
      if (until <= new Date()) return this.showToast(this.t("error.future_snooze"), true);
      return this.mutate(() => this.call("snooze", { occurrence_id: id, until: until.toISOString() }), this.t("action.reminder_snoozed_until"));
    }
    if (action === "skip" && confirm(this.t("confirm.skip"))) return this.mutate(() => this.call("skip", { occurrence_id: id }), this.t("action.intake_skipped"));
    if (action === "postpone-interval" && confirm(this.t("confirm.postpone_interval"))) return this.mutate(() => this.call("postpone_interval", { occurrence_id: id }), this.t("action.interval_postponed"));
    if (action === "show-code") return this.openCode(button.dataset.kind, id, button.dataset.label);
    if (action === "copy-code") return this.copyCode(button.dataset.value);
    if (action === "add-dose") { this.addDoseRow(button); return; }
    if (action === "remove-dose") { if (button.closest(".item-editor").children.length > 1) button.closest(".dose-row").remove(); return; }
  }

  takeSelected(id, ticket) {
    const doses = {};
    ticket.querySelectorAll("[data-medication]").forEach((checkbox) => {
      if (checkbox.checked) doses[checkbox.dataset.medication] = Number(ticket.querySelector(`[data-dose="${checkbox.dataset.medication}"]`).value);
    });
    if (!Object.values(doses).some((value) => value > 0)) return this.showToast(this.t("error.select_dose"), true);
    return this.mutate(() => this.call("record_intake", { occurrence_id: id, doses }), this.t("action.intake_recorded"));
  }

  addDoseRow(button) {
    const editor = button.parentElement.querySelector(".item-editor");
    const index = Math.max(0, ...[...editor.querySelectorAll("select")].map((el) => Number(el.name.split("_")[1]))) + 1;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = this.doseRow({ medication_id: "", dose: 1 }, index);
    editor.append(wrapper.firstElementChild);
  }

  onChange(event) {
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
      medication.stock = Number(medication.stock); medication.low_stock_threshold = Number(medication.low_stock_threshold);
      if (!medication.id) delete medication.id;
      return this.mutate(() => this.call("save_medication", { medication }), this.t("action.medication_saved"));
    }
    if (form.dataset.form === "package") {
      const packageData = Object.fromEntries(data.entries());
      if (packageData.id) packageData.remaining_quantity = Number(packageData.remaining_quantity);
      else { delete packageData.id; packageData.quantity = Number(packageData.quantity); }
      return this.mutate(() => this.call("save_package", { package: packageData }), this.t("action.package_saved"));
    }
    if (form.dataset.form === "unplanned") {
      const rows = [...form.querySelectorAll(".dose-row")];
      const items = rows.map((row) => ({ medication_id: row.querySelector("select").value, dose: Number(row.querySelector("input").value) }));
      if (new Set(items.map((item) => item.medication_id)).size !== items.length) return this.showToast(this.t("error.duplicate_medication"), true);
      const takenAt = new Date(data.get("taken_at"));
      if (takenAt > new Date()) return this.showToast(this.t("error.unplanned_future"), true);
      return this.mutate(() => this.call("record_unplanned_intake", { items, taken_at: takenAt.toISOString() }), this.t("action.unplanned_saved"));
    }
    if (form.dataset.form === "regimen") {
      try {
        const regimen = this.regimenFromForm(form, data);
        return this.mutate(() => this.call("save_regimen", { regimen }), this.t("action.regimen_saved"));
      } catch (error) { this.showToast(error.message, true); }
    }
  }

  regimenFromForm(form, data) {
    const rows = [...form.querySelectorAll(".dose-row")];
    const items = rows.map((row) => ({ medication_id: row.querySelector("select").value, dose: Number(row.querySelector("input").value) }));
    if (new Set(items.map((item) => item.medication_id)).size !== items.length) throw new Error(this.t("error.duplicate_medication"));
    let schedule;
    if (data.get("schedule_type") === "weekly") {
      const days = {};
      const dayNames = this.days();
      dayNames.forEach((_, index) => {
        if (!form.elements[`day_${index}`].checked) return;
        const times = form.elements[`times_${index}`].value.split(",").map((v) => v.trim()).filter(Boolean);
        if (!times.length || times.some((time) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))) throw new Error(this.t("error.invalid_time", { day: dayNames[index] }));
        days[index] = times;
      });
      if (!Object.keys(days).length) throw new Error(this.t("error.select_weekday"));
      schedule = { type: "weekly", days };
    } else schedule = { type: "interval", every_days: Number(data.get("every_days")), start_date: data.get("start_date"), time: data.get("interval_time") };
    const split = (name) => String(data.get(name) || "").split(",").map((v) => v.trim()).filter(Boolean);
    const regimen = { id: data.get("id") || undefined, name: data.get("name"), active: data.get("active") === "true", items, schedule,
      repeat_minutes: Number(data.get("repeat_minutes")), notify_services: split("notify_services"), scripts: split("scripts"), instructions: data.get("instructions") };
    if (!regimen.id) delete regimen.id;
    return regimen;
  }

  styles() { return `
    :host { --ink: var(--primary-text-color, #17211f); --muted: var(--secondary-text-color, #687572); --surface: var(--card-background-color, #fff); --line: color-mix(in srgb, var(--ink) 12%, transparent); display:block; min-height:100vh; color:var(--ink); background:var(--primary-background-color, #f4f7f5); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif; }
    * { box-sizing:border-box; } button,input,select,textarea { font:inherit; } button { cursor:pointer; } .app { min-height:100vh; background:radial-gradient(circle at 75% -20%, color-mix(in srgb, var(--primary-color, #0b8f72) 16%, transparent), transparent 35%); }
    header { height:84px; padding:0 clamp(20px,4vw,64px); display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); background:color-mix(in srgb, var(--surface) 88%, transparent); backdrop-filter:blur(18px); position:sticky; top:0; z-index:8; }
    .brand,.header-actions,.ticket-actions,.card-actions,.regimen-title,.page-title,.section-heading,.modal-head,.modal-actions { display:flex; align-items:center; } .brand { gap:14px; } .brand-icon { width:48px;height:48px;display:grid;place-items:center;filter:drop-shadow(0 7px 10px #0b8f7238); } .brand-icon img{display:block;width:48px;height:48px;object-fit:contain}.brand span,.eyebrow{font-size:10px;letter-spacing:.16em;font-weight:800;color:var(--primary-color,#07856c);margin:0 0 4px}.brand h1{font-size:20px;line-height:1;margin:0;letter-spacing:-.02em}.header-actions{gap:10px}
    nav { display:flex; gap:6px; padding:14px clamp(20px,4vw,64px) 0; max-width:1440px; margin:auto; overflow:auto; } nav button { display:flex;align-items:center;gap:8px;padding:11px 16px;border:0;border-radius:12px;background:transparent;color:var(--muted);font-weight:650;white-space:nowrap } nav button.active { background:var(--surface);color:var(--primary-color,#07856c);box-shadow:0 2px 12px #0000000b } nav ha-icon{--mdc-icon-size:20px}
    main { max-width:1440px; margin:auto; padding:28px clamp(20px,4vw,64px) 48px; } .hero { min-height:190px;border-radius:26px;padding:34px 38px;display:flex;align-items:center;justify-content:space-between;color:#fff;background:linear-gradient(118deg,#075f54,#07856c 55%,#17aa82);position:relative;overflow:hidden;box-shadow:0 18px 45px #08745f36 } .hero:after{content:"";position:absolute;width:340px;height:340px;border:1px solid #ffffff26;border-radius:50%;right:-80px;top:-190px;box-shadow:0 0 0 55px #ffffff0b,0 0 0 110px #ffffff08}.hero .eyebrow{color:#c8fff0}.hero h2{font-size:34px;letter-spacing:-.04em;margin:6px 0}.hero p:last-child{opacity:.82;margin:0}.hero-orb{width:90px;height:90px;border-radius:28px;background:#ffffff1c;display:grid;place-items:center;z-index:1;border:1px solid #ffffff2e}.hero-orb ha-icon{--mdc-icon-size:48px}
    .stats { display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0 38px}.stat{background:var(--surface);padding:20px;border-radius:18px;display:flex;gap:14px;align-items:center;border:1px solid var(--line);box-shadow:0 6px 24px #122b2410;min-width:0}.stat-icon{width:46px;height:46px;flex:0 0 46px;border-radius:14px;display:grid;place-items:center}.stat-icon.mint{background:#d9f8ee;color:#07856c}.stat-icon.amber{background:#fff1ce;color:#a96500}.stat-icon.red{background:#ffe1df;color:#c63f3a}.stat-icon.blue{background:#e1edff;color:#336ccc}.stat-icon.violet{background:#eee5ff;color:#7752bd}.stat div:last-child{min-width:0}.stat span,.stat small{display:block;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stat span{font-size:12px;font-weight:650}.stat strong{font-size:22px;display:block;margin:2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stat small{font-size:11px}
    .section-heading,.page-title{justify-content:space-between;gap:20px;margin:30px 0 16px}.section-heading h2,.page-title h2{font-size:25px;letter-spacing:-.03em;margin:2px 0}.page-title{margin-top:4px;align-items:flex-end}.page-title p:last-child{color:var(--muted);margin:4px 0 0}.ticket-list{display:grid;gap:16px}.ticket{display:grid;grid-template-columns:64px 1fr;background:var(--surface);border:1px solid var(--line);border-radius:20px;overflow:hidden;box-shadow:0 8px 28px #142f2810}.ticket-side{background:#e4faf3;color:#07856c;display:flex;justify-content:center;padding-top:28px}.ticket-side.snoozed{background:#eee9fa;color:#7558ae}.ticket-side ha-icon{--mdc-icon-size:27px}.ticket-body{padding:24px}.ticket-head{display:flex;justify-content:space-between;gap:16px}.ticket-head h3{font-size:21px;margin:7px 0 3px}.ticket-head p{color:var(--muted);margin:0;font-size:13px}.ticket-head .time{font-size:25px;color:var(--primary-color,#07856c)}.badge{display:inline-flex;padding:4px 9px;border-radius:99px;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}.badge.pending,.badge.warning{background:#fff0c7;color:#946000}.badge.partial{background:#e9e0ff;color:#6948a5}.badge.taken,.badge.ok{background:#d9f8ee;color:#08725e}.badge.skipped{background:#f0f1f1;color:#69716f}.badge.muted{background:#eceeee;color:#747b79}.instructions{padding:10px 12px;background:color-mix(in srgb,var(--primary-color,#07856c) 7%,transparent);border-radius:10px;color:var(--muted);font-size:13px;display:flex;gap:8px;align-items:center}.instructions ha-icon{--mdc-icon-size:18px}.dose-list{margin:18px 0 20px;border:1px solid var(--line);border-radius:14px;overflow:hidden}.dose{display:grid;grid-template-columns:auto auto 1fr auto;align-items:center;gap:12px;padding:13px 15px;border-bottom:1px solid var(--line)}.dose:last-child{border:0}.dose.done{opacity:.55}.dose>input{width:17px;height:17px;accent-color:var(--primary-color,#07856c)}.pill-dot{width:28px;height:28px;border-radius:9px;background:#e4faf3;position:relative}.pill-dot:after{content:"";position:absolute;width:14px;height:7px;border-radius:8px;background:#0b9878;transform:rotate(-35deg);top:10px;left:7px}.dose-name strong,.dose-name small,.dose-amount small{display:block}.dose-name small,.dose-amount small{color:var(--muted);font-size:11px}.dose-amount{text-align:right;font-weight:700}.dose-amount input{width:70px;padding:7px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);text-align:right}.ticket-actions{gap:8px;flex-wrap:wrap}.snooze{display:flex;gap:5px}.custom-time{padding:9px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink)}
    button.primary,button.ghost,button.text{border-radius:11px;padding:10px 14px;display:inline-flex;gap:8px;align-items:center;justify-content:center;font-weight:700;border:0}button.primary{background:var(--primary-color,#07856c);color:#fff;box-shadow:0 5px 14px color-mix(in srgb,var(--primary-color,#07856c) 24%,transparent)}button.primary:hover{filter:brightness(1.06)}button.primary:disabled{opacity:.45;cursor:not-allowed}button.ghost{background:var(--surface);color:var(--ink);border:1px solid var(--line)}button.text{background:transparent;color:var(--primary-color,#07856c);padding:8px}.icon-only{width:42px;height:42px;padding:0!important}.danger-text{color:#c04440!important}
    .stock-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.stock-grid.large{grid-template-columns:repeat(3,1fr)}.stock-card{background:var(--surface);border:1px solid var(--line);border-radius:19px;padding:20px;box-shadow:0 6px 24px #122b240c}.stock-card.is-low{border-color:#e5a19c}.stock-top{display:flex;justify-content:space-between}.medicine-icon{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;background:#e3f8f1;color:#087d68}.stock-card h3{font-size:18px;margin:16px 0 3px}.stock-card>p{color:var(--muted);font-size:12px;min-height:18px;margin:0}.stock-value{display:flex;align-items:baseline;gap:6px;margin-top:18px}.stock-value strong{font-size:32px;letter-spacing:-.04em}.stock-value span{color:var(--muted)}.progress{height:6px;border-radius:9px;background:var(--line);margin:10px 0 7px;overflow:hidden}.progress i{display:block;height:100%;background:linear-gradient(90deg,#07856c,#36c79e);border-radius:9px}.is-low .progress i{background:#d95750}.stock-card>small{color:var(--muted)}.card-actions{gap:6px;margin-top:18px;padding-top:14px;border-top:1px solid var(--line);flex-wrap:wrap}.package-section{margin-top:18px;padding-top:15px;border-top:1px solid var(--line);display:grid;gap:8px}.package-heading{display:flex;align-items:center;justify-content:space-between;font-size:12px}.package-heading span{color:var(--muted)}.package-section>small,.next-package{color:var(--muted);font-size:11px}.next-package{margin:10px 0 0!important}.package-row{display:grid;grid-template-columns:34px 1fr auto;gap:9px;align-items:center;padding:9px;border:1px solid var(--line);border-radius:12px}.package-row.empty-package{opacity:.55}.package-mark{width:32px;height:32px;border-radius:9px;background:#eef7f4;color:#07856c;display:grid;place-items:center}.package-mark ha-icon{--mdc-icon-size:18px}.package-row strong,.package-row small{display:block}.package-row strong{font-size:12px}.package-row small{font-size:10px;color:var(--muted);margin-top:2px}.package-actions{display:flex}.package-actions .icon-only{width:32px;height:32px}.highlight{outline:3px solid color-mix(in srgb,var(--primary-color,#07856c) 42%,transparent);outline-offset:2px}.pack-plan{color:#087d68!important;margin-top:4px}.history-packages{display:block;color:var(--muted);font-size:10px;margin-top:3px}
    .regimen-list{display:grid;gap:13px}.regimen-card{display:grid;grid-template-columns:54px 1fr auto;gap:17px;align-items:start;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:20px}.regimen-card.inactive{opacity:.65}.regimen-icon{width:52px;height:52px;border-radius:16px;background:#e3f8f1;color:#07856c;display:grid;place-items:center}.regimen-icon ha-icon{--mdc-icon-size:27px}.regimen-title{gap:10px}.regimen-title h3{margin:0;font-size:19px}.schedule{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:13px;margin:8px 0}.schedule ha-icon{--mdc-icon-size:17px}.chips{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}.chips span{padding:5px 9px;border-radius:8px;background:color-mix(in srgb,var(--primary-color,#07856c) 8%,transparent);font-size:12px}.regimen-main>small{color:var(--muted)}.vertical-actions{display:flex;gap:6px}
    .table-wrap{overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:18px}table{border-collapse:collapse;width:100%;min-width:900px}th,td{text-align:left;padding:15px;border-bottom:1px solid var(--line);font-size:13px}th{font-size:10px;letter-spacing:.1em;color:var(--muted);text-transform:uppercase;background:color-mix(in srgb,var(--surface) 88%,var(--ink) 2%)}tbody tr:last-child td{border:0}.empty{grid-column:1/-1;text-align:center;padding:52px 20px;background:var(--surface);border:1px dashed var(--line);border-radius:19px}.empty ha-icon{--mdc-icon-size:42px;color:var(--primary-color,#07856c)}.empty h3{margin:12px 0 4px}.empty p{color:var(--muted);margin:0}
    .modal-backdrop{position:fixed;inset:0;z-index:30;background:#0a1613a3;backdrop-filter:blur(7px);display:grid;place-items:center;padding:20px}.modal{width:min(680px,100%);max-height:92vh;overflow:auto;background:var(--surface);border-radius:23px;box-shadow:0 30px 80px #0006}.modal.wide{width:min(920px,100%)}.modal-head{justify-content:space-between;padding:23px 26px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--surface);z-index:1}.modal-head h2{margin:2px 0;font-size:23px}.modal form{padding:24px 26px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:17px}.field{display:flex;flex-direction:column;gap:7px}.field.full{grid-column:1/-1}.field>span{font-size:12px;font-weight:750}.field small{color:var(--muted);line-height:1.35}.field input,.field select,.field textarea,.dose-row input,.dose-row select{width:100%;border:1px solid var(--line);border-radius:10px;padding:11px 12px;background:var(--surface);color:var(--ink);outline:none}.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--primary-color,#07856c);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary-color,#07856c) 12%,transparent)}.modal-actions{justify-content:flex-end;gap:9px;margin-top:26px}.item-editor{display:grid;gap:8px}.dose-row{display:grid;grid-template-columns:2fr 1fr auto;gap:8px}.add-dose{align-self:flex-start;margin-top:6px}.week-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.week-grid label{display:grid;grid-template-columns:auto 1fr 1.3fr;gap:8px;align-items:center;border:1px solid var(--line);padding:8px;border-radius:10px}.week-grid label>input:first-child{width:17px}.week-grid b{font-size:12px}.week-grid input[type=text]{padding:7px}.inline-fields{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.code-content{padding:25px;text-align:center}.code-content h3{margin:0 0 14px}.code-content img{display:block;width:min(340px,90%);aspect-ratio:1;margin:auto;border-radius:16px;background:#fff;padding:10px}.code-content p{color:var(--muted);font-size:13px;line-height:1.5}.code-content code{display:block;padding:10px;border-radius:10px;background:color-mix(in srgb,var(--ink) 5%,transparent);overflow-wrap:anywhere;text-align:left;font-size:11px}.hidden{display:none!important}.toast{position:fixed;z-index:50;right:24px;bottom:24px;max-width:420px;padding:14px 17px;border-radius:13px;background:#063f35;color:#fff;display:flex;gap:10px;align-items:center;box-shadow:0 14px 40px #0004;animation:toast-in .22s ease}.toast.error{background:#9d302c}@keyframes toast-in{from{transform:translateY(14px);opacity:0}}.loading{min-height:100vh;display:grid;place-content:center;text-align:center;padding:20px}.loading p{color:var(--muted)}.loader{width:44px;height:44px;border:4px solid var(--line);border-top-color:var(--primary-color,#07856c);border-radius:50%;animation:spin .8s linear infinite;margin:auto}@keyframes spin{to{transform:rotate(360deg)}}footer{max-width:1440px;margin:auto;padding:18px clamp(20px,4vw,64px) 30px;border-top:1px solid var(--line);display:flex;justify-content:space-between;color:var(--muted);font-size:11px}.live{display:inline-block;width:7px;height:7px;background:#15af81;border-radius:50%;margin-right:6px}
    @media(max-width:1050px){.stats{grid-template-columns:repeat(2,1fr)}.stock-grid,.stock-grid.large{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:700px){header{height:72px;padding:0 16px}.brand span{display:none}.brand h1{font-size:17px}.header-actions button span{display:none}nav{padding:10px 14px 0}nav button{padding:10px 12px;font-size:12px}main{padding:18px 14px 36px}.hero{padding:27px 23px;min-height:165px}.hero h2{font-size:27px}.hero-orb{width:64px;height:64px}.hero-orb ha-icon{--mdc-icon-size:34px}.stats{grid-template-columns:1fr 1fr;gap:9px}.stat{padding:14px;gap:9px}.stat-icon{width:38px;height:38px;flex-basis:38px}.stat strong{font-size:18px}.ticket{grid-template-columns:1fr}.ticket-side{display:none}.ticket-body{padding:18px}.ticket-head .time{font-size:20px}.dose{grid-template-columns:auto auto 1fr}.dose-amount{grid-column:3}.ticket-actions>.primary{width:100%}.custom-time{max-width:185px}.stock-grid,.stock-grid.large{grid-template-columns:1fr}.page-title{align-items:flex-start;flex-direction:column}.regimen-card{grid-template-columns:44px 1fr}.vertical-actions{grid-column:2}.form-grid{grid-template-columns:1fr}.field.full{grid-column:auto}.week-grid{grid-template-columns:1fr}.inline-fields{grid-template-columns:1fr}.modal-backdrop{padding:0}.modal{max-height:100vh;height:100%;border-radius:0}.modal-head{padding:18px}.modal form{padding:18px}.package-row{grid-template-columns:30px 1fr}.package-actions{grid-column:2}footer{flex-direction:column;gap:5px}}
  `; }
}

if (!customElements.get("medication-reminder-panel")) customElements.define("medication-reminder-panel", MedicationReminderPanel);
