(function () {
  const bodyEl = document.getElementById("planTableBody");
  const metaEl = document.getElementById("planTopMeta");
  const summaryEl = document.getElementById("planSummary");
  const tableWrapEl = document.querySelector(".plan-table-wrap");
  const centerDateEl = document.getElementById("planCenterDate");
  const centerBtn = document.getElementById("planCenterBtn");
  const reloadBtn = document.getElementById("planReloadBtn");
  const settingsBtn = document.getElementById("planSettingsBtn");
  const settingsPanel = document.getElementById("planSettingsPanel");
  const seedBtn = document.getElementById("planSeedBtn");
  const settingsStatusEl = document.getElementById("planSettingsStatus");
  const paceDrawer = document.getElementById("planPaceDrawer");
  const paceDrawerTab = document.getElementById("planPaceDrawerTab");
  const paceDrawerClose = document.getElementById("planPaceDrawerClose");
  const paceBackdrop = document.getElementById("planPaceBackdrop");
  const paceStatusEl = document.getElementById("planPaceStatus");
  const marathonGoalInputEl = document.getElementById("planMarathonGoalInput");
  const marathonGoalSetBtn = document.getElementById("planMarathonGoalSetBtn");
  const paceDistanceSelectEl = document.getElementById("planPaceDistanceSelect");
  const paceTimeInputEl = document.getElementById("planPaceTimeInput");
  const paceCalcBtn = document.getElementById("planPaceCalcBtn");
  const paceDerivedGoalEl = document.getElementById("planPaceDerivedGoal");
  const paceSetDerivedBtn = document.getElementById("planPaceSetDerivedBtn");
  const raceEquivalencyListEl = document.getElementById("planRaceEquivalencyList");
  const trainingPacesListEl = document.getElementById("planTrainingPacesList");

  let runTypeOptions = [""];
  let pendingFocus = { date: "", field: "distance" };
  let rowsByDate = new Map();
  let renderedRows = [];
  let loadedStartDate = "";
  let loadedEndDate = "";
  let loadedTimezone = "";
  let refreshFromDate = "";
  let refreshTimer = null;
  let refreshInFlight = false;
  let refreshQueuedAfterFlight = false;
  let pendingPlanSaves = new Map();
  let saveFlushTimer = null;
  let saveFlushInFlight = false;
  let saveFlushQueuedAfterFlight = false;
  let saveMaxNextFocusDate = "";
  let hasLoadedPlanMeta = false;
  let paceCurrentGoal = "5:00:00";
  let paceDerivedGoal = "";
  const PLAN_INITIAL_FUTURE_DAYS = 365;
  const PLAN_APPEND_FUTURE_DAYS = 56;

  const runTypeHotkeys = {
    e: "Easy",
    r: "Recovery",
    s: "SOS",
    l: "Long Road",
    m: "Long Moderate",
    t: "Long Trail",
    x: "Race",
    h: "HIIT",
    "1": "LT1",
    "2": "LT2",
  };

  const workoutPresetOptions = [
    "2E + 3x2T w/2:00 jog + 2E (Hansons strength)",
    "2E + 6x800m @5k w/400m jog + 2E (Hansons speed)",
    "1.5E + 10x400m @5k w/400m jog + 1.5E (Hansons speed)",
    "2E + 20T + 2E (Jack Daniels tempo)",
    "2E + 5x1k @I w/3:00 jog + 2E (Jack Daniels interval)",
    "2E + 6x200m @R w/200m jog + 2E (Jack Daniels repetition)",
    "15WU + 4x4min @LT2 w/3min easy + 10CD (Norwegian 4x4)",
    "15WU + 5x4min @LT2 w/2min easy + 10CD (Norwegian variant)",
    "15WU + 3x8min @LT1 w/2min easy + 10CD (Norwegian threshold)",
  ];
  const workoutPresetMenuWidthCh = Math.max(
    44,
    workoutPresetOptions.reduce((max, item) => Math.max(max, String(item || "").length), 0) + 3,
  );
  let workoutMenuHandlersBound = false;

  function normalizeRunType(value) {
    return String(value || "").trim().toLowerCase();
  }

  function isSosRunType(value) {
    return normalizeRunType(value) === "sos";
  }

  function bindWorkoutMenuHandlers() {
    if (workoutMenuHandlersBound) return;
    workoutMenuHandlersBound = true;
    document.addEventListener("click", (event) => {
      const target = event.target;
      if (target instanceof Element && target.closest(".plan-workout-field")) return;
      for (const field of document.querySelectorAll(".plan-workout-field")) {
        field.dataset.open = "0";
      }
      for (const menu of document.querySelectorAll(".plan-workout-menu")) {
        if (!(menu instanceof HTMLElement)) continue;
        menu.hidden = true;
      }
    });
  }

  function setWorkoutMenuOpen(field, menu, nextOpen) {
    if (!(field instanceof HTMLElement) || !(menu instanceof HTMLElement)) return;
    field.dataset.open = nextOpen ? "1" : "0";
    menu.hidden = !nextOpen;
  }

  function asNumber(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function formatMiles(value, decimals) {
    const parsed = asNumber(value);
    return parsed === null ? "--" : parsed.toFixed(decimals);
  }

  function formatPct(value) {
    const parsed = asNumber(value);
    return parsed === null ? "--" : `${Math.round(parsed * 100)}%`;
  }

  function formatRatio(value, decimals) {
    const parsed = asNumber(value);
    return parsed === null ? "--" : parsed.toFixed(decimals);
  }

  function formatSigned(value, decimals) {
    const parsed = asNumber(value);
    if (parsed === null) return "--";
    const fixed = parsed.toFixed(decimals);
    return parsed > 0 ? `+${fixed}` : fixed;
  }

  function formatPercentRatio(value) {
    const parsed = asNumber(value);
    if (parsed === null) return "--";
    return `${Math.round(parsed * 100)}%`;
  }

  function formatSessionValue(value) {
    if (Math.abs(value - Math.round(value)) < 1e-9) {
      return String(Math.round(value));
    }
    return value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  }

  function metricBandClass(band) {
    const key = String(band || "neutral").toLowerCase();
    if (key === "easy" || key === "good" || key === "caution" || key === "hard") {
      return `metric-${key}`;
    }
    return "metric-neutral";
  }

  function wowBandFromValue(value) {
    const parsed = asNumber(value);
    if (parsed === null) return "metric-neutral";
    if (parsed < 0) return "metric-easy";
    if (parsed <= 0.08) return "metric-good";
    if (parsed <= 0.12) return "metric-caution";
    return "metric-hard";
  }

  function miT30BandFromValue(value) {
    const parsed = asNumber(value);
    if (parsed === null) return "metric-neutral";
    const rounded = Number(parsed.toFixed(1));
    if (rounded < 0.8) return "metric-easy";
    if (rounded <= 1.4) return "metric-good";
    if (rounded <= 1.8) return "metric-caution";
    return "metric-hard";
  }

  const DISTANCE_COLOR_STOPS = [
    { miles: 4.50, rgb: [201, 207, 218] }, // light gray (min)
    { miles: 6.15, rgb: [66, 196, 117] }, // green (mid)
    { miles: 13.10, rgb: [132, 88, 206] }, // purple (max)
  ];

  function interpolateRgb(a, b, ratio) {
    const next = Math.max(0, Math.min(1, Number(ratio || 0)));
    return [
      Math.round(a[0] + ((b[0] - a[0]) * next)),
      Math.round(a[1] + ((b[1] - a[1]) * next)),
      Math.round(a[2] + ((b[2] - a[2]) * next)),
    ];
  }

  function distanceColorForMiles(value) {
    const miles = asNumber(value);
    if (miles === null) return "";
    const first = DISTANCE_COLOR_STOPS[0];
    const last = DISTANCE_COLOR_STOPS[DISTANCE_COLOR_STOPS.length - 1];
    if (miles <= first.miles) return `rgb(${first.rgb.join(" ")})`;
    if (miles >= last.miles) return `rgb(${last.rgb.join(" ")})`;
    for (let idx = 1; idx < DISTANCE_COLOR_STOPS.length; idx += 1) {
      const left = DISTANCE_COLOR_STOPS[idx - 1];
      const right = DISTANCE_COLOR_STOPS[idx];
      if (miles > right.miles) continue;
      const span = right.miles - left.miles;
      const ratio = span > 0 ? (miles - left.miles) / span : 0;
      const rgb = interpolateRgb(left.rgb, right.rgb, ratio);
      return `rgb(${rgb.join(" ")})`;
    }
    return `rgb(${last.rgb.join(" ")})`;
  }

  function makeCell(text, className) {
    const td = document.createElement("td");
    td.textContent = text;
    if (className) td.className = className;
    return td;
  }

  function rowAt(rows, index) {
    if (index < 0 || index >= rows.length) return null;
    return rows[index];
  }

  function parseIsoDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || "").trim());
    if (!match) return null;
    const year = Number.parseInt(match[1], 10);
    const month = Number.parseInt(match[2], 10);
    const day = Number.parseInt(match[3], 10);
    if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
    const date = new Date(Date.UTC(year, month - 1, day));
    if (
      date.getUTCFullYear() !== year ||
      date.getUTCMonth() !== month - 1 ||
      date.getUTCDate() !== day
    ) {
      return null;
    }
    return date;
  }

  function formatIsoDate(date) {
    const year = String(date.getUTCFullYear());
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function todayIsoLocal() {
    const today = new Date();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");
    return `${today.getFullYear()}-${month}-${day}`;
  }

  function addDaysIso(value, days) {
    const parsed = parseIsoDate(value);
    if (!parsed) return "";
    const shifted = new Date(parsed.getTime());
    shifted.setUTCDate(shifted.getUTCDate() + Number(days || 0));
    return formatIsoDate(shifted);
  }

  function isIsoDateString(value) {
    return parseIsoDate(value) !== null;
  }

  function loadCachedRunTypeOptions() {
    try {
      const raw = window.sessionStorage.getItem("plan.run_type_options");
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed) || parsed.length === 0) return;
      runTypeOptions = parsed.map((item) => String(item || ""));
      hasLoadedPlanMeta = true;
    } catch (_err) {
      // Ignore cache parse errors.
    }
  }

  function cacheRunTypeOptions(options) {
    try {
      window.sessionStorage.setItem("plan.run_type_options", JSON.stringify(options || []));
    } catch (_err) {
      // Ignore storage errors.
    }
  }

  function setPaceStatus(message, tone) {
    if (!paceStatusEl) return;
    paceStatusEl.textContent = String(message || "");
    if (tone === "ok" || tone === "error") {
      paceStatusEl.dataset.tone = tone;
      return;
    }
    paceStatusEl.dataset.tone = "neutral";
  }

  function setPaceDrawerOpen(nextOpen) {
    if (!(paceDrawer instanceof HTMLElement)) return;
    paceDrawer.classList.toggle("open", !!nextOpen);
    paceDrawer.setAttribute("aria-hidden", nextOpen ? "false" : "true");
    document.body.classList.toggle("plan-pace-open", !!nextOpen);
    if (paceBackdrop instanceof HTMLElement) {
      paceBackdrop.classList.toggle("open", !!nextOpen);
      paceBackdrop.setAttribute("aria-hidden", nextOpen ? "false" : "true");
    }
  }

  function paceSetButtonBusy(buttonEl, isBusy, busyLabel) {
    if (!(buttonEl instanceof HTMLElement)) return;
    if (isBusy) {
      buttonEl.dataset.originalLabel = buttonEl.textContent || "";
      buttonEl.textContent = String(busyLabel || "Saving...");
      buttonEl.setAttribute("disabled", "disabled");
      return;
    }
    const original = String(buttonEl.dataset.originalLabel || "").trim();
    if (original) buttonEl.textContent = original;
    buttonEl.removeAttribute("disabled");
  }

  function makePaceItem(labelText, valueText) {
    const row = document.createElement("div");
    row.className = "plan-pace-item";
    const label = document.createElement("span");
    label.className = "plan-pace-item-label";
    label.textContent = String(labelText || "--");
    const value = document.createElement("span");
    value.className = "plan-pace-item-value";
    value.textContent = String(valueText || "--");
    row.appendChild(label);
    row.appendChild(value);
    return row;
  }

  function renderPaceGrid(targetEl, rows) {
    if (!(targetEl instanceof HTMLElement)) return;
    targetEl.textContent = "";
    for (const row of Array.isArray(rows) ? rows : []) {
      if (!row || typeof row !== "object") continue;
      targetEl.appendChild(makePaceItem(row.label, row.time || row.pace));
    }
  }

  function updatePaceDerivedGoalDisplay() {
    if (!(paceDerivedGoalEl instanceof HTMLElement)) return;
    if (paceDerivedGoal) {
      paceDerivedGoalEl.textContent = `Marathon Equivalent: ${paceDerivedGoal}`;
      return;
    }
    paceDerivedGoalEl.textContent = "Marathon Equivalent: --";
  }

  function supportedDistanceFallback() {
    return [
      { value: "1mi", label: "1mi" },
      { value: "2mi", label: "2mi" },
      { value: "5k", label: "5k" },
      { value: "10k", label: "10k" },
      { value: "15k", label: "15k" },
      { value: "10mi", label: "10mi" },
      { value: "hm", label: "HM" },
      { value: "marathon", label: "Marathon" },
    ];
  }

  function setDistanceOptions(options) {
    if (!(paceDistanceSelectEl instanceof HTMLSelectElement)) return;
    const items = Array.isArray(options) && options.length > 0 ? options : supportedDistanceFallback();
    const currentValue = String(paceDistanceSelectEl.value || "10k");
    paceDistanceSelectEl.textContent = "";
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      const value = String(item.value || "").trim();
      if (!value) continue;
      const option = document.createElement("option");
      option.value = value;
      option.textContent = String(item.label || value);
      paceDistanceSelectEl.appendChild(option);
    }
    if (Array.from(paceDistanceSelectEl.options).some((option) => option.value === currentValue)) {
      paceDistanceSelectEl.value = currentValue;
    } else if (Array.from(paceDistanceSelectEl.options).some((option) => option.value === "10k")) {
      paceDistanceSelectEl.value = "10k";
    }
  }

  function applyPaceWorkshopPayload(payload) {
    if (!payload || payload.status !== "ok") return;
    if (marathonGoalInputEl instanceof HTMLInputElement && typeof payload.marathon_goal === "string") {
      paceCurrentGoal = payload.marathon_goal;
      marathonGoalInputEl.value = paceCurrentGoal;
    }
    setDistanceOptions(payload.supported_distances);
    const goalTraining = payload.goal_training && typeof payload.goal_training === "object"
      ? payload.goal_training
      : {};
    renderPaceGrid(trainingPacesListEl, goalTraining.paces);
  }

  async function loadPaceWorkshop() {
    if (!(paceDistanceSelectEl instanceof HTMLSelectElement)) return;
    setPaceStatus("Loading pace workshop...", "neutral");
    updatePaceDerivedGoalDisplay();
    try {
      const response = await fetch("/plan/pace-workshop.json", { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") {
        throw new Error(String((payload && payload.error) || "Failed to load pace workshop"));
      }
      applyPaceWorkshopPayload(payload);
      setPaceStatus("", "neutral");
    } catch (err) {
      setDistanceOptions([]);
      setPaceStatus(String(err && err.message ? err.message : "Failed to load pace workshop"), "error");
    }
  }

  async function saveMarathonGoal(goalText) {
    if (!goalText) return;
    paceSetButtonBusy(marathonGoalSetBtn, true, "Saving...");
    setPaceStatus("Saving marathon goal...", "neutral");
    try {
      const response = await fetch("/plan/pace-workshop/goal", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ marathon_goal: String(goalText || "").trim() }),
      });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") {
        throw new Error(String((payload && payload.error) || "Failed to save marathon goal"));
      }
      applyPaceWorkshopPayload(payload);
      setPaceStatus(`Goal set to ${payload.marathon_goal}`, "ok");
    } catch (err) {
      setPaceStatus(String(err && err.message ? err.message : "Failed to save marathon goal"), "error");
    } finally {
      paceSetButtonBusy(marathonGoalSetBtn, false);
    }
  }

  async function calculatePaces() {
    if (!(paceDistanceSelectEl instanceof HTMLSelectElement) || !(paceTimeInputEl instanceof HTMLInputElement)) return;
    const distance = String(paceDistanceSelectEl.value || "").trim();
    const time = String(paceTimeInputEl.value || "").trim();
    if (!distance || !time) {
      setPaceStatus("Enter race distance and time before calculating.", "error");
      return;
    }
    paceSetButtonBusy(paceCalcBtn, true, "Working...");
    setPaceStatus("Calculating race equivalency and training paces...", "neutral");
    try {
      const response = await fetch("/plan/pace-workshop/calculate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          distance,
          time,
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") {
        throw new Error(String((payload && payload.error) || "Calculation failed"));
      }
      paceDerivedGoal = String(payload.derived_marathon_goal || "");
      updatePaceDerivedGoalDisplay();
      renderPaceGrid(raceEquivalencyListEl, payload.race_equivalency);
      const trainingBlock = payload.training && typeof payload.training === "object" ? payload.training : {};
      renderPaceGrid(trainingPacesListEl, trainingBlock.paces);
      if (paceSetDerivedBtn instanceof HTMLButtonElement) {
        paceSetDerivedBtn.disabled = !paceDerivedGoal;
      }
      setPaceStatus("Calculation complete.", "ok");
    } catch (err) {
      setPaceStatus(String(err && err.message ? err.message : "Calculation failed"), "error");
    } finally {
      paceSetButtonBusy(paceCalcBtn, false);
    }
  }

  function mergeRowsByDate(existingRows, incomingRows) {
    const merged = new Map();
    for (const row of existingRows) {
      if (!row || typeof row !== "object") continue;
      const dateKey = String(row.date || "");
      if (!dateKey) continue;
      merged.set(dateKey, row);
    }
    for (const row of incomingRows) {
      if (!row || typeof row !== "object") continue;
      const dateKey = String(row.date || "");
      if (!dateKey) continue;
      merged.set(dateKey, row);
    }
    const sorted = Array.from(merged.values());
    sorted.sort((a, b) => String(a && a.date ? a.date : "").localeCompare(String(b && b.date ? b.date : "")));
    return sorted;
  }

  function formatDisplayDate(value) {
    const parsed = parseIsoDate(value);
    if (!parsed) return String(value || "--");
    return `${parsed.getUTCMonth() + 1}-${parsed.getUTCDate()}`;
  }

  function weekInfoForDate(value) {
    const date = parseIsoDate(value);
    if (!date) {
      return {
        weekKey: "",
      };
    }
    const mondayOffset = (date.getUTCDay() + 6) % 7;
    const weekStart = new Date(date.getTime());
    weekStart.setUTCDate(weekStart.getUTCDate() - mondayOffset);
    return {
      weekKey: formatIsoDate(weekStart),
    };
  }

  function weekStartIso(value) {
    const parsed = parseIsoDate(value);
    if (!parsed) return "";
    const mondayOffset = (parsed.getUTCDay() + 6) % 7;
    const weekStart = new Date(parsed.getTime());
    weekStart.setUTCDate(weekStart.getUTCDate() - mondayOffset);
    return formatIsoDate(weekStart);
  }

  function monthStartIso(value) {
    const parsed = parseIsoDate(value);
    if (!parsed) return "";
    const monthStart = new Date(parsed.getTime());
    monthStart.setUTCDate(1);
    return formatIsoDate(monthStart);
  }

  function overlapStartForDate(anchorDate, floorDate = "") {
    const weekBoundaryStart = weekStartIso(anchorDate);
    const monthBoundaryStart = monthStartIso(anchorDate);
    let appendStart = "";
    if (isIsoDateString(weekBoundaryStart) && isIsoDateString(monthBoundaryStart)) {
      appendStart = weekBoundaryStart < monthBoundaryStart ? weekBoundaryStart : monthBoundaryStart;
    } else if (isIsoDateString(weekBoundaryStart)) {
      appendStart = weekBoundaryStart;
    } else if (isIsoDateString(monthBoundaryStart)) {
      appendStart = monthBoundaryStart;
    }
    if (!appendStart && isIsoDateString(anchorDate)) {
      appendStart = anchorDate;
    }
    if (isIsoDateString(floorDate) && appendStart < floorDate) {
      appendStart = floorDate;
    }
    return appendStart;
  }

  function parseDistanceExpression(value) {
    const text = String(value || "").trim();
    if (!text) return [];
    const parts = text.replace(/\s+/g, "").split("+");
    const values = [];
    for (const part of parts) {
      if (!part) continue;
      const parsed = Number.parseFloat(part);
      if (!Number.isFinite(parsed) || parsed <= 0) continue;
      values.push(parsed);
    }
    return values;
  }

  function sessionDetailsFromRow(row) {
    const fromDetail = Array.isArray(row && row.planned_sessions_detail) ? row.planned_sessions_detail : [];
    const normalized = [];
    for (let idx = 0; idx < fromDetail.length; idx += 1) {
      const item = fromDetail[idx];
      if (!item || typeof item !== "object") continue;
      const planned = Number.parseFloat(String(item.planned_miles));
      if (!Number.isFinite(planned) || planned <= 0) continue;
      normalized.push({
        ordinal: idx + 1,
        planned_miles: planned,
        run_type: String(item.run_type || ""),
        planned_workout: String(item.planned_workout || item.workout_code || ""),
      });
    }
    if (normalized.length > 0) return normalized;

    const explicit = Array.isArray(row && row.planned_sessions) ? row.planned_sessions : [];
    const fromExplicit = explicit
      .map((value, idx) => ({
        ordinal: idx + 1,
        planned_miles: Number.parseFloat(String(value)),
        run_type: idx === 0 ? String((row && row.run_type) || "") : "",
        planned_workout: "",
      }))
      .filter((item) => Number.isFinite(item.planned_miles) && item.planned_miles > 0);
    if (fromExplicit.length > 0) return fromExplicit;

    const parsed = parseDistanceExpression(row && row.planned_input);
    if (parsed.length > 0) {
      return parsed.map((value, idx) => ({
        ordinal: idx + 1,
        planned_miles: value,
        run_type: idx === 0 ? String((row && row.run_type) || "") : "",
        planned_workout: "",
      }));
    }

    const fallback = Number.parseFloat(String(row && row.planned_miles));
    if (Number.isFinite(fallback) && fallback > 0) {
      return [{ ordinal: 1, planned_miles: fallback, run_type: String((row && row.run_type) || ""), planned_workout: "" }];
    }
    return [{ ordinal: 1, planned_miles: null, run_type: String((row && row.run_type) || ""), planned_workout: "" }];
  }

  function serializeSessionsForApi(sessionDetails) {
    const payload = [];
    for (let idx = 0; idx < sessionDetails.length; idx += 1) {
      const session = sessionDetails[idx];
      if (!session || typeof session !== "object") continue;
      const planned = Number.parseFloat(String(session.planned_miles));
      if (!Number.isFinite(planned) || planned <= 0) continue;
      const runType = String(session.run_type || "").trim();
      const plannedWorkout = String(session.planned_workout || session.workout_code || "").trim();
      const item = {
        ordinal: payload.length + 1,
        planned_miles: planned,
      };
      if (runType) {
        item.run_type = runType;
      }
      if (plannedWorkout) {
        item.planned_workout = plannedWorkout;
      }
      payload.push(item);
    }
    return payload;
  }

  function canonicalSessionPayload(sessions) {
    const normalized = [];
    for (const session of Array.isArray(sessions) ? sessions : []) {
      if (!session || typeof session !== "object") continue;
      const planned = Number.parseFloat(String(session.planned_miles));
      if (!Number.isFinite(planned) || planned <= 0) continue;
      normalized.push({
        planned_miles: Number(planned.toFixed(3)),
        run_type: String(session.run_type || "").trim(),
        planned_workout: String(session.planned_workout || session.workout_code || "").trim(),
      });
    }
    return normalized;
  }

  function payloadsEqualByValue(left, right) {
    const l = JSON.stringify(canonicalSessionPayload(left));
    const r = JSON.stringify(canonicalSessionPayload(right));
    return l === r;
  }

  function applyLocalPlanEdit(dateLocal, sessions, runType) {
    const row = rowsByDate.get(dateLocal);
    if (!row || typeof row !== "object") return;
    const normalizedSessions = canonicalSessionPayload(sessions).map((item, idx) => ({
      ordinal: idx + 1,
      planned_miles: item.planned_miles,
      run_type: item.run_type,
      planned_workout: item.planned_workout,
      workout_code: item.planned_workout,
    }));
    const plannedTotal = normalizedSessions.reduce((sum, item) => sum + Number(item.planned_miles || 0), 0);
    row.run_type = String(runType || row.run_type || "");
    row.planned_sessions_detail = normalizedSessions;
    row.planned_sessions = normalizedSessions.map((item) => Number(item.planned_miles));
    row.planned_miles = Number(plannedTotal.toFixed(3));
    row.planned_input = normalizedSessions.map((item) => formatSessionValue(Number(item.planned_miles))).join("+");
    const actualMiles = asNumber(row.actual_miles) || 0;
    row.day_delta = actualMiles - Number(row.planned_miles || 0);
    rowsByDate.set(dateLocal, row);
  }

  function queuePlanBackgroundRefresh(anchorDate) {
    const anchor = String(anchorDate || "").trim();
    const candidate = overlapStartForDate(anchor, loadedStartDate);
    if (isIsoDateString(candidate)) {
      if (!isIsoDateString(refreshFromDate) || candidate < refreshFromDate) {
        refreshFromDate = candidate;
      }
    }
    if (refreshTimer !== null) {
      clearTimeout(refreshTimer);
    }
    refreshTimer = setTimeout(() => {
      refreshTimer = null;
      void runPlanBackgroundRefresh();
    }, 280);
  }

  async function runPlanBackgroundRefresh() {
    if (refreshInFlight) {
      refreshQueuedAfterFlight = true;
      return;
    }
    if (!isIsoDateString(loadedEndDate)) return;
    const startDate = isIsoDateString(refreshFromDate) ? refreshFromDate : loadedStartDate;
    refreshFromDate = "";
    refreshInFlight = true;
    try {
      await loadPlanRange({
        startDate,
        endDate: loadedEndDate,
        centerDateOverride: centerDateEl.value,
        append: true,
      });
    } finally {
      refreshInFlight = false;
      if (refreshQueuedAfterFlight || isIsoDateString(refreshFromDate)) {
        refreshQueuedAfterFlight = false;
        void runPlanBackgroundRefresh();
      }
    }
  }

  function sessionsFromRunTypeEditors(dateLocal) {
    const runTypeSelects = Array.from(bodyEl.querySelectorAll(`.plan-session-type[data-date="${dateLocal}"]`));
    runTypeSelects.sort(
      (a, b) => Number.parseInt(a.dataset.sessionIndex || "0", 10) - Number.parseInt(b.dataset.sessionIndex || "0", 10),
    );
    if (runTypeSelects.length === 0) return [];
    const fallbackRow = rowsByDate.get(dateLocal);
    const fallbackSessions = sessionDetailsFromRow(fallbackRow);
    const raw = runTypeSelects.map((runTypeSelect, sessionIndex) => {
      const fallbackSession = fallbackSessions[sessionIndex] || {};
      const workoutInput = bodyEl.querySelector(
        `.plan-session-workout[data-date="${dateLocal}"][data-session-index="${sessionIndex}"]`,
      );
      const fallbackWorkout = runTypeSelect.dataset
        ? String(runTypeSelect.dataset.plannedWorkout || fallbackSession.planned_workout || "")
        : String(fallbackSession.planned_workout || "");
      const workoutValue = workoutInput && typeof workoutInput.value === "string"
        ? workoutInput.value
        : fallbackWorkout;
      if (runTypeSelect.dataset) {
        runTypeSelect.dataset.plannedWorkout = String(workoutValue || "");
      }
      return {
        planned_miles: fallbackSession.planned_miles,
        run_type: runTypeSelect && typeof runTypeSelect.value === "string"
          ? runTypeSelect.value
          : String(fallbackSession.run_type || ""),
        planned_workout: workoutValue,
      };
    });
    return serializeSessionsForApi(raw);
  }

  function collectSessionPayloadForDate(dateLocal) {
    const distanceInputs = Array.from(bodyEl.querySelectorAll(`.plan-session-distance[data-date="${dateLocal}"]`));
    distanceInputs.sort(
      (a, b) => Number.parseInt(a.dataset.sessionIndex || "0", 10) - Number.parseInt(b.dataset.sessionIndex || "0", 10),
    );
    if (distanceInputs.length === 0) {
      return sessionsFromRunTypeEditors(dateLocal);
    }
    const raw = distanceInputs.map((distanceInput) => {
      const sessionIndex = Number.parseInt(distanceInput.dataset.sessionIndex || "0", 10);
      const runTypeSelect = bodyEl.querySelector(
        `.plan-session-type[data-date="${dateLocal}"][data-session-index="${sessionIndex}"]`,
      );
      const workoutInput = bodyEl.querySelector(
        `.plan-session-workout[data-date="${dateLocal}"][data-session-index="${sessionIndex}"]`,
      );
      const fallbackWorkout = runTypeSelect && runTypeSelect.dataset ? String(runTypeSelect.dataset.plannedWorkout || "") : "";
      const workoutValue = workoutInput && typeof workoutInput.value === "string"
        ? workoutInput.value
        : fallbackWorkout;
      if (runTypeSelect && runTypeSelect.dataset) {
        runTypeSelect.dataset.plannedWorkout = String(workoutValue || "");
      }
      return {
        planned_miles: distanceInput && typeof distanceInput.value === "string" ? distanceInput.value : "",
        run_type: runTypeSelect && typeof runTypeSelect.value === "string" ? runTypeSelect.value : "",
        planned_workout: workoutValue,
      };
    });
    return serializeSessionsForApi(raw);
  }

  function buildPastDistanceSummary(row) {
    const summary = document.createElement("div");
    summary.className = "plan-aed-summary";

    function appendMetric(symbol, value) {
      const part = document.createElement("span");
      part.className = "plan-aed-part";
      const symbolEl = document.createElement("strong");
      symbolEl.className = "plan-aed-symbol";
      symbolEl.textContent = `${symbol}:`;
      part.appendChild(symbolEl);
      part.appendChild(document.createTextNode(` ${value}`));
      summary.appendChild(part);
    }

    appendMetric("Λ", formatMiles(row && row.actual_miles, 1));
    summary.appendChild(document.createTextNode("\u00A0\u00A0|\u00A0\u00A0"));
    appendMetric("Σ", formatMiles(row && row.planned_miles, 1));
    summary.appendChild(document.createTextNode("\u00A0\u00A0|\u00A0\u00A0"));
    appendMetric("Δ", formatSigned(row && row.day_delta, 1));
    return summary;
  }

  function resolveDayRunType(dateLocal, fallback) {
    const sessions = collectSessionPayloadForDate(dateLocal);
    for (const session of sessions) {
      if (!session || typeof session !== "object") continue;
      const candidate = String(session.run_type || "").trim();
      if (candidate) return candidate;
    }
    return String(fallback || "").trim();
  }

  function saveSessionPayload(row, index, rows, nextFocusDate, nextField, sessionsOverride) {
    const sessions = Array.isArray(sessionsOverride) ? sessionsOverride : collectSessionPayloadForDate(row.date);
    const runType = resolveDayRunType(row.date, row && row.run_type);
    const existingSessions = serializeSessionsForApi(sessionDetailsFromRow(row));
    const existingRunType = String(row && row.run_type ? row.run_type : "").trim();
    if (payloadsEqualByValue(existingSessions, sessions) && existingRunType === String(runType || "").trim()) {
      return;
    }
    applyLocalPlanEdit(row.date, sessions, runType);
    void savePlanRow(
      row.date,
      {
        sessions,
        run_type: runType,
      },
      nextFocusDate || row.date,
      nextField || "distance",
    );
  }

  function setPendingFocus(dateValue, field) {
    pendingFocus = {
      date: String(dateValue || ""),
      field: "distance",
    };
  }

  function mergeSavePayload(existingPayload, incomingPayload) {
    const base = existingPayload && typeof existingPayload === "object" ? existingPayload : {};
    const next = incomingPayload && typeof incomingPayload === "object" ? incomingPayload : {};
    return {
      ...base,
      ...next,
    };
  }

  async function refreshCenterSummaryLightweight() {
    const centerDate = isIsoDateString(centerDateEl && centerDateEl.value) ? centerDateEl.value : "";
    if (!centerDate) return;
    try {
      const response = await fetch(`/plan/day/${encodeURIComponent(centerDate)}/metrics`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") return;
      if (payload.summary && typeof payload.summary === "object") {
        setSummary({
          status: "ok",
          summary: payload.summary,
        });
      }
    } catch (_err) {
      // Lightweight summary refresh is best-effort.
    }
  }

  function queuePlanSave(dateLocal, payload, nextFocusDate, nextField) {
    const dateKey = String(dateLocal || "").trim();
    if (!isIsoDateString(dateKey)) return;
    const nextPayload = mergeSavePayload(pendingPlanSaves.get(dateKey), payload || {});
    pendingPlanSaves.set(dateKey, nextPayload);
    if (isIsoDateString(nextFocusDate)) {
      if (!isIsoDateString(saveMaxNextFocusDate) || nextFocusDate > saveMaxNextFocusDate) {
        saveMaxNextFocusDate = nextFocusDate;
      }
    }
    setPendingFocus(nextFocusDate, nextField);
    if (saveFlushTimer !== null) {
      clearTimeout(saveFlushTimer);
    }
    saveFlushTimer = setTimeout(() => {
      saveFlushTimer = null;
      void flushQueuedPlanSaves();
    }, 120);
  }

  async function flushQueuedPlanSaves() {
    if (saveFlushInFlight) {
      saveFlushQueuedAfterFlight = true;
      return;
    }
    if (!(pendingPlanSaves instanceof Map) || pendingPlanSaves.size === 0) return;
    const entries = Array.from(pendingPlanSaves.entries());
    pendingPlanSaves = new Map();
    saveFlushInFlight = true;
    try {
      const response = await fetch("/plan/days/bulk", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          days: entries.map(([dateKey, dayPayload]) => ({
            date_local: dateKey,
            ...(dayPayload && typeof dayPayload === "object" ? dayPayload : {}),
          })),
        }),
      });
      const result = await response.json();
      if (!response.ok || result.status !== "ok") {
        throw new Error(String((result && result.error) || "Failed to save plan days"));
      }

      const savedDays = Array.isArray(result && result.days) ? result.days : [];
      let minSavedDate = "";
      for (const saved of savedDays) {
        if (!saved || typeof saved !== "object") continue;
        const dateKey = String(saved.date_local || "");
        if (!isIsoDateString(dateKey)) continue;
        if (!isIsoDateString(minSavedDate) || dateKey < minSavedDate) {
          minSavedDate = dateKey;
        }
        const savedSessions = Array.isArray(saved.sessions) ? saved.sessions : [];
        applyLocalPlanEdit(
          dateKey,
          savedSessions,
          String(saved.run_type || ""),
        );
      }

      const needsAppendFuture = (
        isIsoDateString(saveMaxNextFocusDate)
        && isIsoDateString(loadedEndDate)
        && saveMaxNextFocusDate > loadedEndDate
      );
      if (needsAppendFuture) {
        const anchorDate = isIsoDateString(minSavedDate) ? minSavedDate : loadedEndDate;
        const appendStart = overlapStartForDate(anchorDate, loadedStartDate);
        const appendTarget = addDaysIso(loadedEndDate, PLAN_APPEND_FUTURE_DAYS);
        const appendEnd = saveMaxNextFocusDate > appendTarget ? saveMaxNextFocusDate : appendTarget;
        await loadPlanRange({
          startDate: appendStart,
          endDate: appendEnd,
          centerDateOverride: centerDateEl.value,
          append: true,
        });
      } else if (isIsoDateString(minSavedDate)) {
        queuePlanBackgroundRefresh(minSavedDate);
      }
      void refreshCenterSummaryLightweight();
      if (metaEl) {
        metaEl.textContent = `Saved ${savedDays.length} day(s) | syncing metrics...`;
      }
    } catch (err) {
      for (const [dateKey, dayPayload] of entries) {
        pendingPlanSaves.set(dateKey, mergeSavePayload(pendingPlanSaves.get(dateKey), dayPayload));
      }
      if (metaEl) {
        metaEl.textContent = String(err && err.message ? err.message : "Failed to save plan days");
      }
      if (saveFlushTimer !== null) {
        clearTimeout(saveFlushTimer);
      }
      saveFlushTimer = setTimeout(() => {
        saveFlushTimer = null;
        void flushQueuedPlanSaves();
      }, 300);
    } finally {
      saveMaxNextFocusDate = "";
      saveFlushInFlight = false;
      if (saveFlushQueuedAfterFlight || pendingPlanSaves.size > 0) {
        saveFlushQueuedAfterFlight = false;
        void flushQueuedPlanSaves();
      }
    }
  }

  async function savePlanRow(dateLocal, payload, nextFocusDate, nextField) {
    try {
      queuePlanSave(dateLocal, payload || {}, nextFocusDate, nextField);
    } catch (err) {
      if (metaEl) {
        metaEl.textContent = String(err && err.message ? err.message : "Failed to queue plan save");
      }
    }
  }

  function selectorForField(field, dateValue) {
    const dateEscaped = String(dateValue || "");
    return `.plan-session-distance[data-date="${dateEscaped}"][data-session-index="0"]`;
  }

  function rowIndexByDate(dateValue) {
    const dateKey = String(dateValue || "");
    if (!dateKey) return -1;
    return renderedRows.findIndex((item) => item && item.date === dateKey);
  }

  function focusNeighbor(rows, index, field, delta) {
    const target = rowAt(rows, index + delta);
    if (!target) return false;
    const element = bodyEl.querySelector(selectorForField(field, target.date));
    if (!element) return false;
    element.focus();
    if (field === "distance" && typeof element.select === "function") {
      element.select();
    }
    return true;
  }

  function buildSessionTypeSelect(row, index, rows, session, sessionIndex) {
    const select = document.createElement("select");
    select.className = "plan-run-type plan-session-type";
    select.dataset.date = row.date;
    select.dataset.sessionIndex = String(sessionIndex);
    select.dataset.plannedWorkout = String(session && (session.planned_workout || session.workout_code) ? (session.planned_workout || session.workout_code) : "");
    for (const optionValue of runTypeOptions) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue || "--";
      if (optionValue === String(session && session.run_type ? session.run_type : "")) {
        option.selected = true;
      }
      select.appendChild(option);
    }
    return select;
  }

  function buildSessionWorkoutInput(row, index, rows, session, sessionIndex, runTypeSelect) {
    const field = document.createElement("div");
    field.className = "plan-workout-field";
    field.dataset.open = "0";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "plan-workout-input plan-session-workout";
    input.dataset.date = row.date;
    input.dataset.sessionIndex = String(sessionIndex);
    input.placeholder = "Workout shorthand";
    input.title = "Workout shorthand for SOS session. Press Enter to save.";
    input.value = String((session && (session.planned_workout || session.workout_code)) || runTypeSelect.dataset.plannedWorkout || "");
    runTypeSelect.dataset.plannedWorkout = input.value;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "plan-workout-toggle";
    toggle.setAttribute("aria-label", "Show workout presets");
    toggle.title = "Show workout presets";
    toggle.textContent = "▾";

    const menu = document.createElement("div");
    menu.className = "plan-workout-menu";
    menu.hidden = true;
    menu.style.setProperty("--plan-workout-menu-width-ch", String(workoutPresetMenuWidthCh));

    for (const optionValue of workoutPresetOptions) {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "plan-workout-menu-item";
      option.textContent = optionValue;
      option.title = optionValue;
      option.addEventListener("click", () => {
        input.value = optionValue;
        runTypeSelect.dataset.plannedWorkout = String(optionValue || "");
        setWorkoutMenuOpen(field, menu, false);
        saveSessionPayload(row, index, rows, row.date, "distance");
      });
      menu.appendChild(option);
    }

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const nextOpen = field.dataset.open !== "1";
      for (const openField of document.querySelectorAll(".plan-workout-field")) {
        if (openField instanceof HTMLElement && openField !== field) {
          openField.dataset.open = "0";
        }
      }
      for (const openMenu of document.querySelectorAll(".plan-workout-menu")) {
        if (!(openMenu instanceof HTMLElement) || openMenu === menu) continue;
        openMenu.hidden = true;
      }
      setWorkoutMenuOpen(field, menu, nextOpen);
    });

    input.addEventListener("input", () => {
      runTypeSelect.dataset.plannedWorkout = String(input.value || "");
    });
    input.addEventListener("change", () => {
      runTypeSelect.dataset.plannedWorkout = String(input.value || "");
      saveSessionPayload(row, index, rows, row.date, "distance");
    });
    input.addEventListener("keydown", (event) => {
      if (!event.ctrlKey || (event.key !== "ArrowDown" && event.key !== "ArrowUp")) {
        if (event.altKey && event.key === "ArrowDown") {
          event.preventDefault();
          setWorkoutMenuOpen(field, menu, true);
          return;
        }
        if (event.key === "Enter") {
          event.preventDefault();
          runTypeSelect.dataset.plannedWorkout = String(input.value || "");
          saveSessionPayload(row, index, rows, row.date, "distance");
        }
        return;
      }
      event.preventDefault();
      focusNeighbor(rows, index, "distance", event.key === "ArrowDown" ? 1 : -1);
    });
    field.appendChild(input);
    field.appendChild(toggle);
    field.appendChild(menu);
    return field;
  }

  function buildSessionDistanceEditor(row, index, rows) {
    const editor = document.createElement("div");
    editor.className = "session-editor session-distance-editor";
    const sessions = sessionDetailsFromRow(row);
    const nonEmptySessions = sessions.filter((item) => Number.isFinite(Number(item.planned_miles)) && Number(item.planned_miles) > 0);
    const rowsToRender = nonEmptySessions.length > 0 ? nonEmptySessions : sessions.slice(0, 1);

    for (let sessionIndex = 0; sessionIndex < rowsToRender.length; sessionIndex += 1) {
      const session = rowsToRender[sessionIndex];
      const rowEl = document.createElement("div");
      rowEl.className = "plan-session-row";
      rowEl.dataset.date = row.date;
      rowEl.dataset.sessionIndex = String(sessionIndex);

      const distanceWrap = document.createElement("div");
      distanceWrap.className = "session-distance-wrap";
      const input = document.createElement("input");
      input.className = "plan-distance-input plan-session-distance";
      input.type = "text";
      input.dataset.date = row.date;
      input.dataset.sessionIndex = String(sessionIndex);
      input.value = Number.isFinite(Number(session.planned_miles)) && Number(session.planned_miles) > 0
        ? formatSessionValue(Number(session.planned_miles))
        : "";
      input.placeholder = "mi";
      input.title = "Distance for this session. Press Enter to save.";
      distanceWrap.appendChild(input);

      if (sessionIndex === 0) {
        const inlineActions = document.createElement("div");
        inlineActions.className = "session-inline-actions";

        const addBtn = document.createElement("button");
        addBtn.type = "button";
        addBtn.className = "session-inline-btn";
        addBtn.textContent = "+";
        addBtn.title = "Add session";
        addBtn.addEventListener("click", () => {
          const current = collectSessionPayloadForDate(row.date);
          current.push({ ordinal: current.length + 1, planned_miles: 1.0, run_type: "", planned_workout: "" });
          saveSessionPayload(row, index, rows, row.date, "distance", current);
        });
        inlineActions.appendChild(addBtn);

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "session-inline-btn";
        removeBtn.textContent = "-";
        removeBtn.title = "Remove last session";
        removeBtn.disabled = nonEmptySessions.length <= 1;
        removeBtn.addEventListener("click", () => {
          const current = collectSessionPayloadForDate(row.date);
          if (current.length > 0) current.pop();
          saveSessionPayload(row, index, rows, row.date, "distance", current);
        });
        inlineActions.appendChild(removeBtn);

        distanceWrap.appendChild(inlineActions);
      }

      rowEl.appendChild(distanceWrap);
      editor.appendChild(rowEl);
    }
    return editor;
  }

  function buildSessionTypeEditor(row, index, rows) {
    const editor = document.createElement("div");
    editor.className = "session-editor session-type-editor";
    const sessions = sessionDetailsFromRow(row);
    const nonEmptySessions = sessions.filter((item) => Number.isFinite(Number(item.planned_miles)) && Number(item.planned_miles) > 0);
    const rowsToRender = nonEmptySessions.length > 0 ? nonEmptySessions : sessions.slice(0, 1);

    for (let sessionIndex = 0; sessionIndex < rowsToRender.length; sessionIndex += 1) {
      const session = rowsToRender[sessionIndex];
      const rowEl = document.createElement("div");
      rowEl.className = "plan-session-row";
      rowEl.dataset.date = row.date;
      rowEl.dataset.sessionIndex = String(sessionIndex);
      const runTypeSelect = buildSessionTypeSelect(row, index, rows, session, sessionIndex);
      rowEl.appendChild(runTypeSelect);
      const runTypeValue = String(session && session.run_type ? session.run_type : runTypeSelect.value || "");
      if (isSosRunType(runTypeValue)) {
        rowEl.appendChild(buildSessionWorkoutInput(row, index, rows, session, sessionIndex, runTypeSelect));
      }
      editor.appendChild(rowEl);
    }
    return editor;
  }

  async function renderRows(rows) {
    bodyEl.textContent = "";
    rowsByDate = new Map();
    let chunkFragment = document.createDocumentFragment();
    let chunkCount = 0;
    const shouldChunk = rows.length > 320;
    const chunkSize = 72;
    let weekIndex = -1;
    let currentWeekKey = "";
    for (let index = 0; index < rows.length; index += 1) {
      const row = rows[index];
      if (row && typeof row.date === "string" && row.date) {
        rowsByDate.set(row.date, row);
      }
      const tr = document.createElement("tr");
      if (row && typeof row.date === "string" && row.date) {
        tr.dataset.date = row.date;
      }
      const weekInfo = weekInfoForDate(row && row.date);
      const prevWeekInfo = weekInfoForDate(rowAt(rows, index - 1) && rowAt(rows, index - 1).date);
      const nextWeekInfo = weekInfoForDate(rowAt(rows, index + 1) && rowAt(rows, index + 1).date);
      const isWeekStart = !weekInfo.weekKey || weekInfo.weekKey !== prevWeekInfo.weekKey;
      const isWeekEnd = !weekInfo.weekKey || weekInfo.weekKey !== nextWeekInfo.weekKey;

      if (isWeekStart && weekInfo.weekKey && weekInfo.weekKey !== currentWeekKey) {
        currentWeekKey = weekInfo.weekKey;
        weekIndex += 1;
      }
      if (isWeekStart) tr.classList.add("week-start");
      if (isWeekEnd) tr.classList.add("week-end");
      tr.classList.add((weekIndex + 1) % 2 === 0 ? "week-block-even" : "week-block-odd");
      if (row && row.is_today) tr.classList.add("is-today");

      const doneTd = document.createElement("td");
      doneTd.className = "done-cell";
      const doneChip = document.createElement("span");
      doneChip.className = "done-chip";
      const actualMiles = asNumber(row && row.actual_miles);
      const plannedMiles = asNumber(row && row.planned_miles);
      const isPast = !!(row && row.is_past_or_today && !row.is_today);
      const isTodayPending = !!(row && row.is_today && (actualMiles === null || actualMiles <= 0));
      let doneState = "pending";
      if (actualMiles !== null && actualMiles > 0) {
        doneState = "done";
      } else if (isPast && (plannedMiles !== null && plannedMiles > 0)) {
        doneState = "missed";
      } else if (isPast) {
        doneState = "done";
      } else if (isTodayPending) {
        doneState = "pending";
      }
      doneChip.classList.add(doneState);
      doneChip.title = (
        doneState === "done"
          ? "Compliant day based on detected activity and planned mileage."
          : doneState === "missed"
            ? "Planned run without detected activity."
            : "Future/today pending activity."
      );
      doneTd.appendChild(doneChip);
      tr.appendChild(doneTd);

      const dateTd = document.createElement("td");
      dateTd.className = "date-cell";
      const dateMain = document.createElement("span");
      dateMain.className = "plan-date-main";
      dateMain.textContent = formatDisplayDate(row && row.date);
      dateMain.title = String((row && row.date) || "--");
      dateTd.appendChild(dateMain);
      tr.appendChild(dateTd);

      const distanceTd = document.createElement("td");
      distanceTd.className = "distance-cell";
      let distanceMileage = null;
      if (row && row.is_past_or_today && !row.is_today) {
        distanceMileage = asNumber(row.actual_miles);
        if (distanceMileage === null) distanceMileage = asNumber(row.planned_miles);
      } else {
        distanceMileage = asNumber(row && row.planned_miles);
      }
      const distanceTone = distanceColorForMiles(distanceMileage);
      if (distanceTone) {
        distanceTd.classList.add("distance-gradient-cell");
        distanceTd.style.setProperty("--distance-mile-color", distanceTone);
      }
      if (row && row.is_past_or_today && !row.is_today) {
        distanceTd.appendChild(buildPastDistanceSummary(row));
      } else {
        distanceTd.appendChild(buildSessionDistanceEditor(row, index, rows));
      }
      tr.appendChild(distanceTd);

      const runTypeTd = document.createElement("td");
      runTypeTd.className = "run-type-cell";
      runTypeTd.appendChild(buildSessionTypeEditor(row, index, rows));
      tr.appendChild(runTypeTd);

      const showWeekMetrics = !!(row && row.show_week_metrics);
      const weekRowSpan = Math.max(1, Number(row && row.week_row_span) || 1);
      if (showWeekMetrics) {
        const weekTd = makeCell(formatMiles(row && row.weekly_total, 1), "metric-week metric-week-block metric-block-center metric-week-joined");
        weekTd.classList.add("metric-block-start");
        weekTd.rowSpan = weekRowSpan;
        tr.appendChild(weekTd);

        const wowTd = makeCell(
          formatPct(row && row.wow_change),
          `${wowBandFromValue(row && row.wow_change)} metric-wow-block metric-block-center metric-week-joined`,
        );
        wowTd.classList.add("metric-block-start");
        wowTd.rowSpan = weekRowSpan;
        tr.appendChild(wowTd);

        const longTd = makeCell(
          formatPct(row && row.long_pct),
          `${metricBandClass(row && row.bands && row.bands.long_pct)} metric-long-block metric-block-center metric-week-joined`,
        );
        longTd.classList.add("metric-block-start");
        longTd.rowSpan = weekRowSpan;
        tr.appendChild(longTd);
      }

      const showMonthMetrics = !!(row && row.show_month_metrics);
      const monthRowSpan = Math.max(1, Number(row && row.month_row_span) || 1);
      if (showMonthMetrics) {
        const monthTd = makeCell(formatMiles(row && row.monthly_total, 1), "metric-month metric-month-block metric-block-bottom");
        monthTd.classList.add("metric-block-start");
        monthTd.rowSpan = monthRowSpan;
        tr.appendChild(monthTd);

        const momTd = makeCell(
          formatPct(row && row.mom_change),
          `${wowBandFromValue(row && row.mom_change)} metric-mom-block metric-block-bottom`,
        );
        momTd.classList.add("metric-block-start");
        momTd.rowSpan = monthRowSpan;
        tr.appendChild(momTd);
      }

      tr.appendChild(makeCell(formatMiles(row && row.t7_miles, 1), "metric-neutral"));
      tr.appendChild(makeCell(formatRatio(row && row.t7_p7_ratio, 1), metricBandClass(row && row.bands && row.bands.t7_p7_ratio)));
      tr.appendChild(makeCell(formatMiles(row && row.t30_miles, 1), "metric-neutral"));
      tr.appendChild(makeCell(formatRatio(row && row.t30_p30_ratio, 1), metricBandClass(row && row.bands && row.bands.t30_p30_ratio)));
      tr.appendChild(makeCell(formatRatio(row && row.avg30_miles_per_day, 2), "metric-neutral"));
      tr.appendChild(makeCell(formatRatio(row && row.mi_t30_ratio, 1), miT30BandFromValue(row && row.mi_t30_ratio)));

      chunkFragment.appendChild(tr);
      chunkCount += 1;
      if (shouldChunk && chunkCount >= chunkSize) {
        bodyEl.appendChild(chunkFragment);
        chunkFragment = document.createDocumentFragment();
        chunkCount = 0;
        // Yield to keep typing and scroll interactions responsive on long ranges.
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
    }
    if (chunkCount > 0) {
      bodyEl.appendChild(chunkFragment);
    }
  }

  function setMeta(payload) {
    if (!metaEl) return;
    if (!payload || payload.status !== "ok") {
      metaEl.textContent = "Data unavailable";
      return;
    }
    loadedTimezone = String(payload.timezone || loadedTimezone || "");
    metaEl.textContent = `${payload.start_date} to ${payload.end_date} | Center ${payload.center_date} | ${loadedTimezone}`;
  }

  function setMetaFromState(centerDate) {
    if (!metaEl) return;
    if (!isIsoDateString(loadedStartDate) || !isIsoDateString(loadedEndDate)) return;
    const centerValue = isIsoDateString(centerDate) ? centerDate : centerDateEl.value;
    const effectiveCenter = isIsoDateString(centerValue) ? centerValue : loadedEndDate;
    const timezoneText = loadedTimezone || "--";
    metaEl.textContent = `${loadedStartDate} to ${loadedEndDate} | Center ${effectiveCenter} | ${timezoneText}`;
  }

  function setSettingsStatus(message, tone) {
    if (!settingsStatusEl) return;
    settingsStatusEl.textContent = String(message || "");
    settingsStatusEl.dataset.tone = tone === "error" ? "error" : (tone === "ok" ? "ok" : "neutral");
  }

  function setSettingsOpen(nextOpen) {
    if (!settingsPanel) return;
    settingsPanel.hidden = !nextOpen;
    if (!nextOpen) {
      setSettingsStatus("", "neutral");
    }
  }

  async function seedPlanFromActuals() {
    if (!seedBtn) return;
    seedBtn.disabled = true;
    setSettingsStatus("Seeding expected mileage from actuals...", "neutral");
    try {
      const response = await fetch("/plan/seed/from-actuals", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{}",
      });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") {
        throw new Error(String((payload && payload.error) || "Seed failed"));
      }
      const seededDays = Number(payload.seeded_days || 0);
      const seededMiles = Number(payload.seeded_total_miles || 0);
      setSettingsStatus(`Seed complete: ${seededDays} day(s), ${seededMiles.toFixed(1)} mi`, "ok");
      await loadPlan(centerDateEl.value);
    } catch (err) {
      setSettingsStatus(String(err && err.message ? err.message : "Seed failed"), "error");
    } finally {
      seedBtn.disabled = false;
    }
  }

  function setSummary(payload) {
    if (!summaryEl) return;
    if (!payload || payload.status !== "ok" || !payload.summary) {
      summaryEl.textContent = "";
      return;
    }
    const summary = payload.summary;
    const cards = [
      {
        label: "Day Plan vs Actual",
        value: `${formatMiles(summary.day_planned, 1)} / ${formatMiles(summary.day_actual, 1)}`,
        detail: `Δ ${formatSigned(summary.day_delta, 1)}`,
      },
      {
        label: "Trailing 7d Plan vs Actual",
        value: `${formatMiles(summary.t7_planned, 1)} / ${formatMiles(summary.t7_actual, 1)}`,
        detail: `Δ ${formatSigned(summary.t7_delta, 1)} | ${formatPercentRatio(summary.t7_adherence_ratio)}`,
      },
      {
        label: "Trailing 30d Plan vs Actual",
        value: `${formatMiles(summary.t30_planned, 1)} / ${formatMiles(summary.t30_actual, 1)}`,
        detail: `Δ ${formatSigned(summary.t30_delta, 1)} | ${formatPercentRatio(summary.t30_adherence_ratio)}`,
      },
      {
        label: "Week Plan vs Actual",
        value: `${formatMiles(summary.week_planned, 1)} / ${formatMiles(summary.week_actual, 1)}`,
        detail: `Δ ${formatSigned(summary.week_delta, 1)} | ${formatPercentRatio(summary.week_adherence_ratio)}`,
      },
      {
        label: "Month Plan vs Actual",
        value: `${formatMiles(summary.month_planned, 1)} / ${formatMiles(summary.month_actual, 1)}`,
        detail: `Δ ${formatSigned(summary.month_delta, 1)} | ${formatPercentRatio(summary.month_adherence_ratio)}`,
      },
    ];
    summaryEl.textContent = "";
    for (const card of cards) {
      const item = document.createElement("div");
      item.className = "plan-summary-card";
      const label = document.createElement("span");
      label.className = "plan-summary-label";
      label.textContent = card.label;
      const value = document.createElement("span");
      value.className = "plan-summary-value";
      value.textContent = card.value;
      const detail = document.createElement("span");
      detail.className = "plan-summary-detail";
      detail.textContent = card.detail;
      item.appendChild(label);
      item.appendChild(value);
      item.appendChild(detail);
      summaryEl.appendChild(item);
    }
  }

  function summaryFromRow(row) {
    const weekPlanned = Number(row && row.weekly_planned_total) || 0;
    const weekActual = Number(row && row.weekly_actual_total) || 0;
    const monthPlanned = Number(row && row.monthly_planned_total) || 0;
    const monthActual = Number(row && row.monthly_actual_total) || 0;
    const t7Planned = Number(row && row.t7_planned_miles) || 0;
    const t7Actual = Number(row && row.t7_actual_miles) || 0;
    const t30Planned = Number(row && row.t30_planned_miles) || 0;
    const t30Actual = Number(row && row.t30_actual_miles) || 0;
    return {
      day_planned: Number(row && row.planned_miles) || 0,
      day_actual: Number(row && row.actual_miles) || 0,
      day_delta: Number(row && row.day_delta) || 0,
      t7_planned: t7Planned,
      t7_actual: t7Actual,
      t7_delta: t7Actual - t7Planned,
      t7_adherence_ratio: row ? row.t7_adherence_ratio : null,
      t30_planned: t30Planned,
      t30_actual: t30Actual,
      t30_delta: t30Actual - t30Planned,
      t30_adherence_ratio: row ? row.t30_adherence_ratio : null,
      week_planned: weekPlanned,
      week_actual: weekActual,
      week_delta: weekActual - weekPlanned,
      week_adherence_ratio: row ? row.weekly_adherence_ratio : null,
      month_planned: monthPlanned,
      month_actual: monthActual,
      month_delta: monthActual - monthPlanned,
      month_adherence_ratio: row ? row.monthly_adherence_ratio : null,
    };
  }

  function setSummaryForDate(dateValue) {
    if (!isIsoDateString(dateValue)) return;
    const row = rowsByDate.get(dateValue);
    if (!row) return;
    setSummary({
      status: "ok",
      summary: summaryFromRow(row),
    });
  }

  function centerDateRowInView(dateValue, behavior = "auto") {
    if (!tableWrapEl || !isIsoDateString(dateValue)) return false;
    const targetRow = bodyEl.querySelector(`tr[data-date="${dateValue}"]`);
    if (!(targetRow instanceof HTMLElement)) return false;
    const tableEl = tableWrapEl.querySelector("table");
    const headerHeight = tableEl && tableEl.tHead ? tableEl.tHead.getBoundingClientRect().height : 0;
    const viewportHeight = Math.max(1, tableWrapEl.clientHeight - headerHeight);
    const desiredTop = targetRow.offsetTop - headerHeight - ((viewportHeight - targetRow.offsetHeight) / 2);
    const maxScroll = Math.max(0, tableWrapEl.scrollHeight - tableWrapEl.clientHeight);
    const nextTop = Math.max(0, Math.min(desiredTop, maxScroll));
    tableWrapEl.scrollTo({
      top: nextTop,
      behavior: behavior === "smooth" ? "smooth" : "auto",
    });
    return true;
  }

  async function ensureDateLoadedForCenter(targetDate) {
    if (!isIsoDateString(targetDate)) return;
    if (!isIsoDateString(loadedEndDate)) return;
    const hasStart = isIsoDateString(loadedStartDate);
    if (hasStart && targetDate < loadedStartDate) {
      await loadPlanRange({
        startDate: targetDate,
        endDate: loadedEndDate,
        centerDateOverride: targetDate,
        append: false,
      });
      return;
    }
    if (targetDate > loadedEndDate) {
      const appendStart = overlapStartForDate(loadedEndDate, hasStart ? loadedStartDate : "");
      const appendTarget = addDaysIso(loadedEndDate, PLAN_APPEND_FUTURE_DAYS);
      const appendEnd = targetDate > appendTarget ? targetDate : appendTarget;
      await loadPlanRange({
        startDate: appendStart,
        endDate: appendEnd,
        centerDateOverride: targetDate,
        append: true,
      });
    }
  }

  function applyPendingFocus() {
    if (!pendingFocus.date) return;
    const target = bodyEl.querySelector(selectorForField(pendingFocus.field, pendingFocus.date));
    const field = pendingFocus.field;
    pendingFocus = { date: "", field: "distance" };
    if (!target) return;
    target.focus();
    if (field === "distance" && typeof target.select === "function") {
      target.select();
    }
  }

  async function loadPlanRange({
    startDate = "",
    endDate = "",
    centerDateOverride = "",
    append = false,
    centerDateInView = "",
    centerBehavior = "auto",
  } = {}) {
    const params = new URLSearchParams();
    params.set("window_days", "14");
    params.set("include_meta", hasLoadedPlanMeta ? "0" : "1");
    const targetDate = String(centerDateOverride || centerDateEl.value || "").trim();
    if (targetDate) {
      params.set("center_date", targetDate);
    }
    if (isIsoDateString(startDate)) {
      params.set("start_date", String(startDate));
    }
    if (isIsoDateString(endDate)) {
      params.set("end_date", String(endDate));
    }

    try {
      if (metaEl) metaEl.textContent = "Loading...";
      const response = await fetch(`/plan/data.json?${params.toString()}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") {
        const error = String((payload && payload.error) || "Failed to load plan data");
        bodyEl.innerHTML = `<tr><td colspan="15">${error}</td></tr>`;
        if (metaEl) metaEl.textContent = "Load failed";
        return;
      }
      if (typeof payload.center_date === "string" && payload.center_date) {
        centerDateEl.value = payload.center_date;
      }
      if (typeof payload.min_center_date === "string" && payload.min_center_date) {
        centerDateEl.min = payload.min_center_date;
      }
      if (typeof payload.max_center_date === "string" && payload.max_center_date) {
        centerDateEl.max = payload.max_center_date;
      }
      if (Array.isArray(payload.run_type_options) && payload.run_type_options.length > 0) {
        runTypeOptions = payload.run_type_options.map((item) => String(item || ""));
        hasLoadedPlanMeta = true;
        cacheRunTypeOptions(runTypeOptions);
      } else if (!Array.isArray(runTypeOptions) || runTypeOptions.length === 0) {
        runTypeOptions = [""];
      }
      setMeta(payload);
      setSummary(payload);
      const incomingRows = Array.isArray(payload.rows) ? payload.rows : [];
      renderedRows = append ? mergeRowsByDate(renderedRows, incomingRows) : incomingRows;
      await renderRows(renderedRows);
      const payloadStart = (typeof payload.start_date === "string" && isIsoDateString(payload.start_date))
        ? payload.start_date
        : (isIsoDateString(startDate) ? String(startDate) : "");
      const payloadEnd = (typeof payload.end_date === "string" && isIsoDateString(payload.end_date))
        ? payload.end_date
        : (isIsoDateString(endDate) ? String(endDate) : "");
      if (append) {
        if (isIsoDateString(payloadStart)) {
          if (!isIsoDateString(loadedStartDate) || payloadStart < loadedStartDate) {
            loadedStartDate = payloadStart;
          }
        }
        if (isIsoDateString(payloadEnd)) {
          if (!isIsoDateString(loadedEndDate) || payloadEnd > loadedEndDate) {
            loadedEndDate = payloadEnd;
          }
        }
      } else {
        if (isIsoDateString(payloadStart)) loadedStartDate = payloadStart;
        if (isIsoDateString(payloadEnd)) loadedEndDate = payloadEnd;
      }
      applyPendingFocus();
      const centerTarget = String(centerDateInView || "").trim();
      if (isIsoDateString(centerTarget)) {
        requestAnimationFrame(() => {
          centerDateRowInView(centerTarget, centerBehavior);
        });
      }
    } catch (_err) {
      bodyEl.innerHTML = "<tr><td colspan=\"15\">Network error while loading plan data.</td></tr>";
      if (metaEl) metaEl.textContent = "Network error";
    }
  }

  async function loadPlan(centerDate, options = {}) {
    const centerInView = !!options.centerInView;
    const centerBehavior = String(options.centerBehavior || "auto");
    const targetDate = String(centerDate || centerDateEl.value || todayIsoLocal()).trim();
    const endDate = isIsoDateString(loadedEndDate) ? loadedEndDate : addDaysIso(todayIsoLocal(), PLAN_INITIAL_FUTURE_DAYS);
    const startDate = isIsoDateString(loadedStartDate) ? loadedStartDate : "";
    await loadPlanRange({
      startDate,
      endDate,
      centerDateOverride: targetDate,
      append: false,
      centerDateInView: centerInView ? targetDate : "",
      centerBehavior,
    });
  }

  async function centerOnSelectedDate() {
    const selectedDate = isIsoDateString(centerDateEl.value) ? centerDateEl.value : todayIsoLocal();
    centerDateEl.value = selectedDate;
    await ensureDateLoadedForCenter(selectedDate);
    const effectiveCenter = isIsoDateString(centerDateEl.value) ? centerDateEl.value : selectedDate;
    setMetaFromState(effectiveCenter);
    setSummaryForDate(effectiveCenter);
    if (!centerDateRowInView(effectiveCenter, "smooth")) {
      await loadPlan(effectiveCenter, { centerInView: true, centerBehavior: "smooth" });
    }
  }

  reloadBtn.addEventListener("click", () => {
    void loadPlan(centerDateEl.value);
  });
  if (centerBtn) {
    centerBtn.addEventListener("click", () => {
      void centerOnSelectedDate();
    });
  }
  centerDateEl.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    void centerOnSelectedDate();
  });

  if (settingsBtn && settingsPanel) {
    settingsBtn.addEventListener("click", (event) => {
      event.preventDefault();
      const nextOpen = Boolean(settingsPanel.hidden);
      setSettingsOpen(nextOpen);
    });

    document.addEventListener("click", (event) => {
      if (settingsPanel.hidden) return;
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (settingsPanel.contains(target) || settingsBtn.contains(target)) return;
      setSettingsOpen(false);
    });
  }
  if (seedBtn) {
    seedBtn.addEventListener("click", () => {
      void seedPlanFromActuals();
    });
  }

  if (bodyEl) {
    bodyEl.addEventListener("change", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.matches(".plan-session-type")) {
        const dateLocal = String(target.getAttribute("data-date") || "");
        const row = rowsByDate.get(dateLocal);
        if (!row) return;
        const index = rowIndexByDate(dateLocal);
        if (index < 0) return;
        saveSessionPayload(row, index, renderedRows, dateLocal, "distance");
        return;
      }
      if (target.matches(".plan-session-distance")) {
        const dateLocal = String(target.getAttribute("data-date") || "");
        const row = rowsByDate.get(dateLocal);
        if (!row) return;
        const index = rowIndexByDate(dateLocal);
        if (index < 0) return;
        saveSessionPayload(row, index, renderedRows, dateLocal, "distance");
      }
    });

    bodyEl.addEventListener("keydown", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      if (target.matches(".plan-session-type")) {
        if (!event.ctrlKey || (event.key !== "ArrowDown" && event.key !== "ArrowUp")) {
          return;
        }
        const dateLocal = String(target.getAttribute("data-date") || "");
        const index = rowIndexByDate(dateLocal);
        if (index < 0) return;
        event.preventDefault();
        focusNeighbor(renderedRows, index, "distance", event.key === "ArrowDown" ? 1 : -1);
        return;
      }

      if (!target.matches(".plan-session-distance")) return;

      const dateLocal = String(target.getAttribute("data-date") || "");
      const row = rowsByDate.get(dateLocal);
      if (!row) return;
      const index = rowIndexByDate(dateLocal);
      if (index < 0) return;
      const sessionIndex = Number.parseInt(String(target.getAttribute("data-session-index") || "0"), 10);
      if (sessionIndex === 0 && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        event.preventDefault();
        focusNeighbor(renderedRows, index, "distance", event.key === "ArrowDown" ? 1 : -1);
        return;
      }

      if (event.ctrlKey && event.shiftKey) {
        const mapped = runTypeHotkeys[String(event.key || "").toLowerCase()];
        if (mapped && runTypeOptions.includes(mapped)) {
          event.preventDefault();
          const sessionTypeSelect = bodyEl.querySelector(
            `.plan-session-type[data-date="${dateLocal}"][data-session-index="${sessionIndex}"]`,
          );
          if (sessionTypeSelect instanceof HTMLSelectElement) {
            sessionTypeSelect.value = mapped;
          }
          saveSessionPayload(row, index, renderedRows, dateLocal, "distance");
          return;
        }
      }

      if (event.key !== "Enter") return;
      event.preventDefault();
      const nextRow = rowAt(renderedRows, index + 1);
      if (nextRow) {
        focusNeighbor(renderedRows, index, "distance", 1);
      }
      saveSessionPayload(
        row,
        index,
        renderedRows,
        nextRow ? nextRow.date : addDaysIso(dateLocal, 1),
        "distance",
      );
    });
  }

  if (paceDrawerTab) {
    paceDrawerTab.addEventListener("click", () => {
      const nextOpen = !(paceDrawer && paceDrawer.classList.contains("open"));
      setPaceDrawerOpen(nextOpen);
    });
  }
  if (paceDrawerClose) {
    paceDrawerClose.addEventListener("click", () => {
      setPaceDrawerOpen(false);
    });
  }
  if (paceBackdrop) {
    paceBackdrop.addEventListener("click", () => {
      setPaceDrawerOpen(false);
    });
  }
  if (marathonGoalSetBtn && marathonGoalInputEl) {
    marathonGoalSetBtn.addEventListener("click", () => {
      void saveMarathonGoal(marathonGoalInputEl.value);
    });
    marathonGoalInputEl.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      void saveMarathonGoal(marathonGoalInputEl.value);
    });
  }
  if (paceCalcBtn) {
    paceCalcBtn.addEventListener("click", () => {
      void calculatePaces();
    });
  }
  if (paceTimeInputEl) {
    paceTimeInputEl.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      void calculatePaces();
    });
  }
  if (paceSetDerivedBtn && marathonGoalInputEl) {
    paceSetDerivedBtn.addEventListener("click", () => {
      if (!paceDerivedGoal) return;
      marathonGoalInputEl.value = paceDerivedGoal;
      void saveMarathonGoal(paceDerivedGoal);
    });
  }

  bindWorkoutMenuHandlers();
  loadCachedRunTypeOptions();
  setPaceDrawerOpen(false);
  setDistanceOptions([]);
  if (paceSetDerivedBtn instanceof HTMLButtonElement) {
    paceSetDerivedBtn.disabled = true;
  }
  void loadPaceWorkshop();
  if (!isIsoDateString(centerDateEl.value)) {
    centerDateEl.value = todayIsoLocal();
  }
  void loadPlan(centerDateEl.value || todayIsoLocal(), { centerInView: true, centerBehavior: "auto" });
})();
