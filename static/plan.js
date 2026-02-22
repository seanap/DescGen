(function () {
  const bodyEl = document.getElementById("planTableBody");
  const metaEl = document.getElementById("planTopMeta");
  const centerDateEl = document.getElementById("planCenterDate");
  const reloadBtn = document.getElementById("planReloadBtn");
  const todayBtn = document.getElementById("planTodayBtn");

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

  function renderRows(rows) {
    bodyEl.textContent = "";
    for (const row of rows) {
      const tr = document.createElement("tr");
      if (row && row.is_today) tr.classList.add("is-today");

      const doneTd = document.createElement("td");
      const doneChip = document.createElement("span");
      doneChip.className = `done-chip ${row && row.is_complete ? "done" : "pending"}`;
      doneChip.textContent = row && row.is_complete ? "OK" : "";
      doneTd.appendChild(doneChip);
      tr.appendChild(doneTd);

      tr.appendChild(makeCell(String((row && row.date) || "--")));

      const distanceTd = document.createElement("td");
      const main = document.createElement("span");
      main.className = "distance-main";
      main.textContent = formatMiles(row && row.effective_miles, 1);
      const detail = document.createElement("span");
      detail.className = "distance-detail";
      detail.textContent = `A ${formatMiles(row && row.actual_miles, 1)} | P ${formatMiles(row && row.planned_miles, 1)}`;
      distanceTd.appendChild(main);
      distanceTd.appendChild(detail);
      tr.appendChild(distanceTd);

      tr.appendChild(makeCell(String((row && row.run_type) || "")));

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
      setMeta(payload);
      renderRows(Array.isArray(payload.rows) ? payload.rows : []);
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
