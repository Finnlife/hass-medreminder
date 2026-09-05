/**
 * Demo data for the screenshot harness.
 *
 * Every timestamp is derived from one frozen reference point so a capture run
 * produces byte-identical images as long as the interface itself does not
 * change. The capture script pins the browser clock to the same instant.
 */
export const FROZEN_NOW = "2026-09-02T13:20:00+02:00";

const base = new Date(FROZEN_NOW);
const minutes = (value) => new Date(base.getTime() + value * 60000).toISOString();
const days = (value) =>
  new Date(base.getTime() + value * 86400000).toISOString().slice(0, 10);

export function buildState() {
  return {
    server_time: base.toISOString(),
    medications: [
      {
        id: "med-magnesium", name: "Magnesium", manufacturer: "Verla",
        barcode: "04199543", form: "Kapsel", strength: "400 mg", unit: "Kapseln",
        stock: 34, stock_mode: "packages", low_stock_threshold: 10,
        notes: "Abends mit reichlich Wasser einnehmen.", scan_code: "med23456",
        daily_consumption: 1, days_of_supply: 34,
      },
      {
        id: "med-vitamin-d", name: "Vitamin D3", manufacturer: "Dekristol",
        barcode: "04384679", form: "Tropfen", strength: "1000 IE", unit: "Tropfen",
        stock: 6, stock_mode: "packages", low_stock_threshold: 20,
        notes: "", scan_code: "med23457",
        daily_consumption: 2, days_of_supply: 3,
      },
      {
        id: "med-omega", name: "Omega 3", manufacturer: "Norsan",
        barcode: "07721048", form: "Kapsel", strength: "1000 mg", unit: "Kapseln",
        stock: 88, stock_mode: "packages", low_stock_threshold: 15,
        notes: "", scan_code: "med23458",
        daily_consumption: 2, days_of_supply: 44,
      },
    ],
    packages: [
      {
        id: "pkg-mag-1", medication_id: "med-magnesium", nickname: "Apollo",
        lot_number: "L-8842", expires_on: days(430), external_code: "",
        initial_quantity: 60, remaining_quantity: 34,
        created_at: minutes(-60 * 24 * 40), scan_code: "med2345A",
      },
      {
        id: "pkg-vit-1", medication_id: "med-vitamin-d", nickname: "Comet",
        lot_number: "", expires_on: days(12), external_code: "",
        initial_quantity: 30, remaining_quantity: 6,
        created_at: minutes(-60 * 24 * 90), scan_code: "med2345B",
      },
      {
        id: "pkg-vit-2", medication_id: "med-vitamin-d", nickname: "Daisy",
        lot_number: "B-11", expires_on: days(-4), external_code: "",
        initial_quantity: 30, remaining_quantity: 0,
        created_at: minutes(-60 * 24 * 200), scan_code: "med2345C",
      },
      {
        id: "pkg-ome-1", medication_id: "med-omega", nickname: "Nova",
        lot_number: "N-2291", expires_on: days(300), external_code: "",
        initial_quantity: 120, remaining_quantity: 88,
        created_at: minutes(-60 * 24 * 20), scan_code: "med2345D",
      },
    ],
    regimens: [
      {
        id: "reg-morning", name: "Morgens", active: true,
        items: [
          { medication_id: "med-vitamin-d", dose: 2 },
          { medication_id: "med-omega", dose: 2 },
        ],
        schedule: {
          type: "weekly",
          days: {
            0: ["08:00"], 1: ["08:00"], 2: ["08:00"], 3: ["08:00"],
            4: ["08:00"], 5: ["09:30"], 6: ["09:30"],
          },
        },
        notify_services: ["notify.mobile_app_handy"], scripts: [],
        repeat_minutes: 30, reminder_window_minutes: 180,
        auto_miss_after_minutes: 720,
        instructions: "Nach dem Frühstück einnehmen.",
      },
      {
        id: "reg-evening", name: "Abends", active: true,
        items: [{ medication_id: "med-magnesium", dose: 1 }],
        schedule: { type: "weekly", days: { 0: ["21:00"], 2: ["21:00"], 4: ["21:00"] } },
        notify_services: ["notify.mobile_app_handy"], scripts: [],
        repeat_minutes: 45, reminder_window_minutes: 120,
        auto_miss_after_minutes: 0, instructions: "",
      },
      {
        id: "reg-interval", name: "Vitamin-B-Kur", active: false,
        items: [{ medication_id: "med-omega", dose: 1 }],
        schedule: {
          type: "interval", every_days: 3, start_date: days(-9), time: "12:00",
        },
        notify_services: [], scripts: ["script.licht_blinken"],
        repeat_minutes: 60, reminder_window_minutes: 0,
        auto_miss_after_minutes: 0, instructions: "",
      },
    ],
    occurrences: [
      {
        id: "occ-open-1", regimen_id: "reg-morning", regimen_name: "Morgens",
        unplanned: false, ad_hoc: false, reason: "", reference: "",
        scheduled_at: minutes(-95), status: "pending", taken_at: null,
        snoozed_until: null, last_reminded_at: minutes(-30), reminders_sent: 3,
        completed_by: null, scan_code: "med2345E",
        items: [
          {
            medication_id: "med-vitamin-d", planned_dose: 2, taken_dose: 0,
            allocations: [],
            package_plan: [{
              package_id: "pkg-vit-1", nickname: "Comet", lot_number: "",
              expires_on: days(12), amount: 2, taken_at: null,
            }],
          },
          {
            medication_id: "med-omega", planned_dose: 2, taken_dose: 0,
            allocations: [],
            package_plan: [{
              package_id: "pkg-ome-1", nickname: "Nova", lot_number: "N-2291",
              expires_on: days(300), amount: 2, taken_at: null,
            }],
          },
        ],
      },
      {
        id: "occ-adhoc", regimen_id: null, regimen_name: "Sport",
        unplanned: false, ad_hoc: true, reason: "Sport", reference: "gym-2026-09-02",
        scheduled_at: minutes(-12), status: "pending", taken_at: null,
        snoozed_until: null, last_reminded_at: minutes(-12), reminders_sent: 1,
        completed_by: null, scan_code: "med2345F",
        reminder: {
          notify_services: ["notify.mobile_app_handy"], scripts: [],
          repeat_minutes: 30, reminder_window_minutes: 180,
          auto_miss_after_minutes: 0,
        },
        items: [{
          medication_id: "med-magnesium", planned_dose: 2, taken_dose: 0,
          allocations: [],
          package_plan: [{
            package_id: "pkg-mag-1", nickname: "Apollo", lot_number: "L-8842",
            expires_on: days(430), amount: 2, taken_at: null,
          }],
        }],
      },
      {
        id: "occ-partial", regimen_id: "reg-evening", regimen_name: "Abends",
        unplanned: false, ad_hoc: false, reason: "", reference: "",
        scheduled_at: minutes(45), status: "partial", taken_at: null,
        snoozed_until: minutes(70), last_reminded_at: null, reminders_sent: 0,
        completed_by: null, scan_code: "med23460",
        items: [{
          medication_id: "med-magnesium", planned_dose: 2, taken_dose: 1,
          allocations: [],
          package_plan: [{
            package_id: "pkg-mag-1", nickname: "Apollo", lot_number: "L-8842",
            expires_on: days(430), amount: 1, taken_at: null,
          }],
        }],
      },
      {
        id: "occ-done-1", regimen_id: "reg-morning", regimen_name: "Morgens",
        unplanned: false, ad_hoc: false, reason: "", reference: "",
        scheduled_at: minutes(-60 * 24 - 5), status: "taken",
        taken_at: minutes(-60 * 24), snoozed_until: null,
        last_reminded_at: null, reminders_sent: 1, completed_by: "user",
        scan_code: "med23461",
        items: [{
          medication_id: "med-omega", planned_dose: 2, taken_dose: 2,
          allocations: [{
            package_id: "pkg-ome-1", nickname: "Nova", lot_number: "N-2291",
            expires_on: days(300), amount: 2, taken_at: minutes(-60 * 24),
          }],
        }],
      },
      {
        id: "occ-done-2", regimen_id: "reg-evening", regimen_name: "Abends",
        unplanned: false, ad_hoc: false, reason: "", reference: "",
        scheduled_at: minutes(-60 * 40), status: "taken",
        taken_at: minutes(-60 * 40 + 18), snoozed_until: null,
        last_reminded_at: null, reminders_sent: 2, completed_by: "user",
        scan_code: "med23462",
        items: [{
          medication_id: "med-magnesium", planned_dose: 1, taken_dose: 1,
          allocations: [{
            package_id: "pkg-mag-1", nickname: "Apollo", lot_number: "L-8842",
            expires_on: days(430), amount: 1, taken_at: minutes(-60 * 40 + 18),
          }],
        }],
      },
      {
        id: "occ-missed", regimen_id: "reg-morning", regimen_name: "Morgens",
        unplanned: false, ad_hoc: false, reason: "", reference: "",
        scheduled_at: minutes(-60 * 52), status: "missed", taken_at: null,
        snoozed_until: null, last_reminded_at: null, reminders_sent: 4,
        completed_by: null, scan_code: "med23463",
        items: [{
          medication_id: "med-vitamin-d", planned_dose: 2, taken_dose: 0,
          allocations: [],
        }],
      },
      {
        id: "occ-skipped", regimen_id: "reg-evening", regimen_name: "Abends",
        unplanned: false, ad_hoc: false, reason: "", reference: "",
        scheduled_at: minutes(-60 * 64), status: "skipped",
        taken_at: minutes(-60 * 63), snoozed_until: null, last_reminded_at: null,
        reminders_sent: 1, completed_by: "user", scan_code: "med23464",
        items: [{
          medication_id: "med-magnesium", planned_dose: 1, taken_dose: 0,
          allocations: [],
        }],
      },
      {
        id: "occ-unplanned", regimen_id: null, regimen_name: null,
        unplanned: true, ad_hoc: false, reason: "", reference: "",
        note: "Kopfschmerzen", scheduled_at: minutes(-60 * 76), status: "taken",
        taken_at: minutes(-60 * 76), snoozed_until: null, last_reminded_at: null,
        reminders_sent: 0, completed_by: "user", scan_code: "med23465",
        items: [{
          medication_id: "med-magnesium", planned_dose: 2, taken_dose: 2,
          allocations: [{
            package_id: "pkg-mag-1", nickname: "Apollo", lot_number: "L-8842",
            expires_on: days(430), amount: 2, taken_at: minutes(-60 * 76),
          }],
        }],
      },
    ],
    upcoming: [
      {
        regimen_id: "reg-evening", regimen_name: "Abends",
        scheduled_at: minutes(460),
        items: [{
          medication_id: "med-magnesium", medication_name: "Magnesium", dose: 1,
        }],
      },
      {
        regimen_id: "reg-morning", regimen_name: "Morgens",
        scheduled_at: minutes(1120),
        items: [
          { medication_id: "med-vitamin-d", medication_name: "Vitamin D3", dose: 2 },
          { medication_id: "med-omega", medication_name: "Omega 3", dose: 2 },
        ],
      },
    ],
    adherence: {
      window_days: 30, total: 46, taken: 39, partial: 3, skipped: 2, missed: 2,
      rate: 88,
    },
    notify_services: ["notify.mobile_app_handy", "notify.persistent_notification"],
    scripts: ["script.licht_blinken"],
  };
}
