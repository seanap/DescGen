const SECTION_LIBRARY = [
  {
    id: "streak",
    label: "Streak Header",
    enabled: true,
    template: "🏆 {{ streak_days }} days in a row",
  },
  {
    id: "notables",
    label: "Smashrun Notables",
    enabled: true,
    template: "{% for notable in notables %}🏅 {{ notable }}\\n{% endfor %}",
  },
  {
    id: "achievements",
    label: "Intervals Achievements",
    enabled: true,
    template: "{% for achievement in achievements %}🏅 {{ achievement }}\\n{% endfor %}",
  },
  {
    id: "weather",
    label: "Weather + AQI",
    enabled: true,
    template:
      "🌤️🌡️ Misery Index: {{ weather.misery_index }} {{ weather.misery_description }} | 🏭 AQI: {{ weather.aqi }}{{ weather.aqi_description }}",
  },
  {
    id: "crono",
    label: "Fuel / Energy",
    enabled: true,
    template: "{% if crono.line %}{{ crono.line }}{% endif %}",
  },
  {
    id: "readiness",
    label: "Readiness Line",
    enabled: true,
    template:
      "🌤️🚦 Training Readiness: {{ training.readiness_score }} {{ training.readiness_emoji }} | 💗 {{ training.resting_hr }} | 💤 {{ training.sleep_score }}",
  },
  {
    id: "activity_core",
    label: "Latest Activity Core",
    enabled: true,
    template:
      "👟🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} | 🏔️ {{ activity.elevation_feet }}' | 🕓 {{ activity.time }} | 🍺 {{ activity.beers }}",
  },
  {
    id: "activity_power",
    label: "Cadence / Power / HR",
    enabled: true,
    template:
      "👟👣 {{ activity.cadence_spm }}spm | 💼 {{ activity.work }} | ⚡ {{ activity.norm_power }} | 💓 {{ activity.average_hr }} | ⚙️{{ activity.efficiency }}",
  },
  {
    id: "status",
    label: "Training Status",
    enabled: true,
    template:
      "🚄 {{ training.status_emoji }} {{ training.status_key }} | {{ training.aerobic_te }} : {{ training.anaerobic_te }} - {{ training.te_label }}",
  },
  {
    id: "icu_summary",
    label: "Intervals Summary",
    enabled: true,
    template: "🚄 {{ intervals.summary }}",
  },
  {
    id: "load",
    label: "Load Balance",
    enabled: true,
    template:
      "🚄 🏋️ {{ training.chronic_load }} | 💦 {{ training.acute_load }} | 🗿 {{ training.load_ratio }} - {{ training.acwr_status }} {{ training.acwr_status_emoji }}",
  },
  {
    id: "vo2",
    label: "VO2 / Endurance / Hill",
    enabled: true,
    template:
      "❤️‍🔥 {{ training.vo2 }} | ♾ Endur: {{ training.endurance_score }} | 🗻 Hill: {{ training.hill_score }}",
  },
  {
    id: "week",
    label: "7-Day Summary",
    enabled: true,
    template:
      "7️⃣ Past 7 days:\\n🏃 {{ periods.week.gap }} | 🗺️ {{ periods.week.distance_miles }} | 🏔️ {{ periods.week.elevation_feet }}' | 🕓 {{ periods.week.duration }} | 🍺 {{ periods.week.beers }}",
  },
  {
    id: "month",
    label: "30-Day Summary",
    enabled: true,
    template:
      "📅 Past 30 days:\\n🏃 {{ periods.month.gap }} | 🗺️ {{ periods.month.distance_miles }} | 🏔️ {{ periods.month.elevation_feet }}' | 🕓 {{ periods.month.duration }} | 🍺 {{ periods.month.beers }}",
  },
  {
    id: "year",
    label: "Year Summary",
    enabled: true,
    template:
      "🌍 This Year:\\n🏃 {{ periods.year.gap }} | 🗺️ {{ periods.year.distance_miles }} | 🏔️ {{ periods.year.elevation_feet }}' | 🕓 {{ periods.year.duration }} | 🍺 {{ periods.year.beers }}",
  },
];

const state = {
  templateActive: "",
  templateDefault: "",
  schema: null,
  sections: SECTION_LIBRARY.map((x) => ({ ...x })),
};

const elements = {
  topStatus: document.getElementById("topStatus"),
  templateEditor: document.getElementById("templateEditor"),
  previewText: document.getElementById("previewText"),
  previewMeta: document.getElementById("previewMeta"),
  validationPane: document.getElementById("validationPane"),
  schemaList: document.getElementById("schemaList"),
  schemaMeta: document.getElementById("schemaMeta"),
  schemaSearch: document.getElementById("schemaSearch"),
  simpleSections: document.getElementById("simpleSections"),
};

function setStatus(text, tone = "neutral") {
  elements.topStatus.textContent = text;
  elements.topStatus.dataset.tone = tone;
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, payload };
}

function getEditorText() {
  return elements.templateEditor.value;
}

function setEditorText(templateText) {
  elements.templateEditor.value = templateText || "";
}

function updateValidationPane(result, ok) {
  const pane = elements.validationPane;
  pane.classList.remove("ok", "error");

  if (!result) {
    pane.textContent = "Validation output will appear here.";
    return;
  }

  const lines = [];
  if (ok) {
    pane.classList.add("ok");
    lines.push("Template is valid.");
  } else {
    pane.classList.add("error");
    lines.push("Template has validation issues.");
  }

  const validation = result.validation || {};
  if (Array.isArray(validation.errors) && validation.errors.length > 0) {
    lines.push("Errors:");
    for (const error of validation.errors) lines.push(`- ${error}`);
  }
  if (Array.isArray(validation.warnings) && validation.warnings.length > 0) {
    lines.push("Warnings:");
    for (const warning of validation.warnings) lines.push(`- ${warning}`);
  }
  if (Array.isArray(validation.undeclared_variables)) {
    lines.push(`Undeclared variables: ${validation.undeclared_variables.join(", ") || "none"}`);
  }

  pane.textContent = lines.join("\n");
}

function renderSchemaCatalog(filterText = "") {
  const schema = state.schema;
  elements.schemaList.innerHTML = "";

  if (!schema || !Array.isArray(schema.groups) || schema.groups.length === 0) {
    elements.schemaMeta.textContent = "No schema context yet. Run /rerun/latest once.";
    return;
  }

  const q = filterText.trim().toLowerCase();
  let visibleFields = 0;

  for (const group of schema.groups) {
    const fields = (group.fields || []).filter((field) => {
      if (!q) return true;
      return (
        String(field.path || "").toLowerCase().includes(q) ||
        String(field.type || "").toLowerCase().includes(q)
      );
    });

    if (fields.length === 0) continue;
    visibleFields += fields.length;

    const card = document.createElement("section");
    card.className = "catalog-group";

    const h = document.createElement("h3");
    h.textContent = `${group.group} (${fields.length})`;
    card.appendChild(h);

    for (const field of fields) {
      const row = document.createElement("div");
      row.className = "field";

      const key = document.createElement("div");
      key.className = "field-key";
      key.textContent = `{{ ${field.path} }}`;

      const type = document.createElement("div");
      type.className = "field-type";
      type.textContent = `${field.type} | sample: ${JSON.stringify(field.sample)}`;

      row.appendChild(key);
      row.appendChild(type);
      card.appendChild(row);
    }

    elements.schemaList.appendChild(card);
  }

  elements.schemaMeta.textContent = `${visibleFields} fields shown`;
}

function moveSection(fromIndex, toIndex) {
  if (toIndex < 0 || toIndex >= state.sections.length) return;
  const [item] = state.sections.splice(fromIndex, 1);
  state.sections.splice(toIndex, 0, item);
  renderSimpleSections();
}

function renderSimpleSections() {
  elements.simpleSections.innerHTML = "";

  state.sections.forEach((section, index) => {
    const row = document.createElement("div");
    row.className = "section-row";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = section.enabled;
    checkbox.addEventListener("change", () => {
      section.enabled = checkbox.checked;
    });

    const label = document.createElement("label");
    label.textContent = section.label;

    const controls = document.createElement("div");
    controls.className = "row-controls";

    const up = document.createElement("button");
    up.className = "mini-btn";
    up.textContent = "↑";
    up.title = "Move up";
    up.addEventListener("click", () => moveSection(index, index - 1));

    const down = document.createElement("button");
    down.className = "mini-btn";
    down.textContent = "↓";
    down.title = "Move down";
    down.addEventListener("click", () => moveSection(index, index + 1));

    controls.appendChild(up);
    controls.appendChild(down);

    row.appendChild(checkbox);
    row.appendChild(label);
    row.appendChild(controls);

    elements.simpleSections.appendChild(row);
  });
}

function buildTemplateFromSimple() {
  const chunks = state.sections
    .filter((section) => section.enabled)
    .map((section) => section.template)
    .filter(Boolean);

  if (chunks.length === 0) {
    return "{{ '' }}";
  }

  return chunks.join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === name);
  });
  document.querySelectorAll(".tabpanel").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `tab${name.charAt(0).toUpperCase()}${name.slice(1)}`);
  });
}

async function loadEditorBootstrap() {
  setStatus("Loading editor data...");
  const [activeRes, defaultRes, schemaRes] = await Promise.all([
    requestJSON("/editor/template"),
    requestJSON("/editor/template/default"),
    requestJSON("/editor/schema"),
  ]);

  if (!activeRes.ok || !defaultRes.ok || !schemaRes.ok) {
    setStatus("Failed to load editor data", "error");
    return;
  }

  state.templateActive = activeRes.payload.template || "";
  state.templateDefault = defaultRes.payload.template || "";
  state.schema = schemaRes.payload.schema || null;

  setEditorText(state.templateActive);
  renderSchemaCatalog("");
  renderSimpleSections();

  const isCustom = Boolean(activeRes.payload.is_custom);
  setStatus(isCustom ? "Loaded custom template" : "Loaded default template", "ok");
}

async function validateTemplate() {
  const template = getEditorText();
  const res = await requestJSON("/editor/validate", {
    method: "POST",
    body: JSON.stringify({ template }),
  });

  updateValidationPane(res.payload, res.ok);
  setStatus(res.ok ? "Validation passed" : "Validation failed", res.ok ? "ok" : "error");
}

async function previewTemplate() {
  const template = getEditorText();
  const res = await requestJSON("/editor/preview", {
    method: "POST",
    body: JSON.stringify({ template }),
  });

  if (!res.ok) {
    elements.previewMeta.textContent = res.payload.error || "Preview failed";
    elements.previewText.textContent = "";
    setStatus("Preview failed", "error");
    return;
  }

  elements.previewText.textContent = res.payload.preview || "";
  elements.previewMeta.textContent = `Rendered length: ${res.payload.length} chars`;
  setStatus("Preview updated", "ok");
}

async function saveTemplate() {
  const template = getEditorText();
  const res = await requestJSON("/editor/template", {
    method: "PUT",
    body: JSON.stringify({ template }),
  });

  if (!res.ok) {
    updateValidationPane(res.payload, false);
    setStatus("Save failed", "error");
    return;
  }

  updateValidationPane(res.payload, true);
  setStatus("Template saved", "ok");
}

async function copyPreview() {
  const text = elements.previewText.textContent || "";
  if (!text) {
    setStatus("Nothing to copy", "error");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    setStatus("Preview copied to clipboard", "ok");
  } catch (_err) {
    setStatus("Clipboard copy failed", "error");
  }
}

function bindUI() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });

  document.getElementById("btnLoadActive").addEventListener("click", () => {
    setEditorText(state.templateActive);
    setStatus("Loaded active template", "ok");
  });

  document.getElementById("btnLoadDefault").addEventListener("click", () => {
    setEditorText(state.templateDefault);
    setStatus("Loaded default template", "ok");
  });

  document.getElementById("btnValidate").addEventListener("click", validateTemplate);
  document.getElementById("btnPreview").addEventListener("click", previewTemplate);
  document.getElementById("btnSave").addEventListener("click", saveTemplate);
  document.getElementById("btnCopyPreview").addEventListener("click", copyPreview);

  document.getElementById("btnSimpleApply").addEventListener("click", () => {
    setEditorText(buildTemplateFromSimple());
    switchTab("advanced");
    setStatus("Builder output applied to advanced editor", "ok");
  });

  document.getElementById("btnSimpleReset").addEventListener("click", () => {
    state.sections = SECTION_LIBRARY.map((x) => ({ ...x }));
    renderSimpleSections();
    setStatus("Builder reset", "ok");
  });

  elements.schemaSearch.addEventListener("input", (event) => {
    renderSchemaCatalog(event.target.value || "");
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  bindUI();
  updateValidationPane(null, true);
  await loadEditorBootstrap();
});
