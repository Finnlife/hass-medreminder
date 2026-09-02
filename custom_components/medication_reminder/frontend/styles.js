/**
 * Panel styling.
 *
 * Every colour is derived from Home Assistant theme variables so the panel
 * follows the active theme in both light and dark mode. Status tones are mixed
 * from the theme's own accent colours instead of fixed pastel values.
 */
export const PANEL_STYLES = `
:host {
  --mr-ink: var(--primary-text-color, #212121);
  --mr-muted: var(--secondary-text-color, #727272);
  --mr-surface: var(--card-background-color, #fff);
  --mr-bg: var(--primary-background-color, #f5f5f5);
  --mr-line: var(--divider-color, rgba(127, 127, 127, .25));
  --mr-accent: var(--primary-color, #03a9f4);
  --mr-danger: var(--error-color, #db4437);
  --mr-warn: var(--warning-color, #ffa600);
  --mr-ok: var(--success-color, #43a047);
  --mr-info: var(--info-color, #039be5);
  --mr-radius: var(--ha-card-border-radius, 12px);
  --mr-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, .12));
  --mr-max: 1180px;
  display: block;
  min-height: 100vh;
  color: var(--mr-ink);
  background: var(--mr-bg);
  font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif));
  font-size: 14px;
  line-height: 1.45;
}
* { box-sizing: border-box; }
button, input, select, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
h1, h2, h3 { margin: 0; font-weight: 500; letter-spacing: -.01em; }
p { margin: 0; }
.muted { color: var(--mr-muted); }
.spacer { flex: 1; }
.hidden { display: none !important; }

/* ---------------------------------------------------------------- chrome */
header {
  display: flex; align-items: center; gap: 16px; justify-content: space-between;
  padding: 14px clamp(12px, 3vw, 32px);
  background: var(--app-header-background-color, var(--mr-surface));
  border-bottom: 1px solid var(--mr-line);
  position: sticky; top: 0; z-index: 5;
}
.brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
.brand img { width: 34px; height: 34px; object-fit: contain; }
.brand h1 { font-size: 20px; }
.brand p { font-size: 12px; color: var(--mr-muted); }
.header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }

nav {
  display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none;
  padding: 8px clamp(12px, 3vw, 32px) 0;
  max-width: var(--mr-max); margin: 0 auto;
  border-bottom: 1px solid var(--mr-line);
}
nav::-webkit-scrollbar { display: none; }
nav button {
  display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
  padding: 10px 14px; border: 0; background: none; color: var(--mr-muted);
  border-bottom: 2px solid transparent; border-radius: 6px 6px 0 0; font-weight: 500;
}
nav button:hover { background: color-mix(in srgb, var(--mr-ink) 5%, transparent); }
nav button.active { color: var(--mr-accent); border-bottom-color: var(--mr-accent); }
nav ha-icon { --mdc-icon-size: 20px; }
nav .count {
  font-style: normal; font-size: 11px; font-weight: 600; line-height: 1;
  padding: 3px 6px; border-radius: 999px;
  background: var(--mr-accent); color: var(--text-primary-color, #fff);
}

main { max-width: var(--mr-max); margin: 0 auto; padding: 20px clamp(12px, 3vw, 32px) 48px; }
footer {
  max-width: var(--mr-max); margin: 0 auto; display: flex; justify-content: space-between;
  gap: 12px; padding: 12px clamp(12px, 3vw, 32px) 28px;
  color: var(--mr-muted); font-size: 12px; border-top: 1px solid var(--mr-line);
}
.live {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: var(--mr-ok); margin-right: 7px;
}

/* ---------------------------------------------------------------- buttons */
button.primary, button.ghost, button.text {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 9px 14px; border-radius: 8px; border: 1px solid transparent; font-weight: 500;
}
button.primary { background: var(--mr-accent); color: var(--text-primary-color, #fff); }
button.primary:hover { filter: brightness(1.08); }
button.primary:disabled { opacity: .5; cursor: not-allowed; filter: none; }
button.ghost { background: var(--mr-surface); border-color: var(--mr-line); }
button.ghost:hover { background: color-mix(in srgb, var(--mr-ink) 5%, var(--mr-surface)); }
button.text { background: none; color: var(--mr-accent); padding: 8px 10px; }
button.text:hover { background: color-mix(in srgb, var(--mr-accent) 10%, transparent); }
button.icon {
  display: inline-grid; place-items: center; width: 38px; height: 38px; padding: 0;
  border-radius: 50%; border: 0; background: none; color: var(--mr-muted);
}
button.icon:hover { background: color-mix(in srgb, var(--mr-ink) 8%, transparent); color: var(--mr-ink); }
button.icon.small { width: 30px; height: 30px; --mdc-icon-size: 18px; }
button.danger, .danger { color: var(--mr-danger); }
button.danger:hover { background: color-mix(in srgb, var(--mr-danger) 12%, transparent); color: var(--mr-danger); }
button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {
  outline: 2px solid var(--mr-accent); outline-offset: 2px;
}

/* ------------------------------------------------------------------ cards */
.card {
  background: var(--mr-surface); border: 1px solid var(--mr-line);
  border-radius: var(--mr-radius); box-shadow: var(--mr-shadow);
}
.card.pad { padding: 16px; }
.block { margin-bottom: 24px; }
.block-head { display: flex; align-items: baseline; gap: 10px; margin: 0 0 10px; }
.block-head h2 { font-size: 17px; }
.page-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 16px; flex-wrap: wrap; margin-bottom: 18px;
}
.page-head h2 { font-size: 22px; }
.stack { display: grid; gap: 12px; }
.grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
.list > .row { border-bottom: 1px solid var(--mr-line); }
.list > .row:last-child { border-bottom: 0; }
.row { display: flex; align-items: center; gap: 12px; padding: 12px 16px; }
.row-main { flex: 1; min-width: 0; display: grid; }
.row-main small, .row-side small { color: var(--mr-muted); font-size: 12px; }
.row-side { text-align: right; display: grid; }

.metrics {
  display: grid; grid-template-columns: repeat(4, 1fr);
  margin-bottom: 24px; overflow: hidden;
}
.metric { padding: 14px 16px; display: grid; gap: 2px; border-right: 1px solid var(--mr-line); }
.metric:last-child { border-right: 0; }
.metric span { font-size: 12px; color: var(--mr-muted); }
.metric strong { font-size: 22px; font-weight: 500; }
.metric.attention strong { color: var(--mr-warn); }

.empty { text-align: center; padding: 40px 20px; border-style: dashed; box-shadow: none; }
.empty ha-icon { --mdc-icon-size: 36px; color: var(--mr-muted); }
.empty h3 { margin: 10px 0 4px; font-size: 16px; }

/* ----------------------------------------------------------------- badges */
.badges { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.badge {
  display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 600; letter-spacing: .02em;
  background: color-mix(in srgb, var(--mr-ink) 10%, transparent); color: var(--mr-ink);
}
.badge.pending { background: color-mix(in srgb, var(--mr-warn) 18%, transparent); color: var(--mr-warn); }
.badge.partial { background: color-mix(in srgb, var(--mr-info) 18%, transparent); color: var(--mr-info); }
.badge.taken { background: color-mix(in srgb, var(--mr-ok) 18%, transparent); color: var(--mr-ok); }
.badge.skipped { background: color-mix(in srgb, var(--mr-ink) 10%, transparent); color: var(--mr-muted); }
.badge.missed { background: color-mix(in srgb, var(--mr-danger) 16%, transparent); color: var(--mr-danger); }
.badge.snoozed { background: color-mix(in srgb, var(--mr-info) 14%, transparent); color: var(--mr-info); }

.warning-row { display: flex; align-items: center; gap: 10px; }
.warning-row ha-icon { --mdc-icon-size: 20px; flex: 0 0 auto; }
.warning-row.warn ha-icon { color: var(--mr-warn); }
.warning-row.error ha-icon { color: var(--mr-danger); }
.hint {
  display: flex; align-items: center; gap: 8px; margin: 10px 0 0;
  padding: 8px 10px; border-radius: 8px; font-size: 13px; color: var(--mr-muted);
  background: color-mix(in srgb, var(--mr-accent) 8%, transparent);
}
.hint ha-icon { --mdc-icon-size: 18px; }

/* ---------------------------------------------------------------- tickets */
.ticket { padding: 16px; }
.ticket.highlight, .medication.highlight, .package.highlight {
  border-color: var(--mr-accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--mr-accent) 35%, transparent);
}
.ticket-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.ticket-head h3 { font-size: 17px; }
.ticket-head p { font-size: 12px; }
.ticket-time { font-size: 20px; font-weight: 500; color: var(--mr-accent); white-space: nowrap; }
.doses { margin: 14px 0; border: 1px solid var(--mr-line); border-radius: 8px; overflow: hidden; }
.dose {
  display: flex; align-items: center; gap: 12px; padding: 10px 12px;
  border-bottom: 1px solid var(--mr-line);
}
.dose:last-child { border-bottom: 0; }
.dose.done { opacity: .55; }
.dose > input[type=checkbox] { width: 18px; height: 18px; accent-color: var(--mr-accent); flex: 0 0 auto; }
.dose-main { flex: 1; min-width: 0; display: grid; }
.dose-main small { font-size: 12px; color: var(--mr-muted); }
.dose-main small.plan { color: var(--mr-accent); }
.dose-amount { display: flex; align-items: center; gap: 6px; }
.dose-amount input {
  width: 78px; text-align: right; padding: 7px 8px; border-radius: 6px;
  border: 1px solid var(--mr-line); background: var(--mr-bg);
}
.ticket-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.chips { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.chip-label { font-size: 12px; color: var(--mr-muted); }
button.chip, .chip {
  display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px;
  border-radius: 999px; border: 1px solid var(--mr-line);
  background: var(--mr-surface); font-size: 12px;
}
button.chip:hover { background: color-mix(in srgb, var(--mr-ink) 6%, var(--mr-surface)); }
button.chip.on { background: var(--mr-accent); color: var(--text-primary-color, #fff); border-color: transparent; }
.chip.static { background: color-mix(in srgb, var(--mr-accent) 10%, transparent); border-color: transparent; }
.chip-input {
  padding: 4px 8px; border-radius: 999px; border: 1px solid var(--mr-line);
  background: var(--mr-surface); font-size: 12px;
}

/* ------------------------------------------------------------ medications */
.medication { padding: 16px; display: flex; flex-direction: column; }
.medication.is-low { border-color: color-mix(in srgb, var(--mr-warn) 55%, var(--mr-line)); }
.med-head { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.med-head h3 { font-size: 17px; }
.med-head p { font-size: 12px; }
.stock-value { display: flex; align-items: baseline; gap: 6px; margin-top: 14px; flex-wrap: wrap; }
.stock-value strong { font-size: 28px; font-weight: 500; }
.stock-value span { color: var(--mr-muted); }
.stock-value small { margin-left: auto; font-size: 12px; }
.bar { height: 6px; border-radius: 999px; background: var(--mr-line); overflow: hidden; margin: 8px 0 6px; }
.bar i { display: block; height: 100%; background: var(--mr-accent); }
.is-low .bar i { background: var(--mr-warn); }
.packages { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--mr-line); display: grid; gap: 8px; }
.packages-head { display: flex; justify-content: space-between; font-size: 12px; }
.package {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border: 1px solid var(--mr-line); border-radius: 8px;
}
.package > ha-icon { --mdc-icon-size: 20px; color: var(--mr-muted); flex: 0 0 auto; }
.package-main { flex: 1; min-width: 0; display: grid; }
.package-main strong { font-size: 13px; font-weight: 500; }
.package-main small { font-size: 11px; }
.package.empty { opacity: .55; }
.package.expired { border-color: color-mix(in srgb, var(--mr-danger) 55%, var(--mr-line)); }
.package-actions { display: flex; gap: 2px; }
.card-actions {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--mr-line);
}

/* --------------------------------------------------------------- regimens */
.regimen { display: flex; gap: 16px; align-items: flex-start; padding: 16px; }
.regimen.inactive { opacity: .65; }
.regimen-main { flex: 1; min-width: 0; display: grid; gap: 4px; }
.regimen-main h3 { font-size: 17px; }
.regimen-main small { font-size: 12px; }
.schedule { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.schedule ha-icon { --mdc-icon-size: 17px; }
.regimen-actions { display: flex; gap: 2px; }

/* ---------------------------------------------------------------- history */
.adherence { display: grid; gap: 4px; margin-bottom: 12px; }
.adherence strong { font-weight: 500; }
.export { margin-bottom: 12px; display: grid; gap: 8px; }
.export-fields { display: grid; grid-template-columns: 180px 180px 1fr; gap: 12px; align-items: end; }
.export-actions { display: flex; gap: 8px; }
.filters { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.search {
  flex: 1; min-width: 200px; padding: 9px 12px; border-radius: 8px;
  border: 1px solid var(--mr-line); background: var(--mr-surface);
}
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 780px; }
th, td { text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--mr-line); vertical-align: top; }
th {
  font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--mr-muted); font-weight: 600; white-space: nowrap;
}
td small { display: block; font-size: 11px; }
tbody tr:last-child td { border-bottom: 0; }

/* ----------------------------------------------------------------- modals */
.modal-backdrop {
  position: fixed; inset: 0; z-index: 30; display: grid; place-items: center;
  padding: 20px; background: rgba(0, 0, 0, .5);
}
.modal {
  width: min(640px, 100%); max-height: 92vh; overflow: auto;
  background: var(--mr-surface); border-radius: var(--mr-radius);
  box-shadow: 0 12px 40px rgba(0, 0, 0, .35);
}
.modal.wide { width: min(880px, 100%); }
.modal-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 16px 20px; border-bottom: 1px solid var(--mr-line);
  position: sticky; top: 0; background: var(--mr-surface); z-index: 1;
}
.modal-head h2 { font-size: 19px; }
.modal form, .data-management, .code-content { padding: 20px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.field.full { grid-column: 1 / -1; }
.field > span { font-size: 12px; font-weight: 500; color: var(--mr-muted); }
.field small { font-size: 11px; line-height: 1.35; }
.field input, .field select, .field textarea,
.dose-row input, .dose-row select {
  width: 100%; padding: 10px 12px; border-radius: 8px;
  border: 1px solid var(--mr-line); background: var(--mr-bg); color: var(--mr-ink);
}
.field textarea { resize: vertical; }
.field.note {
  background: color-mix(in srgb, var(--mr-accent) 8%, transparent);
  border-radius: 8px; padding: 10px 12px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
.item-editor { display: grid; gap: 8px; }
.dose-row { display: grid; grid-template-columns: 2fr 1fr auto; gap: 8px; align-items: center; }
.add-dose { justify-self: start; }
.week-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.week-row {
  display: grid; grid-template-columns: auto 74px 1fr; gap: 8px; align-items: center;
  border: 1px solid var(--mr-line); border-radius: 8px; padding: 6px 10px;
}
.week-row input[type=checkbox] { width: 17px; height: 17px; accent-color: var(--mr-accent); }
.week-row b { font-size: 12px; font-weight: 500; }
.week-row input[type=text] {
  width: 100%; padding: 7px 9px; border-radius: 6px;
  border: 1px solid var(--mr-line); background: var(--mr-bg);
}
.inline-fields { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
details.advanced { border: 1px solid var(--mr-line); border-radius: 8px; padding: 10px 12px; }
details.advanced summary { cursor: pointer; font-size: 12px; font-weight: 500; color: var(--mr-muted); }
details.advanced .inline-fields { margin-top: 12px; }
.data-management { display: grid; gap: 12px; }
.data-management > section { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.data-management h3 { font-size: 15px; margin-bottom: 4px; }
.code-content { text-align: center; }
.code-content img {
  display: block; width: min(220px, 70%); aspect-ratio: 1; margin: 14px auto;
  background: #fff; padding: 8px; border-radius: 8px;
}
.code-content code {
  display: inline-block; padding: 8px 14px; border-radius: 8px; font-size: 16px;
  font-weight: 700; letter-spacing: .12em;
  background: color-mix(in srgb, var(--mr-ink) 7%, transparent);
}
.code-content p { margin-top: 12px; font-size: 13px; }
.code-content .modal-actions { justify-content: center; }

/* ------------------------------------------------------------ misc states */
.loading { min-height: 50vh; display: grid; place-content: center; text-align: center; gap: 6px; }
.loader {
  width: 40px; height: 40px; margin: 0 auto 8px; border-radius: 50%;
  border: 3px solid var(--mr-line); border-top-color: var(--mr-accent);
  animation: mr-spin .8s linear infinite;
}
@keyframes mr-spin { to { transform: rotate(360deg); } }
.toast {
  position: fixed; right: 20px; bottom: 20px; z-index: 50; max-width: 420px;
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  border-radius: 8px; box-shadow: 0 8px 24px rgba(0, 0, 0, .3);
  background: var(--mr-ink); color: var(--mr-surface);
  animation: mr-toast .2s ease;
}
.toast.error { background: var(--mr-danger); color: #fff; }
@keyframes mr-toast { from { transform: translateY(12px); opacity: 0; } }

/* --------------------------------------------------------------- responsive */
@media (max-width: 900px) {
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .metric:nth-child(2) { border-right: 0; }
  .metric:nth-child(-n+2) { border-bottom: 1px solid var(--mr-line); }
  .export-fields { grid-template-columns: 1fr 1fr; }
  .export-fields > .field:last-child { grid-column: 1 / -1; }
}
@media (max-width: 700px) {
  header { flex-wrap: wrap; padding: 12px; }
  .brand p { display: none; }
  .header-actions { width: 100%; }
  .header-actions button.ghost span, .header-actions button.primary span { display: none; }
  .header-actions button.ghost, .header-actions button.primary { padding: 9px 12px; }
  main { padding: 16px 12px 40px; }
  nav { padding: 6px 12px 0; }
  nav button span { font-size: 13px; }
  .grid { grid-template-columns: 1fr; }
  .form-grid, .inline-fields, .week-grid { grid-template-columns: 1fr; }
  .field.full { grid-column: auto; }
  .ticket-actions > .primary { width: 100%; }
  .modal-backdrop { padding: 0; }
  .modal, .modal.wide { width: 100%; height: 100%; max-height: 100%; border-radius: 0; }
  .data-management > section { flex-direction: column; align-items: stretch; }
  .export-fields { grid-template-columns: 1fr; }
  footer { flex-direction: column; gap: 4px; }
  .toast { left: 12px; right: 12px; bottom: 12px; max-width: none; }
}
`;
