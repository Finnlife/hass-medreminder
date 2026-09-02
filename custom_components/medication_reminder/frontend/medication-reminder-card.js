/**
 * Lovelace card for Medication Reminder.
 *
 * The card talks to the integration's own WebSocket API instead of reading
 * entity attributes, so it can show per-package dose plans and record partial
 * intakes the same way the panel does.
 */
import { createTranslator, resolveLanguage } from "./localize.js";

const CARD_TYPE = "medication-reminder-card";
const EDITOR_TYPE = `${CARD_TYPE}-editor`;
const OPEN_STATUSES = ["pending", "partial"];
const POLL_INTERVAL = 15000;
const DOMAIN_EVENTS = [
  "medication_reminder_taken",
  "medication_reminder_skipped",
  "medication_reminder_missed",
  "medication_reminder_due",
  "medication_reminder_postponed",
];

const DEFAULTS = Object.freeze({
  mode: "due",
  max: 5,
  allow_partial: true,
  show_snooze: true,
  show_skip: true,
  show_upcoming: true,
  upcoming_count: 3,
  show_stock: false,
  stock_filter: "low",
});

const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

const CARD_STYLES = `
:host { display: block; }
ha-card {
  --mr-muted: var(--secondary-text-color, #727272);
  --mr-line: var(--divider-color, rgba(127, 127, 127, .25));
  --mr-accent: var(--primary-color, #03a9f4);
  --mr-danger: var(--error-color, #db4437);
  --mr-warn: var(--warning-color, #ffa600);
  --mr-ok: var(--success-color, #43a047);
  --mr-info: var(--info-color, #039be5);
  overflow: hidden;
}
* { box-sizing: border-box; }
button, input { font: inherit; color: inherit; }
button { cursor: pointer; }
.header {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 14px 16px 0;
}
.header h2 {
  margin: 0; font-size: var(--ha-card-header-font-size, 20px);
  font-weight: var(--ha-card-header-font-weight, 400);
  color: var(--ha-card-header-color, var(--primary-text-color));
}
.header .count {
  font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: 999px;
  background: var(--mr-accent); color: var(--text-primary-color, #fff);
}
.content { padding: 12px 16px 16px; display: grid; gap: 10px; }
.muted { color: var(--mr-muted); }
.empty { display: flex; align-items: center; gap: 10px; color: var(--mr-muted); padding: 4px 0 6px; }
.empty ha-icon { --mdc-icon-size: 22px; color: var(--mr-ok); }

.intake { border: 1px solid var(--mr-line); border-radius: 10px; padding: 10px 12px; }
.intake-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.intake-head strong { font-weight: 500; }
.intake-head .when { font-size: 12px; color: var(--mr-muted); white-space: nowrap; }
.chips { display: flex; gap: 5px; flex-wrap: wrap; align-items: center; }
.badge {
  display: inline-flex; padding: 1px 7px; border-radius: 999px;
  font-size: 11px; font-weight: 600;
}
.badge.pending { background: color-mix(in srgb, var(--mr-warn) 18%, transparent); color: var(--mr-warn); }
.badge.partial { background: color-mix(in srgb, var(--mr-info) 18%, transparent); color: var(--mr-info); }
.badge.snoozed { background: color-mix(in srgb, var(--mr-info) 14%, transparent); color: var(--mr-info); }
.badge.overdue { background: color-mix(in srgb, var(--mr-danger) 16%, transparent); color: var(--mr-danger); }

.reason { font-size: 12px; color: var(--mr-muted); margin-top: 6px; }
.doses { display: grid; gap: 4px; margin: 8px 0; }
.dose { display: flex; align-items: center; gap: 10px; }
.dose input[type=checkbox] { width: 17px; height: 17px; accent-color: var(--mr-accent); flex: 0 0 auto; }
.dose-main { flex: 1; min-width: 0; display: grid; }
.dose-main span { font-size: 14px; }
.dose-main small { font-size: 11px; color: var(--mr-accent); }
.dose-amount { display: flex; align-items: center; gap: 5px; font-size: 13px; white-space: nowrap; }
.dose-amount input {
  width: 66px; text-align: right; padding: 5px 7px; border-radius: 6px;
  border: 1px solid var(--mr-line); background: var(--card-background-color, #fff);
}
.dose-amount .fixed { font-variant-numeric: tabular-nums; }

.actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
button.record {
  display: inline-flex; align-items: center; gap: 6px; border: 0; border-radius: 8px;
  padding: 7px 12px; font-weight: 500;
  background: var(--mr-accent); color: var(--text-primary-color, #fff);
}
button.record:hover { filter: brightness(1.08); }
button.chip {
  padding: 4px 9px; border-radius: 999px; border: 1px solid var(--mr-line);
  background: transparent; font-size: 12px; color: var(--mr-muted);
}
button.chip:hover { background: color-mix(in srgb, currentColor 10%, transparent); }
button.chip.skip { color: var(--mr-danger); border-color: color-mix(in srgb, var(--mr-danger) 35%, var(--mr-line)); }
.spacer { flex: 1; }

.section-title {
  font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--mr-muted); font-weight: 600; margin-top: 4px;
}
.line { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.line .grow { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.line .value { color: var(--mr-muted); white-space: nowrap; }
.line.low .value { color: var(--mr-warn); font-weight: 500; }
.bar { height: 4px; border-radius: 999px; background: var(--mr-line); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--mr-accent); }
.bar.low i { background: var(--mr-warn); }
.more { font-size: 12px; color: var(--mr-muted); }
.error { color: var(--mr-danger); font-size: 13px; }
a.panel-link { color: var(--mr-accent); text-decoration: none; font-size: 13px; }
`;

class MedicationReminderCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.config = { ...DEFAULTS };
    this.state = null;
    this.error = null;
    this.loading = false;
    this.language = "en";
    this.locale = "en-US";
    this.t = createTranslator("en");
    this._signature = null;
    this.shadowRoot.addEventListener("click", (event) => this.onClick(event));
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig() {
    return { type: `custom:${CARD_TYPE}`, ...DEFAULTS };
  }

  setConfig(config) {
    const merged = { ...DEFAULTS, ...(config || {}) };
    if (!["due", "open"].includes(merged.mode)) merged.mode = DEFAULTS.mode;
    if (!["all", "low"].includes(merged.stock_filter)) merged.stock_filter = DEFAULTS.stock_filter;
    merged.max = Math.max(1, Math.min(20, Number(merged.max) || DEFAULTS.max));
    merged.upcoming_count = Math.max(
      1, Math.min(10, Number(merged.upcoming_count) || DEFAULTS.upcoming_count));
    this.config = merged;
    this._signature = null;
    if (this.state) this.render();
  }

  set hass(hass) {
    this._hass = hass;
    const language = resolveLanguage(hass);
    if (language !== this.language) {
      this.language = language;
      this.locale = language === "de" ? "de-DE" : "en-US";
      this.t = createTranslator(language);
      this._signature = null;
      this.render();
    }
    if (!this.state && !this.loading) this.load();
  }

  get hass() { return this._hass; }

  getCardSize() {
    const rows = this.state ? Math.min(this.config.max, this.visibleIntakes().length) : 1;
    return 1 + Math.max(1, rows * 2);
  }

  connectedCallback() {
    this.render();
    // `hass` is often assigned before the card enters the document, and a load
    // started back then would have been dropped, so always load on connect.
    this.load();
    this.poller = window.setInterval(() => this.load(), POLL_INTERVAL);
    this.subscribe();
  }

  disconnectedCallback() {
    window.clearInterval(this.poller);
    this.unsubscribe();
  }

  async subscribe() {
    if (!this.hass?.connection || this._unsubscribers) return;
    try {
      this._unsubscribers = await Promise.all(DOMAIN_EVENTS.map((event) =>
        this.hass.connection.subscribeEvents(() => this.load(), event)));
    } catch (error) {
      // Polling still keeps the card up to date without an event subscription.
      this._unsubscribers = null;
    }
  }

  unsubscribe() {
    (this._unsubscribers || []).forEach((unsubscribe) => {
      try {
        unsubscribe();
      } catch (error) {
        /* the connection is already gone */
      }
    });
    this._unsubscribers = null;
  }

  async call(type, payload = {}) {
    if (!this.hass) throw new Error("Home Assistant is not connected yet.");
    return this.hass.connection.sendMessagePromise({
      type: `medication_reminder/${type}`, ...payload,
    });
  }

  async load() {
    if (this.loading || !this.hass || !this.isConnected) return;
    this.loading = true;
    try {
      this.state = await this.call("get_state");
      this.error = null;
    } catch (error) {
      this.error = this.errorText(error);
    } finally {
      this.loading = false;
      this.render();
    }
  }

  errorText(error) {
    const message = error?.body?.message || error?.message || "";
    if (message === "Medication Reminder is not configured") {
      return this.t("card.not_configured");
    }
    if (message.startsWith("Not enough stock for ")) {
      return this.t("error.not_enough_stock", { medication: message.slice(21) });
    }
    const known = {
      "Taken dose exceeds the remaining planned dose": "error.dose_exceeds",
      "No dose was selected": "error.no_dose",
      "Only open intakes can be snoozed": "error.only_open_snooze",
      "Snooze time must be in the future": "error.future_snooze",
    };
    return known[message] ? this.t(known[message]) : message || this.t("error.generic");
  }

  // ------------------------------------------------------------------ helpers

  medication(id) { return this.state?.medications.find((item) => item.id === id); }
  regimen(id) { return this.state?.regimens.find((item) => item.id === id); }

  isDue(item) {
    if (new Date(item.scheduled_at) > new Date()) return false;
    return !item.snoozed_until || new Date(item.snoozed_until) <= new Date();
  }

  openIntakes() {
    return (this.state?.occurrences || [])
      .filter((item) => OPEN_STATUSES.includes(item.status))
      .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
  }

  visibleIntakes() {
    const open = this.openIntakes();
    return this.config.mode === "due" ? open.filter((item) => this.isDue(item)) : open;
  }

  formatNumber(value) {
    return new Intl.NumberFormat(this.locale, { maximumFractionDigits: 3 }).format(value ?? 0);
  }

  formatTime(value) {
    return new Intl.DateTimeFormat(this.locale, { hour: "2-digit", minute: "2-digit" })
      .format(new Date(value));
  }

  formatDateTime(value) {
    return new Intl.DateTimeFormat(this.locale, {
      weekday: "short", hour: "2-digit", minute: "2-digit",
    }).format(new Date(value));
  }

  relative(value) {
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

  /** Skip a re-render while a dose amount is being typed into. */
  hasFocusedInput() {
    const active = this.shadowRoot.activeElement;
    return Boolean(active && active.matches("input"));
  }

  signature() {
    const intakes = this.visibleIntakes().slice(0, this.config.max).map((item) =>
      [item.id, item.status, item.snoozed_until, item.items.map((dose) => dose.taken_dose).join(",")].join("|"));
    const stock = (this.state?.medications || []).map((item) => `${item.id}:${item.stock}`);
    const upcoming = (this.state?.upcoming || []).slice(0, this.config.upcoming_count)
      .map((item) => item.scheduled_at);
    return JSON.stringify([this.language, this.error, intakes, stock, upcoming, this.config]);
  }

  // ---------------------------------------------------------------- rendering

  render() {
    if (this.hasFocusedInput()) return;
    const signature = this.signature();
    if (signature === this._signature && this.shadowRoot.querySelector("ha-card")) return;
    this._signature = signature;
    this.shadowRoot.innerHTML = `<style>${CARD_STYLES}</style>${this.renderCard()}`;
  }

  renderCard() {
    const title = this.config.title === undefined
      ? this.t("card.title_default") : this.config.title;
    const intakes = this.visibleIntakes();
    const shown = intakes.slice(0, this.config.max);
    const hidden = intakes.length - shown.length;
    return `<ha-card>
      ${title ? `<div class="header"><h2>${esc(title)}</h2>
        ${intakes.length ? `<span class="count">${intakes.length}</span>` : ""}</div>` : ""}
      <div class="content">
        ${this.error ? `<div class="error">${esc(this.error)}</div>` : ""}
        ${!this.state && !this.error ? `<div class="muted">${this.t("card.loading")}</div>` : ""}
        ${this.state && !this.error ? `
          ${shown.length
            ? shown.map((item) => this.renderIntake(item)).join("")
            : `<div class="empty"><ha-icon icon="mdi:check-circle-outline"></ha-icon>
                <span>${this.t(this.config.mode === "due" ? "card.nothing_due" : "card.nothing_open")}</span></div>`}
          ${hidden > 0 ? `<div class="more">${this.t("card.more_open", { count: hidden })}</div>` : ""}
          ${this.renderUpcoming()}
          ${this.renderStock()}
          <a class="panel-link" href="/medication_reminder">${this.t("card.open_panel")}</a>
        ` : ""}
      </div>
    </ha-card>`;
  }

  renderIntake(item) {
    const regimen = this.regimen(item.regimen_id);
    const name = item.unplanned
      ? this.t("ticket.unplanned")
      : regimen?.name || item.regimen_name || this.t("ticket.orphan_plan");
    const snoozed = item.snoozed_until && new Date(item.snoozed_until) > new Date();
    const overdue = this.isDue(item) && Date.now() - new Date(item.scheduled_at) > 3600000;
    return `<div class="intake" data-intake="${item.id}">
      <div class="intake-head">
        <div>
          <div class="chips">
            <span class="badge ${item.status}">${this.t(`status.${item.status}`)}</span>
            ${item.ad_hoc ? `<span class="badge partial">${this.t("ticket.ad_hoc")}</span>` : ""}
            ${overdue ? `<span class="badge overdue">${this.t("ticket.overdue")}</span>` : ""}
            ${snoozed ? `<span class="badge snoozed">${this.t("ticket.snoozed_until", { time: this.formatTime(item.snoozed_until) })}</span>` : ""}
          </div>
          <strong>${esc(name)}</strong>
        </div>
        <span class="when">${this.formatTime(item.scheduled_at)} · ${this.relative(item.scheduled_at)}</span>
      </div>
      ${item.reason ? `<div class="reason">${this.t("ticket.reason", { reason: esc(item.reason) })}</div>` : ""}
      <div class="doses">${item.items.map((dose) => this.renderDose(dose)).join("")}</div>
      <div class="actions">
        <button class="record" data-action="record" data-id="${item.id}">
          <ha-icon icon="mdi:check"></ha-icon>${this.t("card.record")}
        </button>
        ${this.config.show_snooze ? `
          <button class="chip" data-action="snooze" data-id="${item.id}" data-minutes="30">${this.t("ticket.snooze_30")}</button>
          <button class="chip" data-action="snooze" data-id="${item.id}" data-minutes="60">${this.t("ticket.snooze_60")}</button>
          <button class="chip" data-action="snooze" data-id="${item.id}" data-minutes="120">${this.t("ticket.snooze_120")}</button>` : ""}
        <div class="spacer"></div>
        ${this.config.show_skip
          ? `<button class="chip skip" data-action="skip" data-id="${item.id}">${this.t("ticket.skip")}</button>`
          : ""}
      </div>
    </div>`;
  }

  renderDose(dose) {
    const med = this.medication(dose.medication_id);
    const remaining = Math.round((dose.planned_dose - dose.taken_dose) * 1000) / 1000;
    const unit = esc(med?.unit || "");
    const plan = dose.package_plan?.length
      ? dose.package_plan.map((part) => part.nickname).join(" + ") : "";
    return `<label class="dose">
      <input type="checkbox" data-medication="${dose.medication_id}" ${remaining > 0 ? "checked" : "disabled"}>
      <span class="dose-main">
        <span>${esc(med?.name || this.t("ticket.deleted_medication"))}</span>
        ${plan ? `<small>${this.t("ticket.take_from", { packages: esc(plan) })}</small>` : ""}
      </span>
      <span class="dose-amount">
        ${this.config.allow_partial
          ? `<input type="number" data-dose="${dose.medication_id}" min="0" max="${remaining}"
              step="0.001" value="${remaining}" ${remaining > 0 ? "" : "disabled"}>`
          : `<b class="fixed" data-dose="${dose.medication_id}" data-value="${remaining}">${this.formatNumber(remaining)}</b>`}
        <small class="muted">${unit}</small>
      </span>
    </label>`;
  }

  renderUpcoming() {
    if (!this.config.show_upcoming) return "";
    const upcoming = (this.state.upcoming || []).slice(0, this.config.upcoming_count);
    if (!upcoming.length) return "";
    return `<div class="section-title">${this.t("card.upcoming")}</div>
      ${upcoming.map((entry) => `<div class="line">
        <span class="grow">${esc(entry.regimen_name)}</span>
        <span class="value">${this.formatDateTime(entry.scheduled_at)}</span>
      </div>`).join("")}`;
  }

  renderStock() {
    if (!this.config.show_stock) return "";
    const medications = (this.state.medications || [])
      .filter((item) => this.config.stock_filter === "all" || item.stock <= item.low_stock_threshold);
    if (!medications.length) return "";
    return `<div class="section-title">${this.t("card.stock")}</div>
      ${medications.map((item) => {
        const low = item.stock <= item.low_stock_threshold;
        const reference = Math.max(item.low_stock_threshold * 3, item.stock, 1);
        const percentage = Math.min(100, (item.stock / reference) * 100);
        const supply = item.days_of_supply === null || item.days_of_supply === undefined
          ? "" : ` · ${this.t("stock.supply", { days: this.formatNumber(item.days_of_supply) })}`;
        return `<div>
          <div class="line ${low ? "low" : ""}">
            <span class="grow">${esc(item.name)}</span>
            <span class="value">${this.formatNumber(item.stock)} ${esc(item.unit)}${supply}</span>
          </div>
          <div class="bar ${low ? "low" : ""}"><i style="width:${percentage}%"></i></div>
        </div>`;
      }).join("")}`;
  }

  // ------------------------------------------------------------------ actions

  onClick(event) {
    const button = event.target.closest("button");
    if (!button) return;
    const id = button.dataset.id;
    const action = button.dataset.action;
    if (action === "record") return this.record(id, button.closest(".intake"));
    if (action === "snooze") {
      return this.run(this.call("snooze", {
        occurrence_id: id, minutes: Number(button.dataset.minutes),
      }));
    }
    if (action === "skip") return this.run(this.call("skip", { occurrence_id: id }));
  }

  record(id, container) {
    const doses = {};
    container.querySelectorAll("[data-medication]").forEach((checkbox) => {
      if (!checkbox.checked) return;
      const field = container.querySelector(`[data-dose="${checkbox.dataset.medication}"]`);
      const amount = Number(field?.value ?? field?.dataset.value ?? 0);
      if (Number.isFinite(amount) && amount > 0) doses[checkbox.dataset.medication] = amount;
    });
    if (!Object.keys(doses).length) {
      this.error = this.t("error.select_dose");
      this._signature = null;
      return this.render();
    }
    return this.run(this.call("record_intake", { occurrence_id: id, doses }));
  }

  async run(operation) {
    try {
      await operation;
      this.error = null;
    } catch (error) {
      this.error = this.errorText(error);
    }
    this._signature = null;
    await this.load();
  }
}

const EDITOR_FIELDS = [
  ["title", { text: {} }],
  ["mode", { select: { mode: "dropdown", options: [
    { value: "due", labelKey: "card.editor.mode_due" },
    { value: "open", labelKey: "card.editor.mode_open" },
  ] } }],
  ["max", { number: { min: 1, max: 20, mode: "box" } }],
  ["allow_partial", { boolean: {} }],
  ["show_snooze", { boolean: {} }],
  ["show_skip", { boolean: {} }],
  ["show_upcoming", { boolean: {} }],
  ["upcoming_count", { number: { min: 1, max: 10, mode: "box" } }],
  ["show_stock", { boolean: {} }],
  ["stock_filter", { select: { mode: "dropdown", options: [
    { value: "low", labelKey: "card.editor.stock_low" },
    { value: "all", labelKey: "card.editor.stock_all" },
  ] } }],
];

class MedicationReminderCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.config = { ...DEFAULTS };
    this.t = createTranslator("en");
  }

  setConfig(config) {
    this.config = { ...DEFAULTS, ...(config || {}) };
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.t = createTranslator(resolveLanguage(hass));
    this.render();
  }

  get hass() { return this._hass; }

  schema() {
    return EDITOR_FIELDS.map(([name, selector]) => {
      if (!selector.select) return { name, selector };
      return {
        name,
        selector: {
          select: {
            mode: selector.select.mode,
            options: selector.select.options.map((option) => ({
              value: option.value, label: this.t(option.labelKey),
            })),
          },
        },
      };
    });
  }

  render() {
    if (!this.hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (field) => this.t(`card.editor.${field.name}`);
      this._form.addEventListener("value-changed", (event) => {
        event.stopPropagation();
        this.dispatchEvent(new CustomEvent("config-changed", {
          detail: { config: { type: `custom:${CARD_TYPE}`, ...event.detail.value } },
          bubbles: true, composed: true,
        }));
      });
      this.shadowRoot.append(this._form);
    }
    this._form.hass = this.hass;
    this._form.schema = this.schema();
    this._form.data = this.config;
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, MedicationReminderCard);
}
if (!customElements.get(EDITOR_TYPE)) {
  customElements.define(EDITOR_TYPE, MedicationReminderCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  const language = resolveLanguage({ language: navigator.language });
  const translate = createTranslator(language);
  window.customCards.push({
    type: CARD_TYPE,
    name: translate("card.name"),
    description: translate("card.description"),
    preview: true,
    documentationURL: "https://github.com/Finnlife/hass-medreminder",
  });
}
