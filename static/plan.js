(function () {
  const bodyEl = document.getElementById("planTableBody");
  const metaEl = document.getElementById("planTopMeta");
  const summaryEl = document.getElementById("planSummary");
  const centerDateEl = document.getElementById("planCenterDate");
  const reloadBtn = document.getElementById("planReloadBtn");
  const todayBtn = document.getElementById("planTodayBtn");
  const settingsBtn = document.getElementById("planSettingsBtn");
  const settingsPanel = document.getElementById("planSettingsPanel");
  const seedBtn = document.getElementById("planSeedBtn");
  const settingsStatusEl = document.getElementById("planSettingsStatus");

  let runTypeOptions = [""];
  let pendingFocus = { date: "", field: "distance" };

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

  const WORKOUT_PRESET_LIST_ID = "planWorkoutPresetList";
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

  function normalizeRunType(value) {
    return String(value || "").trim().toLowerCase();
  }

  function isSosRunType(value) {
    return normalizeRunType(value) === "sos";
  }

  function ensureWorkoutPresetList() {
    if (!document || document.getElementById(WORKOUT_PRESET_LIST_ID)) return;
    const list = document.createElement("datalist");
    list.id = WORKOUT_PRESET_LIST_ID;
    for (const optionValue of workoutPresetOptions) {
      const option = document.createElement("option");
      option.value = optionValue;
      list.appendChild(option);
    }
    document.body.appendChild(list);
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
        weekEndKey: "",
      };
    }
    const mondayOffset = (date.getUTCDay() + 6) % 7;
    const weekStart = new Date(date.getTime());
    weekStart.setUTCDate(weekStart.getUTCDate() - mondayOffset);
    const weekEnd = new Date(weekStart.getTime());
    weekEnd.setUTCDate(weekEnd.getUTCDate() + 6);
    return {
      weekKey: formatIsoDate(weekStart),
      weekEndKey: formatIsoDate(weekEnd),
    };
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

  function collectSessionPayloadForDate(dateLocal) {
    const distanceInputs = Array.from(bodyEl.querySelectorAll(`.plan-session-distance[data-date="${dateLocal}"]`));
    distanceInputs.sort(
      (a, b) => Number.parseInt(a.dataset.sessionIndex || "0", 10) - Number.parseInt(b.dataset.sessionIndex || "0", 10),
    );
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

  async function savePlanRow(dateLocal, payload, nextFocusDate, nextField) {
    try {
      const response = await fetch(`/plan/day/${encodeURIComponent(dateLocal)}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
      const result = await response.json();
      if (!response.ok || result.status !== "ok") {
        throw new Error(String((result && result.error) || "Failed to save plan day"));
      }
      setPendingFocus(nextFocusDate, nextField);
      await loadPlan(centerDateEl.value);
    } catch (err) {
      if (metaEl) {
        metaEl.textContent = String(err && err.message ? err.message : "Failed to save plan row");
      }
    }
  }

  function selectorForField(field, dateValue) {
    const dateEscaped = String(dateValue || "");
    return `.plan-session-distance[data-date="${dateEscaped}"][data-session-index="0"]`;
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
    select.addEventListener("change", () => {
      saveSessionPayload(row, index, rows, row.date, "distance");
    });
    select.addEventListener("keydown", (event) => {
      if (!event.ctrlKey || (event.key !== "ArrowDown" && event.key !== "ArrowUp")) {
        return;
      }
      event.preventDefault();
      focusNeighbor(rows, index, "distance", event.key === "ArrowDown" ? 1 : -1);
    });
    return select;
  }

  function buildSessionWorkoutInput(row, index, rows, session, sessionIndex, runTypeSelect) {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "plan-workout-input plan-session-workout";
    input.dataset.date = row.date;
    input.dataset.sessionIndex = String(sessionIndex);
    input.setAttribute("list", WORKOUT_PRESET_LIST_ID);
    input.placeholder = "Workout shorthand";
    input.title = "Workout shorthand for SOS session. Press Enter to save.";
    input.value = String((session && (session.planned_workout || session.workout_code)) || runTypeSelect.dataset.plannedWorkout || "");
    runTypeSelect.dataset.plannedWorkout = input.value;

    input.addEventListener("input", () => {
      runTypeSelect.dataset.plannedWorkout = String(input.value || "");
    });
    input.addEventListener("change", () => {
      runTypeSelect.dataset.plannedWorkout = String(input.value || "");
      saveSessionPayload(row, index, rows, row.date, "distance");
    });
    input.addEventListener("keydown", (event) => {
      if (!event.ctrlKey || (event.key !== "ArrowDown" && event.key !== "ArrowUp")) {
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
    return input;
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
      input.addEventListener("keydown", (event) => {
        if (sessionIndex === 0 && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
          event.preventDefault();
          focusNeighbor(rows, index, "distance", event.key === "ArrowDown" ? 1 : -1);
          return;
        }

        if (event.ctrlKey && event.shiftKey) {
          const mapped = runTypeHotkeys[String(event.key || "").toLowerCase()];
          if (mapped && runTypeOptions.includes(mapped)) {
            event.preventDefault();
            const sessionTypeSelect = bodyEl.querySelector(
              `.plan-session-type[data-date="${row.date}"][data-session-index="${sessionIndex}"]`,
            );
            if (sessionTypeSelect) sessionTypeSelect.value = mapped;
            saveSessionPayload(row, index, rows, row.date, "distance");
            return;
          }
        }

        if (event.key !== "Enter") return;
        event.preventDefault();
        const nextRow = rowAt(rows, index + 1);
        saveSessionPayload(row, index, rows, nextRow ? nextRow.date : "", "distance");
      });
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
        rowEl.classList.add("plan-session-row-sos");
        rowEl.appendChild(buildSessionWorkoutInput(row, index, rows, session, sessionIndex, runTypeSelect));
      }
      editor.appendChild(rowEl);
    }
    return editor;
  }

  function renderRows(rows) {
    bodyEl.textContent = "";
    let weekIndex = -1;
    let currentWeekKey = "";
    for (let index = 0; index < rows.length; index += 1) {
      const row = rows[index];
      const tr = document.createElement("tr");
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
      const dateDetail = document.createElement("span");
      dateDetail.className = "date-detail";
      dateDetail.textContent = `A ${formatMiles(row && row.actual_miles, 1)} | E ${formatMiles(row && row.effective_miles, 1)} | Δ ${formatSigned(row && row.day_delta, 1)}`;
      dateTd.appendChild(dateDetail);
      if (isWeekStart && weekInfo.weekKey) {
        const badge = document.createElement("span");
        badge.className = "week-badge";
        badge.textContent = `Week of ${weekInfo.weekKey}`;
        badge.title = `${weekInfo.weekKey} to ${weekInfo.weekEndKey}`;
        dateTd.appendChild(badge);
      }
      tr.appendChild(dateTd);

      const distanceTd = document.createElement("td");
      distanceTd.className = "distance-cell";
      distanceTd.appendChild(buildSessionDistanceEditor(row, index, rows));
      tr.appendChild(distanceTd);

      const runTypeTd = document.createElement("td");
      runTypeTd.className = "run-type-cell";
      runTypeTd.appendChild(buildSessionTypeEditor(row, index, rows));
      tr.appendChild(runTypeTd);

      if (row && row.show_week_metrics) {
        const weekTd = makeCell(formatMiles(row.weekly_total, 1), "metric-week");
        weekTd.rowSpan = Math.max(1, Number(row.week_row_span) || 1);
        tr.appendChild(weekTd);
        const wowTd = makeCell(formatPct(row && row.wow_change), wowBandFromValue(row && row.wow_change));
        wowTd.rowSpan = Math.max(1, Number(row.week_row_span) || 1);
        tr.appendChild(wowTd);
      }
      tr.appendChild(makeCell(formatPct(row && row.long_pct), metricBandClass(row && row.bands && row.bands.long_pct)));

      if (row && row.show_month_metrics) {
        const monthTd = makeCell(formatMiles(row.monthly_total, 1), "metric-month");
        monthTd.rowSpan = Math.max(1, Number(row.month_row_span) || 1);
        tr.appendChild(monthTd);
        const momTd = makeCell(formatPct(row && row.mom_change), wowBandFromValue(row && row.mom_change));
        momTd.rowSpan = Math.max(1, Number(row.month_row_span) || 1);
        tr.appendChild(momTd);
      }
      tr.appendChild(makeCell(formatMiles(row && row.t7_miles, 1), "metric-neutral"));
      tr.appendChild(makeCell(formatRatio(row && row.t7_p7_ratio, 1), metricBandClass(row && row.bands && row.bands.t7_p7_ratio)));
      tr.appendChild(makeCell(formatMiles(row && row.t30_miles, 1), "metric-neutral"));
      tr.appendChild(makeCell(formatRatio(row && row.t30_p30_ratio, 1), metricBandClass(row && row.bands && row.bands.t30_p30_ratio)));
      tr.appendChild(makeCell(formatRatio(row && row.avg30_miles_per_day, 2), "metric-neutral"));
      tr.appendChild(makeCell(formatRatio(row && row.mi_t30_ratio, 1), metricBandClass(row && row.bands && row.bands.mi_t30_ratio)));

      bodyEl.appendChild(tr);
    }
  }

  function setMeta(payload) {
    if (!metaEl) return;
    if (!payload || payload.status !== "ok") {
      metaEl.textContent = "Data unavailable";
      return;
    }
    metaEl.textContent = `${payload.start_date} to ${payload.end_date} | Center ${payload.center_date} | ${payload.timezone}`;
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

  async function loadPlan(centerDate) {
    const params = new URLSearchParams();
    params.set("window_days", "14");
    const targetDate = String(centerDate || centerDateEl.value || "").trim();
    if (targetDate) {
      params.set("center_date", targetDate);
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
      runTypeOptions = Array.isArray(payload.run_type_options) ? payload.run_type_options : [""];
      setMeta(payload);
      setSummary(payload);
      renderRows(Array.isArray(payload.rows) ? payload.rows : []);
      applyPendingFocus();
    } catch (_err) {
      bodyEl.innerHTML = "<tr><td colspan=\"15\">Network error while loading plan data.</td></tr>";
      if (metaEl) metaEl.textContent = "Network error";
    }
  }

  reloadBtn.addEventListener("click", () => loadPlan(centerDateEl.value));
  todayBtn.addEventListener("click", () => {
    const today = new Date();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");
    const isoDate = `${today.getFullYear()}-${month}-${day}`;
    centerDateEl.value = isoDate;
    loadPlan(isoDate);
  });
  centerDateEl.addEventListener("change", () => loadPlan(centerDateEl.value));

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

  ensureWorkoutPresetList();
  loadPlan(centerDateEl.value);
})();
