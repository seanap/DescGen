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
    template: "{% for notable in notables %}🏅 {{ notable }}\n{% endfor %}",
  },
  {
    id: "achievements",
    label: "Intervals Achievements",
    enabled: true,
    template: "{% for achievement in achievements %}🏅 {{ achievement }}\n{% endfor %}",
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
    template:
      "{% if crono.average_net_kcal_per_day is defined and crono.average_net_kcal_per_day is not none %}🔥 7d avg daily Energy Balance:{{ '%+.0f'|format(crono.average_net_kcal_per_day) }} kcal{% if crono.average_status %} ({{ crono.average_status }}){% endif %}{% if crono.protein_g and crono.protein_g > 0 %} | 🥩:{{ crono.protein_g|round|int }}g{% endif %}{% if crono.carbs_g and crono.carbs_g > 0 %} | 🍞:{{ crono.carbs_g|round|int }}g{% endif %}{% elif crono.line %}{{ crono.line }}{% endif %}",
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
      "7️⃣ Past 7 days:\n🏃 {{ periods.week.gap }} | 🗺️ {{ periods.week.distance_miles }} | 🏔️ {{ periods.week.elevation_feet }}' | 🕓 {{ periods.week.duration }} | 🍺 {{ periods.week.beers }}",
  },
  {
    id: "month",
    label: "30-Day Summary",
    enabled: true,
    template:
      "📅 Past 30 days:\n🏃 {{ periods.month.gap }} | 🗺️ {{ periods.month.distance_miles }} | 🏔️ {{ periods.month.elevation_feet }}' | 🕓 {{ periods.month.duration }} | 🍺 {{ periods.month.beers }}",
  },
  {
    id: "year",
    label: "Year Summary",
    enabled: true,
    template:
      "🌍 This Year:\n🏃 {{ periods.year.gap }} | 🗺️ {{ periods.year.distance_miles }} | 🏔️ {{ periods.year.elevation_feet }}' | 🕓 {{ periods.year.duration }} | 🍺 {{ periods.year.beers }}",
  },
];

const FALLBACK_SNIPPETS = [
  {
    id: "if-block",
    category: "logic",
    label: "If Present",
    template: "{% if value %}\n{{ value }}\n{% endif %}",
    description: "Render only if value is present.",
  },
  {
    id: "for-loop",
    category: "logic",
    label: "For Loop",
    template: "{% for item in items %}\n- {{ item }}\n{% endfor %}",
    description: "Loop through a list.",
  },
  {
    id: "default-filter",
    category: "filters",
    label: "Default",
    template: "{{ value | default('N/A') }}",
    description: "Fallback value.",
  },
  {
    id: "round-filter",
    category: "filters",
    label: "Round",
    template: "{{ value | round(1) }}",
    description: "Round to one decimal.",
  },
];

const DRAFT_KEY = "auto_stat_description_editor_draft";
const THEME_KEY = "auto_stat_description_editor_theme";

const state = {
  templateActive: "",
  templateDefault: "",
  templateName: "Auto Stat Template",
  templateMeta: null,
  versions: [],
  fixtures: [],
  helperTransforms: [],
  schema: null,
  schemaSource: null,
  sections: SECTION_LIBRARY.map((x) => ({ ...x })),
  snippets: FALLBACK_SNIPPETS,
  autoPreview: true,
  autoPreviewTimer: null,
  previewRequestId: 0,
  editorTouched: false,
};

const elements = {
  topStatus: document.getElementById("topStatus"),
  templateEditor: document.getElementById("templateEditor"),
  previewText: document.getElementById("previewText"),
  previewMeta: document.getElementById("previewMeta"),
  validationPane: document.getElementById("validationPane"),
  schemaList: document.getElementById("schemaList"),
  schemaMeta: document.getElementById("schemaMeta"),
  catalogDiagnostics: document.getElementById("catalogDiagnostics"),
  schemaSearch: document.getElementById("schemaSearch"),
  schemaContextMode: document.getElementById("schemaContextMode"),
  schemaSourceFilter: document.getElementById("schemaSourceFilter"),
  schemaGroupFilter: document.getElementById("schemaGroupFilter"),
  schemaTypeFilter: document.getElementById("schemaTypeFilter"),
  schemaTagFilter: document.getElementById("schemaTagFilter"),
  schemaCuratedOnly: document.getElementById("schemaCuratedOnly"),
  previewContextMode: document.getElementById("previewContextMode"),
  previewFixtureName: document.getElementById("previewFixtureName"),
  templateNameInput: document.getElementById("templateNameInput"),
  templateAuthorInput: document.getElementById("templateAuthorInput"),
  simpleSections: document.getElementById("simpleSections"),
  snippetList: document.getElementById("snippetList"),
  templateMeta: document.getElementById("templateMeta"),
  versionList: document.getElementById("versionList"),
  autoPreviewToggle: document.getElementById("autoPreviewToggle"),
  themeToggle: document.getElementById("themeToggle"),
};

function setStatus(text, tone = "neutral") {
  elements.topStatus.textContent = text;
  elements.topStatus.dataset.tone = tone;
}

async function requestJSON(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch (error) {
    return {
      ok: false,
      status: 0,
      payload: { error: `Network error: ${String(error)}` },
    };
  }

  const payload = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, payload };
}

function decodeEscapedNewlines(text) {
  return String(text || "").replace(/\\n/g, "\n");
}

function getEditorText() {
  return elements.templateEditor.value;
}

function setEditorText(templateText) {
  elements.templateEditor.value = decodeEscapedNewlines(templateText || "");
}

function insertAtCursor(text) {
  const editor = elements.templateEditor;
  const start = editor.selectionStart || 0;
  const end = editor.selectionEnd || 0;
  const current = editor.value;
  editor.value = current.slice(0, start) + text + current.slice(end);

  const nextCursor = start + text.length;
  editor.focus();
  editor.setSelectionRange(nextCursor, nextCursor);
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
  if (result.context_source) {
    lines.push(`Context source: ${result.context_source}`);
  }

  pane.textContent = lines.join("\n");
}

function setSelectOptions(select, values, allLabel) {
  const previous = select.value || "all";
  select.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = allLabel;
  select.appendChild(allOption);
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  const valid = values.includes(previous);
  select.value = valid ? previous : "all";
}

function renderCatalogDiagnostics() {
  const schema = state.schema || {};
  const facets = schema.facets || {};
  const overlaps = Array.isArray(schema.overlaps) ? schema.overlaps : [];
  let curatedCount = 0;
  for (const group of schema.groups || []) {
    for (const field of group.fields || []) {
      if (field.curated) curatedCount += 1;
    }
  }
  const lines = [];
  lines.push(`Groups: ${(facets.groups || []).length} | Fields: ${schema.field_count || 0}`);
  lines.push(`Curated fields: ${curatedCount}`);
  lines.push(`Sources: ${(facets.sources || []).length} | Tags: ${(facets.tags || []).length}`);
  lines.push(`Metric overlaps: ${overlaps.length}`);
  if (overlaps.length > 0) {
    const sample = overlaps.slice(0, 3).map((item) => item.metric_key).join(", ");
    lines.push(`Overlap sample: ${sample}`);
  }
  elements.catalogDiagnostics.textContent = lines.join("\n");
}

function refreshSourceFilterOptions() {
  const schema = state.schema || {};
  const facets = schema.facets || {};
  setSelectOptions(
    elements.schemaSourceFilter,
    Array.isArray(facets.sources) ? facets.sources.slice() : [],
    "All Sources",
  );
  setSelectOptions(
    elements.schemaGroupFilter,
    Array.isArray(facets.groups) ? facets.groups.slice() : [],
    "All Groups",
  );
  setSelectOptions(
    elements.schemaTypeFilter,
    Array.isArray(facets.types) ? facets.types.slice() : [],
    "All Types",
  );
  setSelectOptions(
    elements.schemaTagFilter,
    Array.isArray(facets.tags) ? facets.tags.slice() : [],
    "All Tags",
  );
  renderCatalogDiagnostics();
}

function stringifySample(sample) {
  if (sample === undefined) return "undefined";
  if (sample === null) return "null";
  if (typeof sample === "string") return sample;
  try {
    return JSON.stringify(sample);
  } catch (_err) {
    return String(sample);
  }
}

function insertFieldWithTransform(fieldPath, transformTemplate) {
  const path = String(fieldPath || "").trim();
  if (!path) return;
  const template = String(transformTemplate || "{{ {path} }}");
  const snippet = template.replaceAll("{path}", path);
  insertAtCursor(snippet);
  setStatus(`Inserted ${path}`, "ok");
  queueAutoPreview();
}

function renderSchemaCatalog(filterText = "") {
  const schema = state.schema;
  elements.schemaList.innerHTML = "";

  if (!schema || !Array.isArray(schema.groups) || schema.groups.length === 0) {
    elements.schemaMeta.textContent = "No schema fields available.";
    return;
  }

  const q = filterText.trim().toLowerCase();
  const sourceFilter = elements.schemaSourceFilter.value || "all";
  const groupFilter = elements.schemaGroupFilter.value || "all";
  const typeFilter = elements.schemaTypeFilter.value || "all";
  const tagFilter = elements.schemaTagFilter.value || "all";
  const curatedOnly = Boolean(elements.schemaCuratedOnly.checked);
  let visibleFields = 0;

  for (const group of schema.groups) {
    if (groupFilter !== "all" && String(group.group) !== groupFilter) {
      continue;
    }

    const fields = (group.fields || []).filter((field) => {
      const fieldSource = String(field.source || group.source || "Unknown");
      const fieldType = String(field.type || "");
      const fieldTags = Array.isArray(field.tags) ? field.tags.map((tag) => String(tag)) : [];
      const fieldCurated = Boolean(field.curated);

      if (sourceFilter !== "all" && fieldSource !== sourceFilter) {
        return false;
      }
      if (typeFilter !== "all" && fieldType !== typeFilter) {
        return false;
      }
      if (tagFilter !== "all" && !fieldTags.includes(tagFilter)) {
        return false;
      }
      if (curatedOnly && !fieldCurated) {
        return false;
      }

      if (!q) return true;
      const alternatives = Array.isArray(field.alternatives)
        ? field.alternatives.map((alt) => String(alt))
        : [];
      return (
        String(field.path || "").toLowerCase().includes(q) ||
        String(field.label || "").toLowerCase().includes(q) ||
        String(field.description || "").toLowerCase().includes(q) ||
        String(field.type || "").toLowerCase().includes(q) ||
        fieldSource.toLowerCase().includes(q) ||
        String(field.source_note || "").toLowerCase().includes(q) ||
        String(field.metric_key || "").toLowerCase().includes(q) ||
        fieldTags.join(" ").toLowerCase().includes(q) ||
        alternatives.join(" ").toLowerCase().includes(q)
      );
    });

    if (fields.length === 0) continue;
    visibleFields += fields.length;

    const card = document.createElement("section");
    card.className = "catalog-group";

    const groupSource = group.source ? ` | ${group.source}` : "";
    const h = document.createElement("h3");
    h.textContent = `${group.group} (${fields.length})${groupSource}`;
    card.appendChild(h);

    for (const field of fields.sort((a, b) => String(a.path || "").localeCompare(String(b.path || "")))) {
      const row = document.createElement("div");
      row.className = "field";
      if (field.curated) {
        row.classList.add("field-curated");
      }

      const body = document.createElement("div");
      const label = document.createElement("div");
      label.className = "field-label";
      label.textContent = field.label || field.path;

      const key = document.createElement("div");
      key.className = "field-key";
      key.textContent = `{{ ${field.path} }}`;

      const type = document.createElement("div");
      type.className = "field-type";
      type.textContent = `${field.type} | sample: ${stringifySample(field.sample)}`;

      const source = document.createElement("div");
      source.className = "field-source";
      source.textContent = field.source_note
        ? `Source: ${field.source} (${field.source_note})`
        : `Source: ${field.source || "Unknown"}`;

      const desc = document.createElement("div");
      desc.className = "field-description";
      desc.textContent = field.description || "";

      const metric = document.createElement("div");
      metric.className = "field-type";
      metric.textContent = field.metric_key
        ? `Metric key: ${field.metric_key}`
        : "Metric key: none";

      const tags = Array.isArray(field.tags) ? field.tags : [];
      const tagsLine = document.createElement("div");
      tagsLine.className = "field-type";
      tagsLine.textContent = tags.length > 0 ? `Tags: ${tags.join(", ")}` : "Tags: none";

      const alternatives = Array.isArray(field.alternatives) ? field.alternatives : [];
      const alternativesLine = document.createElement("div");
      alternativesLine.className = "field-type";
      alternativesLine.textContent = alternatives.length > 0
        ? `Alternatives: ${alternatives.join(", ")}`
        : "Alternatives: none";

      body.appendChild(label);
      body.appendChild(key);
      if (desc.textContent) body.appendChild(desc);
      body.appendChild(type);
      body.appendChild(metric);
      body.appendChild(tagsLine);
      if (alternatives.length > 0) {
        body.appendChild(alternativesLine);
      }
      body.appendChild(source);

      const controls = document.createElement("div");
      controls.className = "field-actions";

      const insertBtn = document.createElement("button");
      insertBtn.className = "field-insert";
      insertBtn.textContent = "Insert";
      insertBtn.title = "Insert into advanced template";
      insertBtn.addEventListener("click", () => {
        insertFieldWithTransform(field.path, "{{ {path} }}");
      });

      controls.appendChild(insertBtn);

      if (Array.isArray(state.helperTransforms) && state.helperTransforms.length > 0) {
        const transformSelect = document.createElement("select");
        transformSelect.className = "field-transform";
        for (const transform of state.helperTransforms) {
          const option = document.createElement("option");
          option.value = String(transform.template || "{{ {path} }}");
          option.textContent = String(transform.label || transform.id || "Transform");
          transformSelect.appendChild(option);
        }
        const transformBtn = document.createElement("button");
        transformBtn.className = "field-insert";
        transformBtn.textContent = "Insert As";
        transformBtn.title = "Insert using selected transform";
        transformBtn.addEventListener("click", () => {
          insertFieldWithTransform(field.path, transformSelect.value);
        });
        controls.appendChild(transformSelect);
        controls.appendChild(transformBtn);
      }

      row.appendChild(body);
      row.appendChild(controls);
      row.addEventListener("dblclick", () => {
        insertFieldWithTransform(field.path, "{{ {path} }}");
      });

      card.appendChild(row);
    }

    elements.schemaList.appendChild(card);
  }

  const sourceText = state.schemaSource ? ` | context: ${state.schemaSource}` : "";
  elements.schemaMeta.textContent = `${visibleFields} fields shown${sourceText}`;
}

function renderSnippets() {
  elements.snippetList.innerHTML = "";

  for (const snippet of state.snippets) {
    const btn = document.createElement("button");
    btn.className = "snippet-btn";
    btn.type = "button";
    btn.title = `${snippet.category || "snippet"}: ${snippet.description || ""}`;
    btn.textContent = snippet.label;
    btn.addEventListener("click", () => {
      insertAtCursor(decodeEscapedNewlines(snippet.template || ""));
      setStatus(`Inserted snippet: ${snippet.label}`, "ok");
      queueAutoPreview();
    });
    elements.snippetList.appendChild(btn);
  }
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
    .map((section) => decodeEscapedNewlines(section.template))
    .filter(Boolean);

  if (chunks.length === 0) {
    return "{{ '' }}";
  }

  return chunks.join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function formatTemplateText(input) {
  return String(input || "")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
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

async function loadSchema(mode) {
  const query = new URLSearchParams({ context_mode: mode || "sample" });
  if ((mode || "sample") !== "latest") {
    query.set("fixture_name", elements.previewFixtureName.value || "default");
  }
  const res = await requestJSON(`/editor/catalog?${query.toString()}`);
  if (!res.ok) {
    setStatus("Failed to load data catalog", "error");
    return;
  }

  state.schema = res.payload.catalog || null;
  state.helperTransforms = Array.isArray(state.schema?.helper_transforms)
    ? state.schema.helper_transforms
    : [];
  state.schemaSource = res.payload.context_source || null;
  refreshSourceFilterOptions();
  renderSchemaCatalog(elements.schemaSearch.value || "");
}

function selectedFixtureName() {
  return (elements.previewFixtureName.value || "default").trim().toLowerCase();
}

function renderTemplateMeta(meta) {
  if (!meta) {
    elements.templateMeta.textContent = "No template metadata.";
    return;
  }
  const lines = [];
  lines.push(`Name: ${meta.name || "Auto Stat Template"}`);
  lines.push(`Version: ${meta.current_version || "none"}`);
  lines.push(`Updated: ${meta.updated_at_utc || "unknown"}`);
  lines.push(`By: ${meta.updated_by || "unknown"} | Source: ${meta.source || "unknown"}`);
  elements.templateMeta.textContent = lines.join("\n");
}

function renderVersionHistory() {
  elements.versionList.innerHTML = "";
  if (!Array.isArray(state.versions) || state.versions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "meta";
    empty.textContent = "No saved versions yet.";
    elements.versionList.appendChild(empty);
    return;
  }

  for (const version of state.versions) {
    const row = document.createElement("div");
    row.className = "field";

    const body = document.createElement("div");
    const key = document.createElement("div");
    key.className = "field-key";
    key.textContent = `${version.version_id || "unknown"} | ${version.name || "Template"}`;

    const type = document.createElement("div");
    type.className = "field-type";
    type.textContent = `${version.operation || "save"} | ${version.author || "unknown"} | ${version.created_at_utc || "unknown"}`;

    const source = document.createElement("div");
    source.className = "field-source";
    source.textContent = version.notes
      ? `Source: ${version.source || "unknown"} (${version.notes})`
      : `Source: ${version.source || "unknown"}`;

    body.appendChild(key);
    body.appendChild(type);
    body.appendChild(source);

    const controls = document.createElement("div");
    controls.className = "row-controls";

    const loadBtn = document.createElement("button");
    loadBtn.className = "field-insert";
    loadBtn.textContent = "Load";
    loadBtn.addEventListener("click", async () => {
      await loadTemplateVersion(String(version.version_id || ""));
    });

    const rollbackBtn = document.createElement("button");
    rollbackBtn.className = "field-insert";
    rollbackBtn.textContent = "Rollback";
    rollbackBtn.addEventListener("click", async () => {
      await rollbackTemplateVersion(String(version.version_id || ""));
    });

    controls.appendChild(loadBtn);
    controls.appendChild(rollbackBtn);

    row.appendChild(body);
    row.appendChild(controls);
    elements.versionList.appendChild(row);
  }
}

async function loadFixtures(fixturesPayload = null) {
  if (fixturesPayload && Array.isArray(fixturesPayload)) {
    state.fixtures = fixturesPayload;
  } else {
    const res = await requestJSON("/editor/fixtures");
    if (!res.ok || !Array.isArray(res.payload.fixtures)) {
      setStatus("Failed to load fixtures", "error");
      return;
    }
    state.fixtures = res.payload.fixtures;
  }
  const previous = selectedFixtureName();
  elements.previewFixtureName.innerHTML = "";
  for (const fixture of state.fixtures) {
    const option = document.createElement("option");
    option.value = fixture.name;
    option.textContent = fixture.label || fixture.name;
    option.title = fixture.description || fixture.name;
    elements.previewFixtureName.appendChild(option);
  }
  const names = state.fixtures.map((x) => String(x.name || ""));
  elements.previewFixtureName.value = names.includes(previous) ? previous : (names[0] || "default");
}

async function loadVersionHistory() {
  const res = await requestJSON("/editor/template/versions?limit=40");
  if (!res.ok) {
    setStatus("Failed to load template history", "error");
    return;
  }
  state.versions = Array.isArray(res.payload.versions) ? res.payload.versions : [];
  renderVersionHistory();
}

async function loadTemplateVersion(versionId) {
  if (!versionId) return;
  const res = await requestJSON(`/editor/template/version/${encodeURIComponent(versionId)}`);
  if (!res.ok) {
    setStatus("Failed to load version", "error");
    return;
  }
  const record = res.payload.version || {};
  setEditorText(record.template || "");
  switchTab("advanced");
  setStatus(`Loaded version ${versionId}`, "ok");
  queueAutoPreview();
}

async function rollbackTemplateVersion(versionId) {
  if (!versionId) return;
  const ok = window.confirm(`Rollback active template to ${versionId}?`);
  if (!ok) return;

  const res = await requestJSON("/editor/template/rollback", {
    method: "POST",
    body: JSON.stringify({
      version_id: versionId,
      author: elements.templateAuthorInput.value || "editor-user",
      source: "editor-rollback",
    }),
  });
  if (!res.ok) {
    setStatus("Rollback failed", "error");
    return;
  }
  await loadEditorBootstrap();
  setStatus(`Rolled back to ${versionId}`, "ok");
}

function saveDraft() {
  try {
    localStorage.setItem(DRAFT_KEY, getEditorText());
    setStatus("Draft saved locally", "ok");
  } catch (_err) {
    setStatus("Draft save failed", "error");
  }
}

function loadDraft() {
  try {
    const draft = localStorage.getItem(DRAFT_KEY);
    if (!draft) {
      setStatus("No local draft found", "error");
      return;
    }
    setEditorText(draft);
    setStatus("Loaded local draft", "ok");
    queueAutoPreview();
  } catch (_err) {
    setStatus("Draft load failed", "error");
  }
}

function applyTheme(theme) {
  const nextTheme = theme === "light" ? "light" : "dark";
  document.body.dataset.theme = nextTheme;
  elements.themeToggle.checked = nextTheme === "dark";
  try {
    localStorage.setItem(THEME_KEY, nextTheme);
  } catch (_err) {
    // Ignore localStorage failures.
  }
}

function loadThemePreference() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
  } catch (_err) {
    // Ignore localStorage failures.
  }
  return "dark";
}

async function loadEditorBootstrap() {
  setStatus("Loading editor data...");

  const schemaMode = elements.schemaContextMode.value || "sample";
  const fixtureName = selectedFixtureName();
  const [activeRes, defaultRes, schemaRes, snippetRes, fixtureRes, versionsRes] = await Promise.all([
    requestJSON("/editor/template"),
    requestJSON("/editor/template/default"),
    requestJSON(`/editor/catalog?context_mode=${encodeURIComponent(schemaMode)}&fixture_name=${encodeURIComponent(fixtureName)}`),
    requestJSON("/editor/snippets"),
    requestJSON("/editor/fixtures"),
    requestJSON("/editor/template/versions?limit=40"),
  ]);

  if (!activeRes.ok || !defaultRes.ok) {
    setStatus("Failed to load templates", "error");
    return;
  }

  state.templateActive = decodeEscapedNewlines(activeRes.payload.template || "");
  state.templateDefault = decodeEscapedNewlines(defaultRes.payload.template || "");
  state.templateMeta = activeRes.payload || null;
  state.templateName = String(activeRes.payload.name || "Auto Stat Template");

  setEditorText(state.templateActive);
  elements.templateNameInput.value = state.templateName;
  if (!elements.templateAuthorInput.value.trim()) {
    elements.templateAuthorInput.value = String(activeRes.payload.updated_by || "editor-user");
  }

  if (schemaRes.ok) {
    state.schema = schemaRes.payload.catalog || null;
    state.helperTransforms = Array.isArray(state.schema?.helper_transforms)
      ? state.schema.helper_transforms
      : [];
    state.schemaSource = schemaRes.payload.context_source || null;
  }

  if (snippetRes.ok && Array.isArray(snippetRes.payload.snippets)) {
    state.snippets = snippetRes.payload.snippets;
  }
  if (fixtureRes.ok && Array.isArray(fixtureRes.payload.fixtures)) {
    await loadFixtures(fixtureRes.payload.fixtures);
  }
  if (versionsRes.ok && Array.isArray(versionsRes.payload.versions)) {
    state.versions = versionsRes.payload.versions;
  }

  refreshSourceFilterOptions();
  renderSchemaCatalog("");
  renderSimpleSections();
  renderSnippets();
  renderTemplateMeta(state.templateMeta);
  renderVersionHistory();

  state.autoPreview = true;
  elements.autoPreviewToggle.checked = true;

  const isCustom = Boolean(activeRes.payload.is_custom);
  const sourceLabel = state.schemaSource ? ` | schema: ${state.schemaSource}` : "";
  setStatus((isCustom ? "Loaded custom template" : "Loaded default template") + sourceLabel, "ok");

  await previewTemplate({ force: true });
}

async function validateTemplate() {
  const template = getEditorText();
  const contextMode = elements.previewContextMode.value || "sample";
  const fixtureName = selectedFixtureName();
  const res = await requestJSON("/editor/validate", {
    method: "POST",
    body: JSON.stringify({ template, context_mode: contextMode, fixture_name: fixtureName }),
  });

  updateValidationPane(res.payload, res.ok);
  setStatus(res.ok ? "Validation passed" : "Validation failed", res.ok ? "ok" : "error");
}

async function previewTemplate(options = {}) {
  const { force = false } = options;
  const template = getEditorText();
  const contextMode = elements.previewContextMode.value || "sample";
  const fixtureName = selectedFixtureName();

  const requestId = ++state.previewRequestId;
  const res = await requestJSON("/editor/preview", {
    method: "POST",
    body: JSON.stringify({ template, context_mode: contextMode, fixture_name: fixtureName }),
  });

  if (requestId !== state.previewRequestId) {
    return;
  }

  if (!res.ok) {
    elements.previewMeta.textContent = res.payload.error || "Preview failed";
    if (force) {
      elements.previewText.textContent = "";
    }
    setStatus("Preview failed", "error");
    return;
  }

  elements.previewText.textContent = res.payload.preview || "";
  const source = res.payload.context_source || "sample";
  elements.previewMeta.textContent = `Rendered length: ${res.payload.length} chars | context: ${source}`;
  setStatus("Preview updated", "ok");
}

function queueAutoPreview() {
  if (!state.autoPreview) {
    return;
  }
  if (state.autoPreviewTimer) {
    clearTimeout(state.autoPreviewTimer);
  }
  state.autoPreviewTimer = setTimeout(() => {
    previewTemplate({ force: false });
  }, 450);
}

async function saveTemplate() {
  const template = getEditorText();
  const author = (elements.templateAuthorInput.value || "editor-user").trim();
  const name = (elements.templateNameInput.value || "Auto Stat Template").trim();
  const res = await requestJSON("/editor/template", {
    method: "PUT",
    body: JSON.stringify({
      template,
      author: author || "editor-user",
      source: "editor-ui",
      name: name || "Auto Stat Template",
    }),
  });

  if (!res.ok) {
    updateValidationPane(res.payload, false);
    setStatus("Save failed", "error");
    return;
  }

  updateValidationPane(res.payload, true);
  state.templateActive = template;
  state.templateMeta = res.payload.active || state.templateMeta;
  renderTemplateMeta(state.templateMeta);
  await loadVersionHistory();
  setStatus("Template saved + published", "ok");
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
    queueAutoPreview();
  });

  document.getElementById("btnLoadDefault").addEventListener("click", () => {
    setEditorText(state.templateDefault);
    setStatus("Loaded default template", "ok");
    queueAutoPreview();
  });

  document.getElementById("btnSaveDraft").addEventListener("click", saveDraft);
  document.getElementById("btnLoadDraft").addEventListener("click", loadDraft);

  document.getElementById("btnFormatTemplate").addEventListener("click", () => {
    setEditorText(formatTemplateText(getEditorText()));
    setStatus("Formatted: normalized whitespace and blank lines", "ok");
    queueAutoPreview();
  });

  document.getElementById("btnValidate").addEventListener("click", validateTemplate);
  document.getElementById("btnPreview").addEventListener("click", () => previewTemplate({ force: true }));
  document.getElementById("btnSave").addEventListener("click", saveTemplate);
  document.getElementById("btnCopyPreview").addEventListener("click", copyPreview);
  document.getElementById("btnRefreshHistory").addEventListener("click", async () => {
    await loadVersionHistory();
    setStatus("Template history refreshed", "ok");
  });

  document.getElementById("btnSimpleApply").addEventListener("click", () => {
    setEditorText(buildTemplateFromSimple());
    switchTab("advanced");
    setStatus("Builder output applied to advanced editor", "ok");
    queueAutoPreview();
  });

  document.getElementById("btnSimpleReset").addEventListener("click", () => {
    state.sections = SECTION_LIBRARY.map((x) => ({ ...x }));
    renderSimpleSections();
    setStatus("Builder reset", "ok");
  });

  elements.schemaSearch.addEventListener("input", (event) => {
    renderSchemaCatalog(event.target.value || "");
  });

  elements.schemaSourceFilter.addEventListener("change", () => {
    renderSchemaCatalog(elements.schemaSearch.value || "");
  });
  elements.schemaGroupFilter.addEventListener("change", () => {
    renderSchemaCatalog(elements.schemaSearch.value || "");
  });
  elements.schemaTypeFilter.addEventListener("change", () => {
    renderSchemaCatalog(elements.schemaSearch.value || "");
  });
  elements.schemaTagFilter.addEventListener("change", () => {
    renderSchemaCatalog(elements.schemaSearch.value || "");
  });
  elements.schemaCuratedOnly.addEventListener("change", () => {
    renderSchemaCatalog(elements.schemaSearch.value || "");
  });

  elements.schemaContextMode.addEventListener("change", async () => {
    await loadSchema(elements.schemaContextMode.value || "sample");
    setStatus("Catalog context changed", "ok");
  });

  elements.previewContextMode.addEventListener("change", () => {
    queueAutoPreview();
  });

  elements.previewFixtureName.addEventListener("change", async () => {
    await loadSchema(elements.schemaContextMode.value || "sample");
    queueAutoPreview();
  });

  elements.autoPreviewToggle.addEventListener("change", () => {
    state.autoPreview = elements.autoPreviewToggle.checked;
    setStatus(state.autoPreview ? "Auto-preview enabled" : "Auto-preview disabled", "ok");
    if (state.autoPreview) {
      queueAutoPreview();
    }
  });

  elements.themeToggle.addEventListener("change", () => {
    applyTheme(elements.themeToggle.checked ? "dark" : "light");
    setStatus(elements.themeToggle.checked ? "Dark mode enabled" : "Light mode enabled", "ok");
  });

  elements.templateEditor.addEventListener("input", () => {
    state.editorTouched = true;
    queueAutoPreview();
  });

  elements.templateEditor.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      previewTemplate({ force: true });
    }
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  bindUI();
  applyTheme(loadThemePreference());
  updateValidationPane(null, true);
  await loadEditorBootstrap();
});
