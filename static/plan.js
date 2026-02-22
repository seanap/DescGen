(function () {
  const bodyEl = document.getElementById("planTableBody");
  const metaEl = document.getElementById("planTopMeta");
  const centerDateEl = document.getElementById("planCenterDate");
  const reloadBtn = document.getElementById("planReloadBtn");
  const todayBtn = document.getElementById("planTodayBtn");

  let runTypeOptions = [""];
  let pendingFocusDate = "";

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

  async function savePlanRow(dateLocal, payload, nextDate) {
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
      pendingFocusDate = String(nextDate || "");
      await loadPlan(centerDateEl.value);
    } catch (err) {
      metaEl.textContent = String(err && err.message ? err.message : "Failed to save plan row");
    }
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
          is_complete: !!row.is_complete,
        },
        rows[index + 1] ? rows[index + 1].date : "",
      );
    });
    return select;
  }

  function buildDistanceInput(row, index, rows) {
    const input = document.createElement("input");
    input.className = "plan-distance-input";
    input.type = "text";
    input.dataset.date = row.date;
    input.value = String(row.planned_input || "");
    input.title = "Use single mileage (6.2) or doubles/triples syntax (6+4 or 5+3+2).";

    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") {
        return;
      }
      event.preventDefault();
      const nextDate = rows[index + 1] ? rows[index + 1].date : "";
      const runTypeSelect = bodyEl.querySelector(`.plan-run-type[data-date="${row.date}"]`);
      const runTypeValue = runTypeSelect && typeof runTypeSelect.value === "string" ? runTypeSelect.value : String(row.run_type || "");
      void savePlanRow(
        row.date,
        {
          distance: input.value,
          run_type: runTypeValue,
          is_complete: !!row.is_complete,
        },
        nextDate,
      );
    });
    return input;
  }

  function renderRows(rows) {
    bodyEl.textContent = "";
    for (let index = 0; index < rows.length; index += 1) {
      const row = rows[index];
      const tr = document.createElement("tr");
      if (row && row.is_today) tr.classList.add("is-today");

      const doneTd = document.createElement("td");
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
          "",
        );
      });
      doneTd.appendChild(doneInput);
      tr.appendChild(doneTd);

      tr.appendChild(makeCell(String((row && row.date) || "--")));

      const distanceTd = document.createElement("td");
      distanceTd.className = "distance-cell";
      distanceTd.appendChild(buildDistanceInput(row, index, rows));
      const detail = document.createElement("span");
      detail.className = "distance-detail";
      detail.textContent = `A ${formatMiles(row && row.actual_miles, 1)} | E ${formatMiles(row && row.effective_miles, 1)}`;
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

  function applyPendingFocus() {
    if (!pendingFocusDate) return;
    const target = bodyEl.querySelector(`.plan-distance-input[data-date="${pendingFocusDate}"]`);
    pendingFocusDate = "";
    if (!target) return;
    target.focus();
    target.select();
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
