(function () {
  const bodyEl = document.getElementById("planTableBody");
  const metaEl = document.getElementById("planTopMeta");
  const summaryEl = document.getElementById("planSummary");
  const centerDateEl = document.getElementById("planCenterDate");
  const reloadBtn = document.getElementById("planReloadBtn");
  const todayBtn = document.getElementById("planTodayBtn");

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

  function sessionsFromRow(row, distanceValue) {
    const explicit = Array.isArray(row && row.planned_sessions) ? row.planned_sessions : [];
    const cleanExplicit = explicit
      .map((value) => Number.parseFloat(String(value)))
      .filter((value) => Number.isFinite(value) && value > 0);
    if (cleanExplicit.length > 0) return cleanExplicit;

    const parsed = parseDistanceExpression(distanceValue);
    if (parsed.length > 0) return parsed;
    const fallback = Number.parseFloat(String(row && row.planned_miles));
    return Number.isFinite(fallback) && fallback > 0 ? [fallback] : [];
  }

  function serializeSessionsForApi(values) {
    return values
      .map((value, index) => ({
        ordinal: index + 1,
        planned_miles: value,
      }))
      .filter((item) => Number.isFinite(item.planned_miles) && item.planned_miles > 0);
  }

  function setPendingFocus(dateValue, field) {
    pendingFocus = {
      date: String(dateValue || ""),
      field: field === "run_type" || field === "complete" ? field : "distance",
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
      metaEl.textContent = String(err && err.message ? err.message : "Failed to save plan row");
    }
  }

  function selectorForField(field, dateValue) {
    const dateEscaped = String(dateValue || "");
    if (field === "run_type") return `.plan-run-type[data-date="${dateEscaped}"]`;
    if (field === "complete") return `.plan-complete-toggle[data-date="${dateEscaped}"]`;
    return `.plan-distance-input[data-date="${dateEscaped}"]`;
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

  function buildRunTypeSelect(row, index, rows) {
    const select = document.createElement("select");
    select.className = "plan-run-type";
    select.dataset.date = row.date;
    for (const optionValue of runTypeOptions) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue || "--";
      if (optionValue === String(row.run_type || "")) {
        option.selected = true;
      }
      select.appendChild(option);
    }
    select.addEventListener("change", () => {
      const distanceInput = bodyEl.querySelector(`.plan-distance-input[data-date="${row.date}"]`);
      const distanceValue = distanceInput && typeof distanceInput.value === "string" ? distanceInput.value : String(row.planned_input || "");
      void savePlanRow(
        row.date,
        {
          distance: distanceValue,
          run_type: select.value,
        },
        row.date,
        "run_type",
      );
    });
    select.addEventListener("keydown", (event) => {
      if (!event.ctrlKey || (event.key !== "ArrowDown" && event.key !== "ArrowUp")) {
        return;
      }
      event.preventDefault();
      focusNeighbor(rows, index, "run_type", event.key === "ArrowDown" ? 1 : -1);
    });
    return select;
  }

  function buildDistanceInput(row, index, rows) {
    const input = document.createElement("input");
    input.className = "plan-distance-input";
    input.type = "text";
    input.dataset.date = row.date;
    input.value = String(row.planned_input || "");
    input.title = "Use single mileage (6.2) or doubles/triples syntax (6+4 or 5+3+2). Hotkeys: Ctrl+Shift+E/R/S/L/M/T/X/H/1/2.";

    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        focusNeighbor(rows, index, "distance", event.key === "ArrowDown" ? 1 : -1);
        return;
      }

      if (event.ctrlKey && event.shiftKey) {
        const mapped = runTypeHotkeys[String(event.key || "").toLowerCase()];
        if (mapped && runTypeOptions.includes(mapped)) {
          event.preventDefault();
          const runTypeSelect = bodyEl.querySelector(`.plan-run-type[data-date="${row.date}"]`);
          if (runTypeSelect) runTypeSelect.value = mapped;
          void savePlanRow(
            row.date,
            {
              distance: input.value,
              run_type: mapped,
            },
            row.date,
            "distance",
          );
          return;
        }
      }

      if (event.key !== "Enter") {
        return;
      }
      event.preventDefault();
      const nextRow = rowAt(rows, index + 1);
      const runTypeSelect = bodyEl.querySelector(`.plan-run-type[data-date="${row.date}"]`);
      const runTypeValue = runTypeSelect && typeof runTypeSelect.value === "string" ? runTypeSelect.value : String(row.run_type || "");
      void savePlanRow(
        row.date,
        {
          distance: input.value,
          run_type: runTypeValue,
        },
        nextRow ? nextRow.date : "",
        "distance",
      );
    });
    return input;
  }

  function buildSessionControls(row, index, rows) {
    const controls = document.createElement("div");
    controls.className = "session-actions";

    const label = document.createElement("span");
    label.className = "session-label";
    const baseSessions = sessionsFromRow(row, row && row.planned_input);
    label.textContent = baseSessions.length > 0 ? baseSessions.map((item) => formatSessionValue(item)).join(" + ") : "single";
    controls.appendChild(label);

    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "session-btn";
    addBtn.textContent = "+ Sess";
    addBtn.title = "Add another session to this day.";
    addBtn.addEventListener("click", () => {
      const distanceInput = bodyEl.querySelector(`.plan-distance-input[data-date="${row.date}"]`);
      const runTypeSelect = bodyEl.querySelector(`.plan-run-type[data-date="${row.date}"]`);
      const runTypeValue = runTypeSelect && typeof runTypeSelect.value === "string" ? runTypeSelect.value : String(row.run_type || "");
      const currentSessions = sessionsFromRow(row, distanceInput ? distanceInput.value : row.planned_input);
      currentSessions.push(1.0);
      const nextPayload = serializeSessionsForApi(currentSessions);
      void savePlanRow(
        row.date,
        {
          sessions: nextPayload,
          run_type: runTypeValue,
        },
        row.date,
        "distance",
      );
    });
    controls.appendChild(addBtn);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "session-btn";
    removeBtn.textContent = "- Sess";
    removeBtn.title = "Remove the last session from this day.";
    removeBtn.disabled = baseSessions.length <= 1;
    removeBtn.addEventListener("click", () => {
      const distanceInput = bodyEl.querySelector(`.plan-distance-input[data-date="${row.date}"]`);
      const runTypeSelect = bodyEl.querySelector(`.plan-run-type[data-date="${row.date}"]`);
      const runTypeValue = runTypeSelect && typeof runTypeSelect.value === "string" ? runTypeSelect.value : String(row.run_type || "");
      const currentSessions = sessionsFromRow(row, distanceInput ? distanceInput.value : row.planned_input);
      currentSessions.pop();
      const nextPayload = serializeSessionsForApi(currentSessions);
      if (nextPayload.length === 0) {
        void savePlanRow(
          row.date,
          {
            distance: "",
            run_type: runTypeValue,
          },
          row.date,
          "distance",
        );
        return;
      }
      void savePlanRow(
        row.date,
        {
          sessions: nextPayload,
          run_type: runTypeValue,
        },
        row.date,
        "distance",
      );
    });
    controls.appendChild(removeBtn);

    return controls;
  }

  function renderRows(rows) {
    bodyEl.textContent = "";
    for (let index = 0; index < rows.length; index += 1) {
      const row = rows[index];
      const tr = document.createElement("tr");
      if (row && row.is_today) tr.classList.add("is-today");

      const doneTd = document.createElement("td");
      doneTd.className = "done-cell";
      const doneInput = document.createElement("input");
      doneInput.type = "checkbox";
      doneInput.checked = !!(row && row.is_complete);
      doneInput.className = "plan-complete-toggle";
      doneInput.dataset.date = row.date;
      doneInput.addEventListener("change", () => {
        const distanceInput = bodyEl.querySelector(`.plan-distance-input[data-date="${row.date}"]`);
        const runTypeSelect = bodyEl.querySelector(`.plan-run-type[data-date="${row.date}"]`);
        const distanceValue = distanceInput && typeof distanceInput.value === "string" ? distanceInput.value : String(row.planned_input || "");
        const runTypeValue = runTypeSelect && typeof runTypeSelect.value === "string" ? runTypeSelect.value : String(row.run_type || "");
        void savePlanRow(
          row.date,
          {
            distance: distanceValue,
            run_type: runTypeValue,
            is_complete: doneInput.checked,
          },
          row.date,
          "complete",
        );
      });
      doneInput.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
        event.preventDefault();
        focusNeighbor(rows, index, "complete", event.key === "ArrowDown" ? 1 : -1);
      });
      doneTd.appendChild(doneInput);
      if (row && row.completion_source === "manual") {
        const autoBtn = document.createElement("button");
        autoBtn.type = "button";
        autoBtn.className = "auto-reset-btn";
        autoBtn.textContent = "Auto";
        autoBtn.title = "Reset completion to auto-sync with actual mileage";
        autoBtn.addEventListener("click", () => {
          const distanceInput = bodyEl.querySelector(`.plan-distance-input[data-date="${row.date}"]`);
          const runTypeSelect = bodyEl.querySelector(`.plan-run-type[data-date="${row.date}"]`);
          const distanceValue = distanceInput && typeof distanceInput.value === "string" ? distanceInput.value : String(row.planned_input || "");
          const runTypeValue = runTypeSelect && typeof runTypeSelect.value === "string" ? runTypeSelect.value : String(row.run_type || "");
          void savePlanRow(
            row.date,
            {
              distance: distanceValue,
              run_type: runTypeValue,
              is_complete: null,
            },
            row.date,
            "complete",
          );
        });
        doneTd.appendChild(autoBtn);
      }
      tr.appendChild(doneTd);

      tr.appendChild(makeCell(String((row && row.date) || "--")));

      const distanceTd = document.createElement("td");
      distanceTd.className = "distance-cell";
      distanceTd.appendChild(buildDistanceInput(row, index, rows));
      distanceTd.appendChild(buildSessionControls(row, index, rows));
      const detail = document.createElement("span");
      detail.className = "distance-detail";
      detail.textContent = `A ${formatMiles(row && row.actual_miles, 1)} | E ${formatMiles(row && row.effective_miles, 1)} | Δ ${formatSigned(row && row.day_delta, 1)}`;
      distanceTd.appendChild(detail);
      tr.appendChild(distanceTd);

      const runTypeTd = document.createElement("td");
      runTypeTd.appendChild(buildRunTypeSelect(row, index, rows));
      tr.appendChild(runTypeTd);

      if (row && row.show_week_metrics) {
        const weekTd = makeCell(formatMiles(row.weekly_total, 1), "metric-week");
        weekTd.rowSpan = Math.max(1, Number(row.week_row_span) || 1);
        tr.appendChild(weekTd);
      }
      tr.appendChild(makeCell(formatPct(row && row.wow_change), wowBandFromValue(row && row.wow_change)));
      tr.appendChild(makeCell(formatPct(row && row.long_pct), metricBandClass(row && row.bands && row.bands.long_pct)));

      if (row && row.show_month_metrics) {
        const monthTd = makeCell(formatMiles(row.monthly_total, 1), "metric-month");
        monthTd.rowSpan = Math.max(1, Number(row.month_row_span) || 1);
        tr.appendChild(monthTd);
      }
      tr.appendChild(makeCell(formatPct(row && row.mom_change), wowBandFromValue(row && row.mom_change)));

      tr.appendChild(makeCell(formatRatio(row && row.mi_t30_ratio, 1), metricBandClass(row && row.bands && row.bands.mi_t30_ratio)));
      tr.appendChild(makeCell(formatMiles(row && row.t7_miles, 1), "metric-neutral"));
      tr.appendChild(makeCell(formatRatio(row && row.t7_p7_ratio, 1), metricBandClass(row && row.bands && row.bands.t7_p7_ratio)));
      tr.appendChild(makeCell(formatMiles(row && row.t30_miles, 1), "metric-neutral"));
      tr.appendChild(makeCell(formatRatio(row && row.t30_p30_ratio, 1), metricBandClass(row && row.bands && row.bands.t30_p30_ratio)));
      tr.appendChild(makeCell(formatRatio(row && row.avg30_miles_per_day, 2), "metric-neutral"));

      bodyEl.appendChild(tr);
    }
  }

  function setMeta(payload) {
    if (!payload || payload.status !== "ok") {
      metaEl.textContent = "Data unavailable";
      return;
    }
    metaEl.textContent = `${payload.start_date} to ${payload.end_date} | Center ${payload.center_date} | ${payload.timezone}`;
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
      metaEl.textContent = "Loading...";
      const response = await fetch(`/plan/data.json?${params.toString()}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") {
        const error = String((payload && payload.error) || "Failed to load plan data");
        bodyEl.innerHTML = `<tr><td colspan="15">${error}</td></tr>`;
        metaEl.textContent = "Load failed";
        return;
      }
      if (typeof payload.center_date === "string" && payload.center_date) {
        centerDateEl.value = payload.center_date;
      }
      runTypeOptions = Array.isArray(payload.run_type_options) ? payload.run_type_options : [""];
      setMeta(payload);
      setSummary(payload);
      renderRows(Array.isArray(payload.rows) ? payload.rows : []);
      applyPendingFocus();
    } catch (_err) {
      bodyEl.innerHTML = "<tr><td colspan=\"15\">Network error while loading plan data.</td></tr>";
      metaEl.textContent = "Network error";
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

  loadPlan(centerDateEl.value);
})();
