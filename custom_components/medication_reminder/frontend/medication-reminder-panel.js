const DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];
const STATUS = { pending: "Offen", partial: "Teilweise", taken: "Genommen", skipped: "Ausgelassen" };

const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const number = (value) => new Intl.NumberFormat("de-DE", { maximumFractionDigits: 3 }).format(value ?? 0);
const dateTime = (value) => value ? new Intl.DateTimeFormat("de-DE", {
  weekday: "short", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"
}).format(new Date(value)) : "–";
const relative = (value) => {
  if (!value) return "Nicht geplant";
  const diff = new Date(value).getTime() - Date.now();
  const minutes = Math.round(Math.abs(diff) / 60000);
  if (minutes < 1) return "jetzt";
  if (minutes < 60) return `${diff < 0 ? "vor" : "in"} ${minutes} Min.`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${diff < 0 ? "vor" : "in"} ${hours} Std.`;
  return dateTime(value);
};

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
    this.shadowRoot.addEventListener("click", (event) => this.onClick(event));
    this.shadowRoot.addEventListener("submit", (event) => this.onSubmit(event));
    this.shadowRoot.addEventListener("change", (event) => this.onChange(event));
  }

  set hass(value) {
    this._hass = value;
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
    if (!this.hass) throw new Error("Home Assistant ist noch nicht verbunden.");
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
    } catch (error) {
      this.showToast(this.errorText(error), true);
    } finally {
      this.loading = false;
      this.render();
    }
  }

  errorText(error) {
    return error?.message || error?.body?.message || "Die Aktion konnte nicht ausgeführt werden.";
  }

  showToast(message, error = false) {
    this.toast = { message, error };
    this.render();
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => { this.toast = null; this.render(); }, 4000);
  }

  medication(id) { return this.state?.medications.find((item) => item.id === id); }
  regimen(id) { return this.state?.regimens.find((item) => item.id === id); }

  render() {
    const content = !this.state
      ? `<div class="loading"><div class="loader"></div><h2>Medikamentenplan wird geladen</h2><p>Lokale Daten werden sicher aus Home Assistant gelesen.</p></div>`
      : this.renderContent();
    this.shadowRoot.innerHTML = `<style>${this.styles()}</style>${content}${this.renderModal()}${this.renderToast()}`;
  }

  renderContent() {
    const tabs = [
      ["overview", "mdi:view-dashboard-outline", "Übersicht"],
      ["medications", "mdi:pill-multiple", "Medikamente"],
      ["regimens", "mdi:calendar-clock", "Einnahmen"],
      ["history", "mdi:history", "Verlauf"],
    ];
    return `<div class="app">
      <header>
        <div class="brand"><div class="brand-icon"><ha-icon icon="mdi:pill-multiple"></ha-icon></div>
          <div><span>MEDICATION REMINDER</span><h1>Mein Medikamentenplan</h1></div></div>
        <div class="header-actions"><button class="ghost icon-only" data-action="refresh" title="Aktualisieren"><ha-icon icon="mdi:refresh"></ha-icon></button>
          <button class="primary" data-action="new-regimen"><ha-icon icon="mdi:plus"></ha-icon><span>Einnahme planen</span></button></div>
      </header>
      <nav>${tabs.map(([id, icon, label]) => `<button data-tab="${id}" class="${this.activeTab === id ? "active" : ""}"><ha-icon icon="${icon}"></ha-icon>${label}</button>`).join("")}</nav>
      <main>${this.renderTab()}</main>
      <footer><span><i class="live"></i> Lokal in Home Assistant gespeichert</span><span>Zuletzt synchronisiert ${new Date(this.lastLoad).toLocaleTimeString("de-DE", {hour:"2-digit",minute:"2-digit"})}</span></footer>
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
        <div><p class="eyebrow">HEUTE IM BLICK</p><h2>${open.length ? `${open.length} ${open.length === 1 ? "Einnahme wartet" : "Einnahmen warten"}` : "Alles erledigt"}</h2>
          <p>${open.length ? "Erfasse die tatsächlich genommenen Mengen oder verschiebe die Erinnerung." : "Aktuell sind keine Einnahmen offen."}</p></div>
        <div class="hero-orb"><ha-icon icon="${open.length ? "mdi:clock-alert-outline" : "mdi:check-bold"}"></ha-icon></div>
      </section>
      <section class="stats">
        ${this.stat("mdi:calendar-arrow-right", "Nächste Einnahme", nextRegimen?.name || "Keine", next ? relative(next.scheduled_at) : "–", "mint")}
        ${this.stat("mdi:clipboard-clock-outline", "Offene Vorgänge", open.length, open.length ? "Bitte prüfen" : "Alles aktuell", open.length ? "amber" : "blue")}
        ${this.stat("mdi:package-variant", "Niedriger Bestand", low.length, low.length ? low.map((m) => esc(m.name)).join(", ") : "Gut versorgt", low.length ? "red" : "violet")}
        ${this.stat("mdi:pill", "Medikamente", this.state.medications.length, `${this.state.regimens.filter((r) => r.active).length} aktive Pläne`, "blue")}
      </section>
      <div class="section-heading"><div><p class="eyebrow">OFFENE TICKETS</p><h2>Fällige Einnahmen</h2></div></div>
      <section class="ticket-list">${open.length ? open.map((item) => this.renderTicket(item)).join("") : this.empty("mdi:check-decagram-outline", "Keine offenen Einnahmen", "Sobald eine Einnahme fällig wird, erscheint sie hier.")}</section>
      <div class="section-heading"><div><p class="eyebrow">BESTÄNDE</p><h2>Schneller Überblick</h2></div><button class="ghost" data-action="new-medication"><ha-icon icon="mdi:plus"></ha-icon>Medikament</button></div>
      <section class="stock-grid">${this.state.medications.length ? this.state.medications.slice(0, 6).map((item) => this.stockCard(item, true)).join("") : this.empty("mdi:pill-off", "Noch keine Medikamente", "Lege zuerst ein Medikament an.")}</section>`;
  }

  stat(icon, label, value, hint, tone) {
    return `<article class="stat"><div class="stat-icon ${tone}"><ha-icon icon="${icon}"></ha-icon></div><div><span>${label}</span><strong>${esc(value)}</strong><small>${hint}</small></div></article>`;
  }

  renderTicket(item) {
    const regimen = this.regimen(item.regimen_id);
    if (!regimen) return "";
    const snoozed = item.snoozed_until && new Date(item.snoozed_until) > new Date();
    return `<article class="ticket" data-occurrence="${item.id}">
      <div class="ticket-side ${snoozed ? "snoozed" : ""}"><ha-icon icon="${snoozed ? "mdi:power-sleep" : "mdi:alarm"}"></ha-icon></div>
      <div class="ticket-body"><div class="ticket-head"><div><span class="badge ${item.status}">${STATUS[item.status]}</span><h3>${esc(regimen.name)}</h3><p>Soll: ${dateTime(item.scheduled_at)} · ${snoozed ? `Schlummert bis ${dateTime(item.snoozed_until)}` : relative(item.scheduled_at)}</p></div><strong class="time">${new Date(item.scheduled_at).toLocaleTimeString("de-DE", {hour:"2-digit",minute:"2-digit"})}</strong></div>
        ${regimen.instructions ? `<p class="instructions"><ha-icon icon="mdi:information-outline"></ha-icon>${esc(regimen.instructions)}</p>` : ""}
        <div class="dose-list">${item.items.map((dose) => {
          const med = this.medication(dose.medication_id);
          const remaining = Math.max(0, dose.planned_dose - dose.taken_dose);
          return `<label class="dose ${remaining === 0 ? "done" : ""}"><input type="checkbox" data-medication="${dose.medication_id}" ${remaining ? "checked" : "disabled"}>
            <span class="pill-dot"></span><span class="dose-name"><strong>${esc(med?.name || "Gelöschtes Medikament")}</strong><small>${esc(med?.strength || med?.form || "")}</small></span>
            <span class="dose-amount"><input type="number" data-dose="${dose.medication_id}" min="0" max="${remaining}" step="0.001" value="${remaining}" ${remaining ? "" : "disabled"}> ${esc(med?.unit || "")}${dose.taken_dose ? `<small>${number(dose.taken_dose)} bereits</small>` : ""}</span></label>`;
        }).join("")}</div>
        <div class="ticket-actions"><button class="primary" data-action="take-selected" data-id="${item.id}"><ha-icon icon="mdi:check"></ha-icon>Auswahl genommen</button>
          <div class="snooze"><button class="ghost" data-action="snooze" data-id="${item.id}" data-minutes="30">30 Min.</button><button class="ghost" data-action="snooze" data-id="${item.id}" data-minutes="60">1 Std.</button><button class="ghost" data-action="snooze" data-id="${item.id}" data-minutes="120">2 Std.</button></div>
          <input class="custom-time" type="datetime-local" data-snooze-time="${item.id}"><button class="ghost icon-only" data-action="snooze-custom" data-id="${item.id}" title="Bis zur gewählten Zeit schlummern"><ha-icon icon="mdi:clock-edit-outline"></ha-icon></button>
          <button class="text danger-text" data-action="skip" data-id="${item.id}">Auslassen</button></div>
      </div></article>`;
  }

  renderMedications() {
    return `<div class="page-title"><div><p class="eyebrow">APOTHEKE</p><h2>Medikamente & Bestände</h2><p>Packungsdaten, Dosiseinheit und Warnschwellen zentral verwalten.</p></div><button class="primary" data-action="new-medication"><ha-icon icon="mdi:plus"></ha-icon>Medikament anlegen</button></div>
      <section class="stock-grid large">${this.state.medications.length ? this.state.medications.map((item) => this.stockCard(item, false)).join("") : this.empty("mdi:pill-off", "Noch keine Medikamente", "Erstelle dein erstes Medikament samt Anfangsbestand.")}</section>`;
  }

  stockCard(item, compact) {
    const low = item.stock <= item.low_stock_threshold;
    const percentage = item.low_stock_threshold > 0 ? Math.min(100, (item.stock / Math.max(item.low_stock_threshold * 3, 1)) * 100) : 100;
    return `<article class="stock-card ${low ? "is-low" : ""}"><div class="stock-top"><div class="medicine-icon"><ha-icon icon="mdi:pill"></ha-icon></div><span class="badge ${low ? "warning" : "ok"}">${low ? "Nachbestellen" : "Verfügbar"}</span></div>
      <h3>${esc(item.name)}</h3><p>${[item.manufacturer, item.strength, item.form].filter(Boolean).map(esc).join(" · ") || "Keine Zusatzangaben"}</p>
      <div class="stock-value"><strong>${number(item.stock)}</strong><span>${esc(item.unit)}</span></div><div class="progress"><i style="width:${percentage}%"></i></div><small>Warnung ab ${number(item.low_stock_threshold)} ${esc(item.unit)}</small>
      <div class="card-actions"><button class="ghost" data-action="adjust-stock" data-id="${item.id}"><ha-icon icon="mdi:plus-minus-variant"></ha-icon>Bestand</button>${compact ? `<button class="text" data-tab="medications">Details</button>` : `<button class="text" data-action="edit-medication" data-id="${item.id}">Bearbeiten</button><button class="text danger-text" data-action="delete-medication" data-id="${item.id}">Löschen</button>`}</div></article>`;
  }

  renderRegimens() {
    return `<div class="page-title"><div><p class="eyebrow">ZEITPLÄNE</p><h2>Einnahmen & Erinnerungen</h2><p>Flexible Wochen- und Intervallpläne mit eigenen Benachrichtigungszielen.</p></div><button class="primary" data-action="new-regimen"><ha-icon icon="mdi:plus"></ha-icon>Einnahme planen</button></div>
      <section class="regimen-list">${this.state.regimens.length ? this.state.regimens.map((item) => this.regimenCard(item)).join("") : this.empty("mdi:calendar-blank-outline", "Noch keine Einnahmen geplant", "Erstelle einen Wochenplan oder einen Rhythmus alle x Tage.")}</section>`;
  }

  regimenCard(item) {
    return `<article class="regimen-card ${item.active ? "" : "inactive"}"><div class="regimen-icon"><ha-icon icon="mdi:calendar-clock"></ha-icon></div><div class="regimen-main"><div class="regimen-title"><span class="badge ${item.active ? "ok" : "muted"}">${item.active ? "Aktiv" : "Pausiert"}</span><h3>${esc(item.name)}</h3></div>
      <p class="schedule"><ha-icon icon="mdi:clock-outline"></ha-icon>${esc(this.scheduleText(item.schedule))}</p><div class="chips">${item.items.map((dose) => { const med = this.medication(dose.medication_id); return `<span>${number(dose.dose)} ${esc(med?.unit || "")} ${esc(med?.name || "Unbekannt")}</span>`; }).join("")}</div>
      <small>${item.notify_services.length} Benachrichtigungsziel(e) · Wiederholung alle ${item.repeat_minutes} Min.</small></div>
      <div class="vertical-actions"><button class="ghost icon-only" data-action="edit-regimen" data-id="${item.id}" title="Bearbeiten"><ha-icon icon="mdi:pencil-outline"></ha-icon></button><button class="ghost icon-only danger-text" data-action="delete-regimen" data-id="${item.id}" title="Löschen"><ha-icon icon="mdi:delete-outline"></ha-icon></button></div></article>`;
  }

  scheduleText(schedule) {
    if (schedule.type === "interval") return `Alle ${schedule.every_days} Tag${schedule.every_days === 1 ? "" : "e"}, ab ${new Date(`${schedule.start_date}T00:00:00`).toLocaleDateString("de-DE")} um ${schedule.time} Uhr`;
    const groups = new Map();
    Object.entries(schedule.days).forEach(([day, times]) => {
      const key = times.join(", ");
      groups.set(key, [...(groups.get(key) || []), DAYS[Number(day)].slice(0, 2)]);
    });
    return [...groups.entries()].map(([times, days]) => `${days.join(", ")} · ${times} Uhr`).join(" | ");
  }

  renderHistory() {
    const rows = this.state.occurrences.filter((item) => ["taken", "skipped"].includes(item.status)).sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at));
    return `<div class="page-title"><div><p class="eyebrow">PROTOKOLL</p><h2>Einnahmeverlauf</h2><p>Soll- und Ist-Zeitpunkt sowie tatsächlich abgebuchte Dosen.</p></div></div>
      ${rows.length ? `<div class="table-wrap"><table><thead><tr><th>Status</th><th>Einnahme</th><th>Geplant</th><th>Tatsächlich</th><th>Abweichung</th><th>Dosen</th></tr></thead><tbody>${rows.map((item) => {
        const regimen = this.regimen(item.regimen_id); const actual = item.taken_at ? new Date(item.taken_at) : null; const planned = new Date(item.scheduled_at);
        const diff = actual && item.status !== "skipped" ? Math.round((actual - planned) / 60000) : null;
        return `<tr><td><span class="badge ${item.status}">${STATUS[item.status]}</span></td><td><strong>${esc(regimen?.name || "Gelöschter Plan")}</strong></td><td>${dateTime(item.scheduled_at)}</td><td>${item.status === "skipped" ? "Ausgelassen" : dateTime(item.taken_at)}</td><td>${diff === null ? "–" : `${diff > 0 ? "+" : ""}${diff} Min.`}</td><td>${item.items.map((dose) => `${number(dose.taken_dose)}/${number(dose.planned_dose)} ${esc(this.medication(dose.medication_id)?.name || "")}`).join("<br>")}</td></tr>`;
      }).join("")}</tbody></table></div>` : this.empty("mdi:history", "Noch kein Verlauf", "Abgeschlossene und ausgelassene Einnahmen werden hier protokolliert.")}`;
  }

  empty(icon, title, text) { return `<div class="empty"><ha-icon icon="${icon}"></ha-icon><h3>${title}</h3><p>${text}</p></div>`; }

  renderModal() {
    if (!this.modal || !this.state) return "";
    if (this.modal.type === "medication") return this.medicationModal(this.modal.item);
    if (this.modal.type === "regimen") return this.regimenModal(this.modal.item);
    return "";
  }

  medicationModal(item = {}) {
    return `<div class="modal-backdrop" data-action="close-modal"><section class="modal" role="dialog" aria-modal="true" aria-label="Medikament bearbeiten" data-modal-stop>
      <div class="modal-head"><div><p class="eyebrow">MEDIKAMENT</p><h2>${item.id ? "Medikament bearbeiten" : "Neues Medikament"}</h2></div><button class="ghost icon-only" data-action="close-modal"><ha-icon icon="mdi:close"></ha-icon></button></div>
      <form data-form="medication"><input type="hidden" name="id" value="${esc(item.id || "")}"><div class="form-grid">
        ${this.field("name", "Name", item.name, true, "z. B. Metformin")}${this.field("manufacturer", "Hersteller", item.manufacturer, false, "z. B. 1A Pharma")}
        ${this.field("barcode", "Barcode / PZN", item.barcode, false, "Scan- oder Artikelnummer")}${this.field("strength", "Wirkstärke", item.strength, false, "z. B. 500 mg")}
        ${this.field("form", "Darreichungsform", item.form, false, "Tablette, Tropfen, …")}${this.field("unit", "Bestandseinheit", item.unit || "Stück", true, "Stück, ml, Hübe, …")}
        ${this.field("stock", "Aktueller Bestand", item.stock ?? 0, true, "", "number", "0", "0.001")}${this.field("low_stock_threshold", "Warnschwelle", item.low_stock_threshold ?? 0, true, "", "number", "0", "0.001")}
        <label class="field full"><span>Notizen</span><textarea name="notes" rows="3" placeholder="Optionale Hinweise">${esc(item.notes || "")}</textarea></label>
      </div><div class="modal-actions"><button type="button" class="ghost" data-action="close-modal">Abbrechen</button><button class="primary" type="submit"><ha-icon icon="mdi:content-save-outline"></ha-icon>Speichern</button></div></form>
    </section></div>`;
  }

  regimenModal(item = {}) {
    const schedule = item.schedule || { type: "weekly", days: {0:["13:00"],1:["13:00"],2:["13:00"],3:["13:00"],4:["13:00"],5:["11:00"],6:["11:00"]} };
    const items = item.items?.length ? item.items : [{ medication_id: this.state.medications[0]?.id || "", dose: 1 }];
    return `<div class="modal-backdrop" data-action="close-modal"><section class="modal wide" role="dialog" aria-modal="true" aria-label="Einnahme bearbeiten" data-modal-stop>
      <div class="modal-head"><div><p class="eyebrow">EINNAHMEPLAN</p><h2>${item.id ? "Einnahme bearbeiten" : "Neue Einnahme"}</h2></div><button class="ghost icon-only" data-action="close-modal"><ha-icon icon="mdi:close"></ha-icon></button></div>
      <form data-form="regimen"><input type="hidden" name="id" value="${esc(item.id || "")}"><div class="form-grid">
        ${this.field("name", "Bezeichnung", item.name, true, "z. B. Mittagsmedikation")}<label class="field"><span>Status</span><select name="active"><option value="true" ${item.active !== false ? "selected" : ""}>Aktiv</option><option value="false" ${item.active === false ? "selected" : ""}>Pausiert</option></select></label>
        <div class="field full"><span>Medikamente & Dosis</span><div class="item-editor">${items.map((dose, index) => this.doseRow(dose, index)).join("")}</div><button type="button" class="text add-dose" data-action="add-dose"><ha-icon icon="mdi:plus"></ha-icon>Weiteres Medikament</button></div>
        <label class="field"><span>Rhythmus</span><select name="schedule_type"><option value="weekly" ${schedule.type === "weekly" ? "selected" : ""}>Wöchentlich nach Wochentag</option><option value="interval" ${schedule.type === "interval" ? "selected" : ""}>Alle x Tage</option></select></label>
        ${this.field("repeat_minutes", "Erneut erinnern nach (Min.)", item.repeat_minutes ?? 30, true, "", "number", "5", "1")}
        <div class="field full schedule-weekly ${schedule.type === "weekly" ? "" : "hidden"}"><span>Wochentage und Uhrzeiten</span><div class="week-grid">${DAYS.map((day, index) => { const times = schedule.type === "weekly" ? schedule.days?.[index] || schedule.days?.[String(index)] || [] : []; return `<label><input type="checkbox" name="day_${index}" ${times.length ? "checked" : ""}><b>${day}</b><input type="text" name="times_${index}" value="${esc(times.join(", ") || (index < 5 ? "13:00" : "11:00"))}" placeholder="13:00, 20:00"></label>`; }).join("")}</div><small>Mehrere Uhrzeiten mit Komma trennen.</small></div>
        <div class="field full schedule-interval ${schedule.type === "interval" ? "" : "hidden"}"><span>Intervall</span><div class="inline-fields">${this.field("every_days", "Alle x Tage", schedule.every_days || 2, true, "", "number", "1", "1")}${this.field("start_date", "Startdatum", schedule.start_date || new Date().toISOString().slice(0,10), true, "", "date")}${this.field("interval_time", "Uhrzeit", schedule.time || "13:00", true, "", "time")}</div></div>
        <label class="field full"><span>Benachrichtigungsdienste</span><input name="notify_services" list="notify-services" value="${esc((item.notify_services || []).join(", "))}" placeholder="notify.mobile_app_mein_handy"><datalist id="notify-services">${this.state.notify_services.map((service) => `<option value="${esc(service)}"></option>`).join("")}</datalist><small>Mehrere Dienste mit Komma trennen. Aktionsbuttons werden automatisch ergänzt.</small></label>
        <label class="field full"><span>Scripts bei jeder Erinnerung</span><input name="scripts" list="scripts" value="${esc((item.scripts || []).join(", "))}" placeholder="script.medikamenten_erinnerung"><datalist id="scripts">${this.state.scripts.map((script) => `<option value="${esc(script)}"></option>`).join("")}</datalist></label>
        <label class="field full"><span>Einnahmehinweis</span><textarea name="instructions" rows="2" placeholder="z. B. Mit einem Glas Wasser und zum Essen">${esc(item.instructions || "")}</textarea></label>
      </div><div class="modal-actions"><button type="button" class="ghost" data-action="close-modal">Abbrechen</button><button class="primary" type="submit" ${this.state.medications.length ? "" : "disabled"}><ha-icon icon="mdi:content-save-outline"></ha-icon>Plan speichern</button></div></form>
    </section></div>`;
  }

  doseRow(dose, index) {
    return `<div class="dose-row"><select name="medication_${index}" required><option value="">Medikament wählen</option>${this.state.medications.map((med) => `<option value="${med.id}" ${med.id === dose.medication_id ? "selected" : ""}>${esc(med.name)} (${esc(med.unit)})</option>`).join("")}</select><input name="dose_${index}" type="number" min="0.001" step="0.001" value="${dose.dose}" required><button type="button" class="ghost icon-only" data-action="remove-dose" title="Entfernen"><ha-icon icon="mdi:close"></ha-icon></button></div>`;
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

  onClick(event) {
    const button = event.target.closest("button, [data-action='close-modal']");
    if (!button) return;
    if (button.hasAttribute("data-modal-stop") || event.target.closest("[data-modal-stop]") && button.classList.contains("modal-backdrop")) return;
    if (button.dataset.tab) { this.activeTab = button.dataset.tab; this.render(); return; }
    const action = button.dataset.action;
    const id = button.dataset.id;
    if (action === "refresh") return this.load();
    if (action === "close-modal") { this.modal = null; this.render(); return; }
    if (action === "new-medication") { this.modal = { type: "medication", item: {} }; this.render(); return; }
    if (action === "edit-medication") { this.modal = { type: "medication", item: this.medication(id) }; this.render(); return; }
    if (action === "new-regimen") {
      if (!this.state.medications.length) { this.showToast("Lege zuerst mindestens ein Medikament an.", true); this.modal = { type: "medication", item: {} }; this.render(); return; }
      this.modal = { type: "regimen", item: {} }; this.render(); return;
    }
    if (action === "edit-regimen") { this.modal = { type: "regimen", item: this.regimen(id) }; this.render(); return; }
    if (action === "delete-medication" && confirm("Dieses Medikament wirklich löschen?")) return this.mutate(() => this.call("delete_medication", { id }), "Medikament gelöscht.");
    if (action === "delete-regimen" && confirm("Diesen Einnahmeplan wirklich löschen? Offene Vorgänge werden ebenfalls entfernt.")) return this.mutate(() => this.call("delete_regimen", { id }), "Einnahmeplan gelöscht.");
    if (action === "adjust-stock") {
      const value = prompt("Bestandsänderung eingeben (z. B. 20 oder -2):", "1");
      if (value !== null && Number.isFinite(Number(value)) && Number(value) !== 0) return this.mutate(() => this.call("adjust_stock", { id, delta: Number(value) }), "Bestand aktualisiert.");
      return;
    }
    if (action === "take-selected") return this.takeSelected(id, button.closest(".ticket"));
    if (action === "snooze") return this.mutate(() => this.call("snooze", { id, minutes: Number(button.dataset.minutes) }), "Erinnerung verschoben.");
    if (action === "snooze-custom") {
      const input = this.shadowRoot.querySelector(`[data-snooze-time="${id}"]`);
      if (!input?.value) return this.showToast("Bitte zuerst eine Uhrzeit auswählen.", true);
      const until = new Date(input.value);
      if (until <= new Date()) return this.showToast("Die Schlummerzeit muss in der Zukunft liegen.", true);
      return this.mutate(() => this.call("snooze", { id, until: until.toISOString() }), "Erinnerung bis zur gewählten Zeit verschoben.");
    }
    if (action === "skip" && confirm("Diese Einnahme auslassen? Der Bestand wird nicht verändert.")) return this.mutate(() => this.call("skip", { id }), "Einnahme als ausgelassen markiert.");
    if (action === "add-dose") { this.addDoseRow(button); return; }
    if (action === "remove-dose") { if (button.closest(".item-editor").children.length > 1) button.closest(".dose-row").remove(); return; }
  }

  takeSelected(id, ticket) {
    const doses = {};
    ticket.querySelectorAll("[data-medication]").forEach((checkbox) => {
      if (checkbox.checked) doses[checkbox.dataset.medication] = Number(ticket.querySelector(`[data-dose="${checkbox.dataset.medication}"]`).value);
    });
    if (!Object.values(doses).some((value) => value > 0)) return this.showToast("Wähle mindestens eine Dosis aus.", true);
    return this.mutate(() => this.call("record_intake", { id, doses }), "Einnahme gespeichert und Bestand abgebucht.");
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
      return this.mutate(() => this.call("save_medication", { medication }), "Medikament gespeichert.");
    }
    if (form.dataset.form === "regimen") {
      try {
        const regimen = this.regimenFromForm(form, data);
        return this.mutate(() => this.call("save_regimen", { regimen }), "Einnahmeplan gespeichert.");
      } catch (error) { this.showToast(error.message, true); }
    }
  }

  regimenFromForm(form, data) {
    const rows = [...form.querySelectorAll(".dose-row")];
    const items = rows.map((row) => ({ medication_id: row.querySelector("select").value, dose: Number(row.querySelector("input").value) }));
    if (new Set(items.map((item) => item.medication_id)).size !== items.length) throw new Error("Ein Medikament darf pro Plan nur einmal vorkommen.");
    let schedule;
    if (data.get("schedule_type") === "weekly") {
      const days = {};
      DAYS.forEach((_, index) => {
        if (!form.elements[`day_${index}`].checked) return;
        const times = form.elements[`times_${index}`].value.split(",").map((v) => v.trim()).filter(Boolean);
        if (!times.length || times.some((time) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))) throw new Error(`Ungültige Uhrzeit bei ${DAYS[index]}.`);
        days[index] = times;
      });
      if (!Object.keys(days).length) throw new Error("Wähle mindestens einen Wochentag.");
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
    .brand,.header-actions,.ticket-actions,.card-actions,.regimen-title,.page-title,.section-heading,.modal-head,.modal-actions { display:flex; align-items:center; } .brand { gap:14px; } .brand-icon { width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(135deg,#087f69,#19b68b);color:#fff;box-shadow:0 8px 22px #0b8f7240; } .brand-icon ha-icon{--mdc-icon-size:26px}.brand span,.eyebrow{font-size:10px;letter-spacing:.16em;font-weight:800;color:var(--primary-color,#07856c);margin:0 0 4px}.brand h1{font-size:20px;line-height:1;margin:0;letter-spacing:-.02em}.header-actions{gap:10px}
    nav { display:flex; gap:6px; padding:14px clamp(20px,4vw,64px) 0; max-width:1440px; margin:auto; overflow:auto; } nav button { display:flex;align-items:center;gap:8px;padding:11px 16px;border:0;border-radius:12px;background:transparent;color:var(--muted);font-weight:650;white-space:nowrap } nav button.active { background:var(--surface);color:var(--primary-color,#07856c);box-shadow:0 2px 12px #0000000b } nav ha-icon{--mdc-icon-size:20px}
    main { max-width:1440px; margin:auto; padding:28px clamp(20px,4vw,64px) 48px; } .hero { min-height:190px;border-radius:26px;padding:34px 38px;display:flex;align-items:center;justify-content:space-between;color:#fff;background:linear-gradient(118deg,#075f54,#07856c 55%,#17aa82);position:relative;overflow:hidden;box-shadow:0 18px 45px #08745f36 } .hero:after{content:"";position:absolute;width:340px;height:340px;border:1px solid #ffffff26;border-radius:50%;right:-80px;top:-190px;box-shadow:0 0 0 55px #ffffff0b,0 0 0 110px #ffffff08}.hero .eyebrow{color:#c8fff0}.hero h2{font-size:34px;letter-spacing:-.04em;margin:6px 0}.hero p:last-child{opacity:.82;margin:0}.hero-orb{width:90px;height:90px;border-radius:28px;background:#ffffff1c;display:grid;place-items:center;z-index:1;border:1px solid #ffffff2e}.hero-orb ha-icon{--mdc-icon-size:48px}
    .stats { display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0 38px}.stat{background:var(--surface);padding:20px;border-radius:18px;display:flex;gap:14px;align-items:center;border:1px solid var(--line);box-shadow:0 6px 24px #122b2410;min-width:0}.stat-icon{width:46px;height:46px;flex:0 0 46px;border-radius:14px;display:grid;place-items:center}.stat-icon.mint{background:#d9f8ee;color:#07856c}.stat-icon.amber{background:#fff1ce;color:#a96500}.stat-icon.red{background:#ffe1df;color:#c63f3a}.stat-icon.blue{background:#e1edff;color:#336ccc}.stat-icon.violet{background:#eee5ff;color:#7752bd}.stat div:last-child{min-width:0}.stat span,.stat small{display:block;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stat span{font-size:12px;font-weight:650}.stat strong{font-size:22px;display:block;margin:2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stat small{font-size:11px}
    .section-heading,.page-title{justify-content:space-between;gap:20px;margin:30px 0 16px}.section-heading h2,.page-title h2{font-size:25px;letter-spacing:-.03em;margin:2px 0}.page-title{margin-top:4px;align-items:flex-end}.page-title p:last-child{color:var(--muted);margin:4px 0 0}.ticket-list{display:grid;gap:16px}.ticket{display:grid;grid-template-columns:64px 1fr;background:var(--surface);border:1px solid var(--line);border-radius:20px;overflow:hidden;box-shadow:0 8px 28px #142f2810}.ticket-side{background:#e4faf3;color:#07856c;display:flex;justify-content:center;padding-top:28px}.ticket-side.snoozed{background:#eee9fa;color:#7558ae}.ticket-side ha-icon{--mdc-icon-size:27px}.ticket-body{padding:24px}.ticket-head{display:flex;justify-content:space-between;gap:16px}.ticket-head h3{font-size:21px;margin:7px 0 3px}.ticket-head p{color:var(--muted);margin:0;font-size:13px}.ticket-head .time{font-size:25px;color:var(--primary-color,#07856c)}.badge{display:inline-flex;padding:4px 9px;border-radius:99px;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}.badge.pending,.badge.warning{background:#fff0c7;color:#946000}.badge.partial{background:#e9e0ff;color:#6948a5}.badge.taken,.badge.ok{background:#d9f8ee;color:#08725e}.badge.skipped{background:#f0f1f1;color:#69716f}.badge.muted{background:#eceeee;color:#747b79}.instructions{padding:10px 12px;background:color-mix(in srgb,var(--primary-color,#07856c) 7%,transparent);border-radius:10px;color:var(--muted);font-size:13px;display:flex;gap:8px;align-items:center}.instructions ha-icon{--mdc-icon-size:18px}.dose-list{margin:18px 0 20px;border:1px solid var(--line);border-radius:14px;overflow:hidden}.dose{display:grid;grid-template-columns:auto auto 1fr auto;align-items:center;gap:12px;padding:13px 15px;border-bottom:1px solid var(--line)}.dose:last-child{border:0}.dose.done{opacity:.55}.dose>input{width:17px;height:17px;accent-color:var(--primary-color,#07856c)}.pill-dot{width:28px;height:28px;border-radius:9px;background:#e4faf3;position:relative}.pill-dot:after{content:"";position:absolute;width:14px;height:7px;border-radius:8px;background:#0b9878;transform:rotate(-35deg);top:10px;left:7px}.dose-name strong,.dose-name small,.dose-amount small{display:block}.dose-name small,.dose-amount small{color:var(--muted);font-size:11px}.dose-amount{text-align:right;font-weight:700}.dose-amount input{width:70px;padding:7px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);text-align:right}.ticket-actions{gap:8px;flex-wrap:wrap}.snooze{display:flex;gap:5px}.custom-time{padding:9px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink)}
    button.primary,button.ghost,button.text{border-radius:11px;padding:10px 14px;display:inline-flex;gap:8px;align-items:center;justify-content:center;font-weight:700;border:0}button.primary{background:var(--primary-color,#07856c);color:#fff;box-shadow:0 5px 14px color-mix(in srgb,var(--primary-color,#07856c) 24%,transparent)}button.primary:hover{filter:brightness(1.06)}button.primary:disabled{opacity:.45;cursor:not-allowed}button.ghost{background:var(--surface);color:var(--ink);border:1px solid var(--line)}button.text{background:transparent;color:var(--primary-color,#07856c);padding:8px}.icon-only{width:42px;height:42px;padding:0!important}.danger-text{color:#c04440!important}
    .stock-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.stock-grid.large{grid-template-columns:repeat(3,1fr)}.stock-card{background:var(--surface);border:1px solid var(--line);border-radius:19px;padding:20px;box-shadow:0 6px 24px #122b240c}.stock-card.is-low{border-color:#e5a19c}.stock-top{display:flex;justify-content:space-between}.medicine-icon{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;background:#e3f8f1;color:#087d68}.stock-card h3{font-size:18px;margin:16px 0 3px}.stock-card>p{color:var(--muted);font-size:12px;min-height:18px;margin:0}.stock-value{display:flex;align-items:baseline;gap:6px;margin-top:18px}.stock-value strong{font-size:32px;letter-spacing:-.04em}.stock-value span{color:var(--muted)}.progress{height:6px;border-radius:9px;background:var(--line);margin:10px 0 7px;overflow:hidden}.progress i{display:block;height:100%;background:linear-gradient(90deg,#07856c,#36c79e);border-radius:9px}.is-low .progress i{background:#d95750}.stock-card>small{color:var(--muted)}.card-actions{gap:6px;margin-top:18px;padding-top:14px;border-top:1px solid var(--line);flex-wrap:wrap}
    .regimen-list{display:grid;gap:13px}.regimen-card{display:grid;grid-template-columns:54px 1fr auto;gap:17px;align-items:start;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:20px}.regimen-card.inactive{opacity:.65}.regimen-icon{width:52px;height:52px;border-radius:16px;background:#e3f8f1;color:#07856c;display:grid;place-items:center}.regimen-icon ha-icon{--mdc-icon-size:27px}.regimen-title{gap:10px}.regimen-title h3{margin:0;font-size:19px}.schedule{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:13px;margin:8px 0}.schedule ha-icon{--mdc-icon-size:17px}.chips{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}.chips span{padding:5px 9px;border-radius:8px;background:color-mix(in srgb,var(--primary-color,#07856c) 8%,transparent);font-size:12px}.regimen-main>small{color:var(--muted)}.vertical-actions{display:flex;gap:6px}
    .table-wrap{overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:18px}table{border-collapse:collapse;width:100%;min-width:900px}th,td{text-align:left;padding:15px;border-bottom:1px solid var(--line);font-size:13px}th{font-size:10px;letter-spacing:.1em;color:var(--muted);text-transform:uppercase;background:color-mix(in srgb,var(--surface) 88%,var(--ink) 2%)}tbody tr:last-child td{border:0}.empty{grid-column:1/-1;text-align:center;padding:52px 20px;background:var(--surface);border:1px dashed var(--line);border-radius:19px}.empty ha-icon{--mdc-icon-size:42px;color:var(--primary-color,#07856c)}.empty h3{margin:12px 0 4px}.empty p{color:var(--muted);margin:0}
    .modal-backdrop{position:fixed;inset:0;z-index:30;background:#0a1613a3;backdrop-filter:blur(7px);display:grid;place-items:center;padding:20px}.modal{width:min(680px,100%);max-height:92vh;overflow:auto;background:var(--surface);border-radius:23px;box-shadow:0 30px 80px #0006}.modal.wide{width:min(920px,100%)}.modal-head{justify-content:space-between;padding:23px 26px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--surface);z-index:1}.modal-head h2{margin:2px 0;font-size:23px}.modal form{padding:24px 26px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:17px}.field{display:flex;flex-direction:column;gap:7px}.field.full{grid-column:1/-1}.field>span{font-size:12px;font-weight:750}.field small{color:var(--muted);line-height:1.35}.field input,.field select,.field textarea,.dose-row input,.dose-row select{width:100%;border:1px solid var(--line);border-radius:10px;padding:11px 12px;background:var(--surface);color:var(--ink);outline:none}.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--primary-color,#07856c);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary-color,#07856c) 12%,transparent)}.modal-actions{justify-content:flex-end;gap:9px;margin-top:26px}.item-editor{display:grid;gap:8px}.dose-row{display:grid;grid-template-columns:2fr 1fr auto;gap:8px}.add-dose{align-self:flex-start;margin-top:6px}.week-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.week-grid label{display:grid;grid-template-columns:auto 1fr 1.3fr;gap:8px;align-items:center;border:1px solid var(--line);padding:8px;border-radius:10px}.week-grid label>input:first-child{width:17px}.week-grid b{font-size:12px}.week-grid input[type=text]{padding:7px}.inline-fields{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.hidden{display:none!important}.toast{position:fixed;z-index:50;right:24px;bottom:24px;max-width:420px;padding:14px 17px;border-radius:13px;background:#063f35;color:#fff;display:flex;gap:10px;align-items:center;box-shadow:0 14px 40px #0004;animation:toast-in .22s ease}.toast.error{background:#9d302c}@keyframes toast-in{from{transform:translateY(14px);opacity:0}}.loading{min-height:100vh;display:grid;place-content:center;text-align:center;padding:20px}.loading p{color:var(--muted)}.loader{width:44px;height:44px;border:4px solid var(--line);border-top-color:var(--primary-color,#07856c);border-radius:50%;animation:spin .8s linear infinite;margin:auto}@keyframes spin{to{transform:rotate(360deg)}}footer{max-width:1440px;margin:auto;padding:18px clamp(20px,4vw,64px) 30px;border-top:1px solid var(--line);display:flex;justify-content:space-between;color:var(--muted);font-size:11px}.live{display:inline-block;width:7px;height:7px;background:#15af81;border-radius:50%;margin-right:6px}
    @media(max-width:1050px){.stats{grid-template-columns:repeat(2,1fr)}.stock-grid,.stock-grid.large{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:700px){header{height:72px;padding:0 16px}.brand span{display:none}.brand h1{font-size:17px}.header-actions .primary span{display:none}nav{padding:10px 14px 0}nav button{padding:10px 12px;font-size:12px}main{padding:18px 14px 36px}.hero{padding:27px 23px;min-height:165px}.hero h2{font-size:27px}.hero-orb{width:64px;height:64px}.hero-orb ha-icon{--mdc-icon-size:34px}.stats{grid-template-columns:1fr 1fr;gap:9px}.stat{padding:14px;gap:9px}.stat-icon{width:38px;height:38px;flex-basis:38px}.stat strong{font-size:18px}.ticket{grid-template-columns:1fr}.ticket-side{display:none}.ticket-body{padding:18px}.ticket-head .time{font-size:20px}.dose{grid-template-columns:auto auto 1fr}.dose-amount{grid-column:3}.ticket-actions>.primary{width:100%}.custom-time{max-width:185px}.stock-grid,.stock-grid.large{grid-template-columns:1fr}.page-title{align-items:flex-start;flex-direction:column}.regimen-card{grid-template-columns:44px 1fr}.vertical-actions{grid-column:2}.form-grid{grid-template-columns:1fr}.field.full{grid-column:auto}.week-grid{grid-template-columns:1fr}.inline-fields{grid-template-columns:1fr}.modal-backdrop{padding:0}.modal{max-height:100vh;height:100%;border-radius:0}.modal-head{padding:18px}.modal form{padding:18px}footer{flex-direction:column;gap:5px}}
  `; }
}

if (!customElements.get("medication-reminder-panel")) customElements.define("medication-reminder-panel", MedicationReminderPanel);
