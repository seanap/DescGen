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
const TOUR_SEEN_KEY = "auto_stat_description_editor_tour_seen_v1";

const TOUR_STEPS = [
  {
    title: "Pick Preview Context",
    body:
      "Use Preview Context to choose SAFE modes (sample/fixture) or LIVE modes (latest). SAFE is best for editing because it avoids live payload dependency.",
  },
  {
    title: "Explore Available Data",
    body:
      "Use the Available Data catalog to search fields by source/group/tag. Click Insert or Insert As to add variables and filters directly into your template.",
  },
  {
    title: "Use Starter Templates",
    body:
      "Choose a starter preset to instantly bootstrap a layout. Preview Starter lets you test without replacing your current editor content.",
  },
  {
    title: "Publish With Confidence",
    body:
      "Save + Publish always opens a required confirmation modal with validation summary and line diff against the active template before publish.",
  },
];

const state = {
  templateActive: "",
  templateDefault: "",
  templateName: "Auto Stat Template",
  templateMeta: null,
  repositoryTemplates: [],
  repositorySelectedId: "",
  repositoryLoadedTemplateId: "",
  versions: [],
  fixtures: [],
  starterTemplates: [],
  helperTransforms: [],
  schema: null,
  schemaSource: null,
  sections: SECTION_LIBRARY.map((x) => ({ ...x })),
  snippets: FALLBACK_SNIPPETS,
  autoPreview: true,
  autoPreviewTimer: null,
  previewRequestId: 0,
  editorTouched: false,
  publishModalValidationOk: false,
  tourStep: 0,
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
  contextSafetyBanner: document.getElementById("contextSafetyBanner"),
  repositoryTemplateSelect: document.getElementById("repositoryTemplateSelect"),
  repositoryTemplateMeta: document.getElementById("repositoryTemplateMeta"),
  repoTemplateNameInput: document.getElementById("repoTemplateNameInput"),
  repoTemplateAuthorInput: document.getElementById("repoTemplateAuthorInput"),
  starterTemplateSelect: document.getElementById("starterTemplateSelect"),
  starterTemplateMeta: document.getElementById("starterTemplateMeta"),
  importTemplateFile: document.getElementById("importTemplateFile"),
  simpleSections: document.getElementById("simpleSections"),
  snippetList: document.getElementById("snippetList"),
  templateMeta: document.getElementById("templateMeta"),
  versionList: document.getElementById("versionList"),
  autoPreviewToggle: document.getElementById("autoPreviewToggle"),
  themeToggle: document.getElementById("themeToggle"),
  publishModal: document.getElementById("publishModal"),
  publishCloseBtn: document.getElementById("publishCloseBtn"),
  publishCancelBtn: document.getElementById("publishCancelBtn"),
  publishConfirmBtn: document.getElementById("publishConfirmBtn"),
  publishValidationSummary: document.getElementById("publishValidationSummary"),
  publishDiffSummary: document.getElementById("publishDiffSummary"),
  publishDiffView: document.getElementById("publishDiffView"),
  publishModeBanner: document.getElementById("publishModeBanner"),
  publishChecklistReviewed: document.getElementById("publishChecklistReviewed"),
  publishChecklistReplace: document.getElementById("publishChecklistReplace"),
  tourModal: document.getElementById("tourModal"),
  tourStepTitle: document.getElementById("tourStepTitle"),
  tourStepBody: document.getElementById("tourStepBody"),
  tourStepCounter: document.getElementById("tourStepCounter"),
  btnTour: document.getElementById("btnTour"),
  btnTourSkip: document.getElementById("btnTourSkip"),
  btnTourPrev: document.getElementById("btnTourPrev"),
  btnTourNext: document.getElementById("btnTourNext"),
  btnTourDone: document.getElementById("btnTourDone"),
};

function setStatus(text, tone = "neutral") {
  elements.topStatus.textContent = text;
  elements.topStatus.dataset.tone = tone;
}

function contextModeProfile(mode) {
  const value = String(mode || "sample");
  if (value === "sample") {
    return {
      level: "safe",
      label: "SAFE",
      text: "SAFE mode: sample context only. No live payload dependency and no upstream API calls.",
    };
  }
  if (value === "fixture") {
    const fixture = selectedFixtureName();
    return {
      level: "safe",
      label: "SAFE",
      text: `SAFE mode: fixture '${fixture}'. No live payload dependency and no upstream API calls.`,
    };
  }
  if (value === "latest_or_sample") {
    return {
      level: "live",
      label: "LIVE",
      text: "LIVE mode: latest captured payload with sample fallback. Editor preview does not call upstream services.",
    };
  }
  return {
    level: "live",
    label: "LIVE",
    text: "LIVE mode: latest captured payload. Editor preview does not call upstream services.",
  };
}

function renderContextSafetyBanner() {
  if (!elements.contextSafetyBanner) return;
  const profile = contextModeProfile(elements.previewContextMode.value || "sample");
  elements.contextSafetyBanner.classList.remove("safe", "live");
  elements.contextSafetyBanner.classList.add(profile.level);
  elements.contextSafetyBanner.textContent = profile.text;
}

function collectValidationHints(validation) {
  const hints = [];
  const errors = Array.isArray(validation.errors) ? validation.errors : [];
  const warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
  const undeclared = Array.isArray(validation.undeclared_variables) ? validation.undeclared_variables : [];

  if (undeclared.length > 0) {
    hints.push("Guard optional fields with `| default('N/A')` or `{% if value is defined %}`.");
  }
  if (errors.some((line) => String(line).toLowerCase().includes("unsupported jinja control tag"))) {
    hints.push("Only basic Jinja logic is supported. Avoid include/import/extends/macro tags.");
  }
  if (errors.some((line) => String(line).toLowerCase().includes("too large"))) {
    hints.push("Trim duplicate sections or long literal blocks to reduce template size.");
  }
  if (warnings.some((line) => String(line).toLowerCase().includes("raw payload"))) {
    hints.push("Prefer curated catalog fields over `raw.*` fields for long-term stability.");
  }

  const groups = Array.isArray(state.schema?.facets?.groups) ? state.schema.facets.groups : [];
  if (groups.length > 0 && undeclared.length > 0) {
    const unknownTop = undeclared.filter((name) => !groups.includes(name));
    if (unknownTop.length > 0) {
      hints.push(`Known top-level keys: ${groups.join(", ")}.`);
    }
  }
  return hints;
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
  const validation = result.validation || {};
  const errors = Array.isArray(validation.errors) ? validation.errors : [];
  const warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
  const undeclared = Array.isArray(validation.undeclared_variables) ? validation.undeclared_variables : [];

  if (ok) {
    pane.classList.add("ok");
    lines.push("Template is valid.");
  } else {
    pane.classList.add("error");
    lines.push("Template has validation issues.");
  }
  lines.push(`Counts: ${errors.length} error(s), ${warnings.length} warning(s), ${undeclared.length} undeclared.`);

  if (errors.length > 0) {
    lines.push("Errors:");
    for (const error of errors) lines.push(`- ${error}`);
  }
  if (warnings.length > 0) {
    lines.push("Warnings:");
    for (const warning of warnings) lines.push(`- ${warning}`);
  }
  if (undeclared.length > 0) {
    lines.push(`Undeclared variables: ${undeclared.join(", ")}`);
  } else {
    lines.push("Undeclared variables: none");
  }

  const hints = collectValidationHints(validation);
  if (hints.length > 0) {
    lines.push("Hints:");
    for (const hint of hints) lines.push(`- ${hint}`);
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
    const contextMode = elements.schemaContextMode.value || "sample";
    elements.schemaMeta.textContent =
      `No schema fields available. Try context mode '${contextMode}' or run one worker cycle to populate latest payload context.`;
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
  if (visibleFields === 0) {
    const activeFilters = [];
    const sourceValue = elements.schemaSourceFilter.value || "all";
    const groupValue = elements.schemaGroupFilter.value || "all";
    const typeValue = elements.schemaTypeFilter.value || "all";
    const tagValue = elements.schemaTagFilter.value || "all";
    if (sourceValue !== "all") activeFilters.push(`source=${sourceValue}`);
    if (groupValue !== "all") activeFilters.push(`group=${groupValue}`);
    if (typeValue !== "all") activeFilters.push(`type=${typeValue}`);
    if (tagValue !== "all") activeFilters.push(`tag=${tagValue}`);
    if (elements.schemaCuratedOnly.checked) activeFilters.push("curated_only=true");
    const filterTextLabel = activeFilters.length > 0 ? ` with filters (${activeFilters.join(", ")})` : "";
    elements.schemaMeta.textContent = `No fields matched${filterTextLabel}${sourceText}.`;
    return;
  }
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

function splitLines(value) {
  return String(value || "").replace(/\r\n/g, "\n").split("\n");
}

function computeLineDiff(beforeText, afterText) {
  const before = splitLines(beforeText);
  const after = splitLines(afterText);
  const n = before.length;
  const m = after.length;
  const lcs = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));

  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      if (before[i] === after[j]) {
        lcs[i][j] = lcs[i + 1][j + 1] + 1;
      } else {
        lcs[i][j] = Math.max(lcs[i + 1][j], lcs[i][j + 1]);
      }
    }
  }

  const rows = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (before[i] === after[j]) {
      rows.push({ type: "context", text: before[i] });
      i += 1;
      j += 1;
      continue;
    }
    if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      rows.push({ type: "removed", text: before[i] });
      i += 1;
    } else {
      rows.push({ type: "added", text: after[j] });
      j += 1;
    }
  }
  while (i < n) {
    rows.push({ type: "removed", text: before[i] });
    i += 1;
  }
  while (j < m) {
    rows.push({ type: "added", text: after[j] });
    j += 1;
  }
  return rows;
}

function summarizeLineDiff(rows) {
  let added = 0;
  let removed = 0;
  let unchanged = 0;
  let changed = 0;
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    if (row.type === "added") added += 1;
    if (row.type === "removed") removed += 1;
    if (row.type === "context") unchanged += 1;
    const next = rows[i + 1];
    if (row.type === "removed" && next && next.type === "added") {
      changed += 1;
    }
    if (row.type === "added" && next && next.type === "removed") {
      changed += 1;
    }
  }
  return { added, removed, unchanged, changed };
}

function renderDiffRows(rows, maxRows = 260) {
  const clipped = rows.slice(0, maxRows);
  const lines = clipped.map((row) => {
    if (row.type === "added") return `+ ${row.text}`;
    if (row.type === "removed") return `- ${row.text}`;
    return `  ${row.text}`;
  });
  if (rows.length > maxRows) {
    lines.push(`... truncated (${rows.length - maxRows} additional line(s))`);
  }
  return lines.join("\n");
}

function updatePublishConfirmEnabled() {
  const checkedA = Boolean(elements.publishChecklistReviewed?.checked);
  const checkedB = Boolean(elements.publishChecklistReplace?.checked);
  const canPublish = state.publishModalValidationOk && checkedA && checkedB;
  if (elements.publishConfirmBtn) {
    elements.publishConfirmBtn.disabled = !canPublish;
  }
}

function setPublishValidationSummary(result, ok) {
  if (!elements.publishValidationSummary) return;
  elements.publishValidationSummary.classList.remove("ok", "error");
  elements.publishValidationSummary.classList.add(ok ? "ok" : "error");

  const validation = result.validation || {};
  const errors = Array.isArray(validation.errors) ? validation.errors : [];
  const warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
  const undeclared = Array.isArray(validation.undeclared_variables) ? validation.undeclared_variables : [];
  const lines = [];
  lines.push(ok ? "Validation: pass" : "Validation: fail");
  if (result && result.error) {
    lines.push(`Error: ${result.error}`);
  }
  lines.push(`Errors: ${errors.length} | Warnings: ${warnings.length} | Undeclared: ${undeclared.length}`);
  if (errors.length > 0) {
    lines.push("Top errors:");
    for (const line of errors.slice(0, 3)) lines.push(`- ${line}`);
  }
  const hints = collectValidationHints(validation);
  if (hints.length > 0) {
    lines.push("Hints:");
    for (const hint of hints.slice(0, 3)) lines.push(`- ${hint}`);
  }
  if (result.context_source) {
    lines.push(`Context: ${result.context_source}`);
  }
  elements.publishValidationSummary.textContent = lines.join("\n");
}

function setPublishModeBanner() {
  if (!elements.publishModeBanner) return;
  const profile = contextModeProfile(elements.previewContextMode.value || "sample");
  elements.publishModeBanner.classList.remove("safe", "live");
  elements.publishModeBanner.classList.add(profile.level);
  elements.publishModeBanner.textContent = `${profile.label}: ${profile.text}`;
}

function closePublishModal() {
  if (!elements.publishModal) return;
  elements.publishModal.classList.remove("open");
  elements.publishModal.setAttribute("aria-hidden", "true");
  state.publishModalValidationOk = false;
  updatePublishConfirmEnabled();
}

async function openPublishModal() {
  if (!elements.publishModal) {
    setStatus("Publish modal unavailable", "error");
    return;
  }
  const candidate = getEditorText();
  const active = state.templateActive || "";
  const diffRows = computeLineDiff(active, candidate);
  const diffSummary = summarizeLineDiff(diffRows);

  if (elements.publishDiffSummary) {
    elements.publishDiffSummary.textContent =
      `Diff: +${diffSummary.added} / -${diffSummary.removed} / unchanged ${diffSummary.unchanged} / changed~ ${diffSummary.changed}`;
  }
  if (elements.publishDiffView) {
    elements.publishDiffView.textContent = renderDiffRows(diffRows);
  }

  if (elements.publishChecklistReviewed) elements.publishChecklistReviewed.checked = false;
  if (elements.publishChecklistReplace) elements.publishChecklistReplace.checked = false;
  state.publishModalValidationOk = false;
  updatePublishConfirmEnabled();
  setPublishModeBanner();
  if (elements.publishValidationSummary) {
    elements.publishValidationSummary.classList.remove("ok", "error");
    elements.publishValidationSummary.textContent = "Running validation checks...";
  }

  elements.publishModal.classList.add("open");
  elements.publishModal.setAttribute("aria-hidden", "false");

  const contextMode = elements.previewContextMode.value || "sample";
  const fixtureName = selectedFixtureName();
  const validationRes = await requestJSON("/editor/validate", {
    method: "POST",
    body: JSON.stringify({
      template: candidate,
      context_mode: contextMode,
      fixture_name: fixtureName,
    }),
  });

  setPublishValidationSummary(validationRes.payload || {}, validationRes.ok);
  state.publishModalValidationOk = Boolean(validationRes.ok);
  updatePublishConfirmEnabled();

  if (!validationRes.ok) {
    updateValidationPane(validationRes.payload || {}, false);
    setStatus("Publish blocked: validation failed", "error");
  } else {
    setStatus("Publish checklist ready", "ok");
  }
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

function repositorySelectedId() {
  return String(elements.repositoryTemplateSelect?.value || "").trim();
}

function findRepositoryTemplateSummary(templateId) {
  if (!templateId) return null;
  return state.repositoryTemplates.find((item) => String(item.template_id || "") === String(templateId)) || null;
}

function setRepositoryFormValues(options = {}) {
  const { name = "", author = "" } = options;
  if (elements.repoTemplateNameInput) {
    elements.repoTemplateNameInput.value = String(name || "").trim();
  }
  if (elements.repoTemplateAuthorInput) {
    elements.repoTemplateAuthorInput.value = String(author || "").trim();
  }
}

function renderRepositoryMeta(record = null) {
  if (!elements.repositoryTemplateMeta) return;
  if (!record) {
    elements.repositoryTemplateMeta.textContent = "No repository template selected.";
    return;
  }
  const lines = [];
  lines.push(`${record.name || "Untitled Template"} (${record.template_id || "unknown"})`);
  lines.push(`Author: ${record.author || "unknown"} | Source: ${record.source || "unknown"}`);
  if (record.description) {
    lines.push(record.description);
  }
  if (record.updated_at_utc) {
    lines.push(`Updated: ${record.updated_at_utc}`);
  }
  if (record.created_at_utc) {
    lines.push(`Created: ${record.created_at_utc}`);
  }
  if (typeof record.template_chars === "number") {
    lines.push(`Template length: ${record.template_chars} chars`);
  } else if (typeof record.template === "string") {
    lines.push(`Template length: ${record.template.length} chars`);
  }
  if (record.is_builtin) {
    lines.push("Built-in template: Save As to create an editable copy.");
  }
  elements.repositoryTemplateMeta.textContent = lines.join("\n");
}

function renderRepositoryOptions() {
  if (!elements.repositoryTemplateSelect) return;
  const select = elements.repositoryTemplateSelect;
  const previous = state.repositorySelectedId || String(select.value || "");
  select.innerHTML = "";

  if (!Array.isArray(state.repositoryTemplates) || state.repositoryTemplates.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No templates in repository";
    select.appendChild(option);
    state.repositorySelectedId = "";
    renderRepositoryMeta(null);
    return;
  }

  for (const item of state.repositoryTemplates) {
    const option = document.createElement("option");
    option.value = String(item.template_id || "");
    const locked = item.is_builtin ? " [built-in]" : "";
    option.textContent = `${item.name || item.template_id}${locked}`;
    option.title = item.description || item.name || item.template_id;
    select.appendChild(option);
  }

  const validPrevious = state.repositoryTemplates.some(
    (item) => String(item.template_id || "") === previous
  );
  select.value = validPrevious ? previous : String(state.repositoryTemplates[0].template_id || "");
  state.repositorySelectedId = String(select.value || "");
  const selected = findRepositoryTemplateSummary(state.repositorySelectedId);
  renderRepositoryMeta(selected);
  if (selected) {
    setRepositoryFormValues({ name: selected.name, author: selected.author });
  }
}

async function loadRepositoryTemplates(options = {}) {
  const { preferTemplateId = "" } = options;
  const res = await requestJSON("/editor/repository/templates");
  if (!res.ok || !Array.isArray(res.payload.templates)) {
    state.repositoryTemplates = [];
    renderRepositoryOptions();
    setStatus("Failed to load template repository", "error");
    return;
  }
  state.repositoryTemplates = res.payload.templates;
  if (preferTemplateId) {
    state.repositorySelectedId = String(preferTemplateId);
  }
  renderRepositoryOptions();
}

async function loadRepositoryTemplateIntoEditor(templateId, options = {}) {
  const { promptIfOverwrite = true } = options;
  const targetId = String(templateId || repositorySelectedId()).trim();
  if (!targetId) {
    setStatus("Select a repository template first", "error");
    return;
  }
  const res = await requestJSON(`/editor/repository/template/${encodeURIComponent(targetId)}`);
  if (!res.ok) {
    setStatus("Failed to load repository template", "error");
    return;
  }
  const record = res.payload.template_record || null;
  if (!record || typeof record.template !== "string") {
    setStatus("Repository template payload missing template text", "error");
    return;
  }
  if (promptIfOverwrite) {
    const current = getEditorText().trim();
    const incoming = String(record.template || "").trim();
    if (current && current !== incoming) {
      const confirmed = window.confirm(
        `Replace current editor content with repository template "${record.name || targetId}"?`
      );
      if (!confirmed) return;
    }
  }
  state.repositorySelectedId = String(record.template_id || targetId);
  state.repositoryLoadedTemplateId = state.repositorySelectedId;
  if (elements.repositoryTemplateSelect) {
    elements.repositoryTemplateSelect.value = state.repositorySelectedId;
  }
  setEditorText(record.template || "");
  setRepositoryFormValues({ name: record.name, author: record.author });
  renderRepositoryMeta(record);
  switchTab("advanced");
  setStatus(`Loaded repository template: ${record.name || targetId}`, "ok");
  queueAutoPreview();
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
      author: elements.repoTemplateAuthorInput?.value || "editor-user",
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

function selectedStarterTemplate() {
  const selectedId = String(elements.starterTemplateSelect?.value || "").trim();
  if (!selectedId) return null;
  return state.starterTemplates.find((item) => String(item.id) === selectedId) || null;
}

function renderStarterTemplateMeta() {
  if (!elements.starterTemplateMeta) return;
  const selected = selectedStarterTemplate();
  if (!selected) {
    elements.starterTemplateMeta.textContent = "No starter selected.";
    return;
  }
  const lines = [];
  lines.push(`${selected.label || selected.id}`);
  if (selected.description) lines.push(selected.description);
  const templateText = String(selected.template || "");
  lines.push(`Template length: ${templateText.length} chars`);
  elements.starterTemplateMeta.textContent = lines.join("\n");
}

function renderStarterTemplateOptions() {
  if (!elements.starterTemplateSelect) return;
  const select = elements.starterTemplateSelect;
  const previous = String(select.value || "");
  select.innerHTML = "";

  if (!Array.isArray(state.starterTemplates) || state.starterTemplates.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No starters available";
    select.appendChild(option);
    select.value = "";
    renderStarterTemplateMeta();
    return;
  }

  for (const starter of state.starterTemplates) {
    const option = document.createElement("option");
    option.value = String(starter.id || "");
    option.textContent = String(starter.label || starter.id || "Starter");
    option.title = String(starter.description || starter.label || "");
    select.appendChild(option);
  }

  const validPrevious = state.starterTemplates.some((item) => String(item.id || "") === previous);
  select.value = validPrevious ? previous : String(state.starterTemplates[0].id || "");
  renderStarterTemplateMeta();
}

async function previewSelectedStarterTemplate() {
  const selected = selectedStarterTemplate();
  if (!selected) {
    setStatus("No starter template selected", "error");
    return;
  }
  const contextMode = elements.previewContextMode.value || "sample";
  const fixtureName = selectedFixtureName();
  const res = await requestJSON("/editor/preview", {
    method: "POST",
    body: JSON.stringify({
      template: String(selected.template || ""),
      context_mode: contextMode,
      fixture_name: fixtureName,
    }),
  });
  if (!res.ok) {
    elements.previewMeta.textContent = res.payload.error || "Starter preview failed";
    elements.previewText.textContent = "";
    setStatus("Starter preview failed", "error");
    return;
  }
  elements.previewText.textContent = res.payload.preview || "";
  elements.previewMeta.textContent = `Starter preview | ${selected.label} | context: ${res.payload.context_source || "sample"}`;
  setStatus(`Starter preview rendered: ${selected.label}`, "ok");
}

function applySelectedStarterTemplate() {
  const selected = selectedStarterTemplate();
  if (!selected) {
    setStatus("No starter template selected", "error");
    return;
  }
  const incoming = decodeEscapedNewlines(String(selected.template || ""));
  const current = getEditorText();
  if (current.trim() && current.trim() !== incoming.trim()) {
    const confirmed = window.confirm(`Replace current editor content with starter template "${selected.label}"?`);
    if (!confirmed) return;
  }
  setEditorText(incoming);
  switchTab("advanced");
  setStatus(`Starter applied: ${selected.label}`, "ok");
  queueAutoPreview();
}

async function loadStarterTemplates(startersPayload = null) {
  if (startersPayload && Array.isArray(startersPayload)) {
    state.starterTemplates = startersPayload;
  } else {
    const res = await requestJSON("/editor/starter-templates");
    if (!res.ok || !Array.isArray(res.payload.starter_templates)) {
      state.starterTemplates = [];
      renderStarterTemplateOptions();
      setStatus("Failed to load starter templates", "error");
      return;
    }
    state.starterTemplates = res.payload.starter_templates;
  }
  renderStarterTemplateOptions();
}

function markTourSeen() {
  try {
    localStorage.setItem(TOUR_SEEN_KEY, "1");
  } catch (_err) {
    // Ignore localStorage failures.
  }
}

function hasSeenTour() {
  try {
    return localStorage.getItem(TOUR_SEEN_KEY) === "1";
  } catch (_err) {
    return false;
  }
}

function renderTourStep() {
  const stepCount = TOUR_STEPS.length;
  if (stepCount === 0) return;
  const index = Math.max(0, Math.min(stepCount - 1, state.tourStep));
  state.tourStep = index;
  const step = TOUR_STEPS[index];

  if (elements.tourStepTitle) elements.tourStepTitle.textContent = step.title;
  if (elements.tourStepBody) elements.tourStepBody.textContent = step.body;
  if (elements.tourStepCounter) elements.tourStepCounter.textContent = `Step ${index + 1} / ${stepCount}`;
  if (elements.btnTourPrev) elements.btnTourPrev.disabled = index === 0;
  if (elements.btnTourNext) elements.btnTourNext.hidden = index >= stepCount - 1;
  if (elements.btnTourDone) elements.btnTourDone.hidden = index < stepCount - 1;
}

function openTour(startIndex = 0) {
  if (!elements.tourModal) return;
  state.tourStep = Math.max(0, Math.min(TOUR_STEPS.length - 1, startIndex));
  renderTourStep();
  elements.tourModal.classList.add("open");
  elements.tourModal.setAttribute("aria-hidden", "false");
}

function closeTour(options = {}) {
  const { markSeen = true } = options;
  if (!elements.tourModal) return;
  elements.tourModal.classList.remove("open");
  elements.tourModal.setAttribute("aria-hidden", "true");
  if (markSeen) markTourSeen();
}

function maybeOpenTourOnFirstRun() {
  if (hasSeenTour()) return;
  openTour(0);
}

function downloadTextFile(filename, text) {
  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function buildExportFilename(name) {
  const baseRaw = String(name || "auto-stat-template").trim().toLowerCase();
  const base = baseRaw
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "") || "auto-stat-template";
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `${base}-${stamp}.json`;
}

async function exportTemplateBundle() {
  const selectedId = repositorySelectedId();
  if (!selectedId) {
    setStatus("Select a repository template to export", "error");
    return;
  }
  const res = await requestJSON(`/editor/repository/template/${encodeURIComponent(selectedId)}/export?include_versions=false`);
  if (!res.ok) {
    setStatus("Template export failed", "error");
    return;
  }
  const payload = res.payload || {};
  const filename = buildExportFilename(payload.name || state.templateName || "auto-stat-template");
  downloadTextFile(filename, `${JSON.stringify(payload, null, 2)}\n`);
  setStatus(`Template exported: ${filename}`, "ok");
}

function triggerImportTemplateFile() {
  if (!elements.importTemplateFile) {
    setStatus("Import control not available", "error");
    return;
  }
  elements.importTemplateFile.value = "";
  elements.importTemplateFile.click();
}

async function saveRepositoryTemplate() {
  const selectedId = repositorySelectedId();
  if (!selectedId) {
    setStatus("Select a repository template first", "error");
    return;
  }
  const summary = findRepositoryTemplateSummary(selectedId);
  if (summary && summary.is_builtin) {
    setStatus("Built-in templates are read-only. Use Save As.", "error");
    return;
  }
  if (
    state.repositoryLoadedTemplateId &&
    selectedId !== state.repositoryLoadedTemplateId
  ) {
    const confirmed = window.confirm(
      "You are about to overwrite a repository template that is not the one currently loaded. Continue?"
    );
    if (!confirmed) return;
  }

  const template = getEditorText();
  const name = (elements.repoTemplateNameInput?.value || "Untitled Template").trim() || "Untitled Template";
  const author = (elements.repoTemplateAuthorInput?.value || "editor-user").trim() || "editor-user";
  const res = await requestJSON(`/editor/repository/template/${encodeURIComponent(selectedId)}`, {
    method: "PUT",
    body: JSON.stringify({
      template,
      name,
      author,
      source: "editor-repository-save",
      context_mode: elements.previewContextMode.value || "sample",
      fixture_name: selectedFixtureName(),
    }),
  });
  if (!res.ok) {
    updateValidationPane(res.payload, false);
    setStatus("Repository save failed", "error");
    return;
  }
  await loadRepositoryTemplates({ preferTemplateId: selectedId });
  const loaded = await requestJSON(`/editor/repository/template/${encodeURIComponent(selectedId)}`);
  if (loaded.ok) {
    renderRepositoryMeta(loaded.payload.template_record || null);
  }
  state.repositoryLoadedTemplateId = selectedId;
  setStatus("Repository template saved", "ok");
}

async function saveRepositoryTemplateAs() {
  const template = getEditorText();
  const name = (elements.repoTemplateNameInput?.value || "Untitled Template").trim() || "Untitled Template";
  const author = (elements.repoTemplateAuthorInput?.value || "editor-user").trim() || "editor-user";
  const res = await requestJSON("/editor/repository/save_as", {
    method: "POST",
    body: JSON.stringify({
      template,
      name,
      author,
      source: "editor-repository-save-as",
      context_mode: elements.previewContextMode.value || "sample",
      fixture_name: selectedFixtureName(),
    }),
  });
  if (!res.ok) {
    updateValidationPane(res.payload, false);
    setStatus("Repository Save As failed", "error");
    return;
  }
  const created = res.payload.template_record || {};
  const createdId = String(created.template_id || "");
  await loadRepositoryTemplates({ preferTemplateId: createdId });
  state.repositoryLoadedTemplateId = createdId;
  renderRepositoryMeta(created);
  setStatus(`Repository template saved as: ${created.name || createdId}`, "ok");
}

async function duplicateRepositoryTemplate() {
  const selectedId = repositorySelectedId();
  if (!selectedId) {
    setStatus("Select a repository template first", "error");
    return;
  }
  const summary = findRepositoryTemplateSummary(selectedId);
  const defaultName = `${summary?.name || "Template"} Copy`;
  const name = window.prompt("Duplicate template as:", defaultName);
  if (name === null) return;
  const author = (elements.repoTemplateAuthorInput?.value || "editor-user").trim() || "editor-user";
  const res = await requestJSON(`/editor/repository/template/${encodeURIComponent(selectedId)}/duplicate`, {
    method: "POST",
    body: JSON.stringify({
      name: name.trim() || defaultName,
      author,
      source: "editor-repository-duplicate",
    }),
  });
  if (!res.ok) {
    setStatus("Template duplicate failed", "error");
    return;
  }
  const duplicated = res.payload.template_record || {};
  const duplicatedId = String(duplicated.template_id || "");
  await loadRepositoryTemplates({ preferTemplateId: duplicatedId });
  state.repositoryLoadedTemplateId = duplicatedId;
  renderRepositoryMeta(duplicated);
  setStatus(`Template duplicated: ${duplicated.name || duplicatedId}`, "ok");
}

async function importTemplateBundleFromFile(file) {
  if (!file) return;
  let parsed;
  try {
    const text = await file.text();
    parsed = JSON.parse(text);
  } catch (_err) {
    setStatus("Import failed: invalid JSON file", "error");
    return;
  }
  if (!parsed || typeof parsed !== "object") {
    setStatus("Import failed: expected a JSON object bundle", "error");
    return;
  }

  const author = (elements.repoTemplateAuthorInput?.value || "editor-user").trim() || "editor-user";
  const name = (elements.repoTemplateNameInput?.value || "").trim();
  const res = await requestJSON("/editor/repository/import", {
    method: "POST",
    body: JSON.stringify({
      bundle: parsed,
      author,
      name: name || undefined,
      source: "editor-repository-import",
      context_mode: elements.previewContextMode.value || "sample",
      fixture_name: selectedFixtureName(),
    }),
  });
  if (!res.ok) {
    updateValidationPane(res.payload, false);
    setStatus("Template import failed", "error");
    return;
  }

  const record = res.payload.template_record || {};
  const importedId = String(record.template_id || "");
  await loadRepositoryTemplates({ preferTemplateId: importedId });
  state.repositoryLoadedTemplateId = importedId;
  if (typeof record.template === "string") {
    setEditorText(record.template);
  }
  setRepositoryFormValues({ name: record.name, author: record.author });
  renderRepositoryMeta(record);
  setStatus("Template imported into repository", "ok");
  queueAutoPreview();
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
  const [activeRes, defaultRes, schemaRes, snippetRes, starterRes, fixtureRes, versionsRes, repositoryRes] = await Promise.all([
    requestJSON("/editor/template"),
    requestJSON("/editor/template/default"),
    requestJSON(`/editor/catalog?context_mode=${encodeURIComponent(schemaMode)}&fixture_name=${encodeURIComponent(fixtureName)}`),
    requestJSON("/editor/snippets"),
    requestJSON("/editor/starter-templates"),
    requestJSON("/editor/fixtures"),
    requestJSON("/editor/template/versions?limit=40"),
    requestJSON("/editor/repository/templates"),
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
  const activeAuthor = String(activeRes.payload.updated_by || "editor-user");
  setRepositoryFormValues({ name: state.templateName, author: activeAuthor });

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
  if (starterRes.ok && Array.isArray(starterRes.payload.starter_templates)) {
    await loadStarterTemplates(starterRes.payload.starter_templates);
  } else {
    await loadStarterTemplates([]);
  }
  if (fixtureRes.ok && Array.isArray(fixtureRes.payload.fixtures)) {
    await loadFixtures(fixtureRes.payload.fixtures);
  }
  if (versionsRes.ok && Array.isArray(versionsRes.payload.versions)) {
    state.versions = versionsRes.payload.versions;
  }
  if (repositoryRes.ok && Array.isArray(repositoryRes.payload.templates)) {
    state.repositoryTemplates = repositoryRes.payload.templates;
    const byName = state.repositoryTemplates.find(
      (item) => String(item.name || "") === state.templateName
    );
    if (byName) {
      state.repositorySelectedId = String(byName.template_id || "");
      setRepositoryFormValues({
        name: byName.name || state.templateName,
        author: byName.author || activeAuthor,
      });
      state.repositoryLoadedTemplateId = state.repositorySelectedId;
    }
    renderRepositoryOptions();
    if (!byName) {
      setRepositoryFormValues({ name: state.templateName, author: activeAuthor });
    }
  } else {
    state.repositoryTemplates = [];
    renderRepositoryOptions();
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
  renderContextSafetyBanner();

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
    const mode = elements.previewContextMode.value || "sample";
    const errorText = res.payload.error || "Preview failed";
    elements.previewMeta.textContent = `Preview failed (${mode}): ${errorText}`;
    if (mode === "latest") {
      elements.previewText.textContent = "No latest context available yet. Try Sample/Fixture mode or run one worker cycle.";
    } else {
      elements.previewText.textContent = "Validation/render issue. Check the Validation panel for details and hints.";
    }
    if (force) {
      // keep informative error text in preview pane on forced preview failures
    }
    setStatus("Preview failed", "error");
    return;
  }

  const rendered = String(res.payload.preview || "");
  if (rendered.trim()) {
    elements.previewText.textContent = rendered;
  } else {
    elements.previewText.textContent = "Template rendered an empty output for this context.";
  }
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

async function saveTemplate(options = {}) {
  const { source = "editor-ui" } = options;
  const template = getEditorText();
  const author = (elements.repoTemplateAuthorInput?.value || "editor-user").trim();
  const name = (elements.repoTemplateNameInput?.value || "Auto Stat Template").trim();
  const res = await requestJSON("/editor/template", {
    method: "PUT",
    body: JSON.stringify({
      template,
      author: author || "editor-user",
      source,
      name: name || "Auto Stat Template",
    }),
  });

  if (!res.ok) {
    updateValidationPane(res.payload, false);
    setStatus("Save failed", "error");
    return false;
  }

  updateValidationPane(res.payload, true);
  state.templateActive = template;
  state.templateMeta = res.payload.active || state.templateMeta;
  renderTemplateMeta(state.templateMeta);
  await loadVersionHistory();
  setStatus("Template saved + published", "ok");
  return true;
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
  if (elements.btnTour) {
    elements.btnTour.addEventListener("click", () => {
      openTour(0);
    });
  }

  document.getElementById("btnFormatTemplate").addEventListener("click", () => {
    setEditorText(formatTemplateText(getEditorText()));
    setStatus("Formatted: normalized whitespace and blank lines", "ok");
    queueAutoPreview();
  });

  document.getElementById("btnValidate").addEventListener("click", validateTemplate);
  document.getElementById("btnPreview").addEventListener("click", () => previewTemplate({ force: true }));
  document.getElementById("btnSave").addEventListener("click", openPublishModal);
  if (elements.starterTemplateSelect) {
    elements.starterTemplateSelect.addEventListener("change", renderStarterTemplateMeta);
  }
  const starterPreviewBtn = document.getElementById("btnStarterPreview");
  if (starterPreviewBtn) {
    starterPreviewBtn.addEventListener("click", previewSelectedStarterTemplate);
  }
  const starterApplyBtn = document.getElementById("btnStarterApply");
  if (starterApplyBtn) {
    starterApplyBtn.addEventListener("click", applySelectedStarterTemplate);
  }
  const repoLoadBtn = document.getElementById("btnRepoLoad");
  if (repoLoadBtn) {
    repoLoadBtn.addEventListener("click", () => loadRepositoryTemplateIntoEditor(repositorySelectedId(), { promptIfOverwrite: true }));
  }
  const repoSaveBtn = document.getElementById("btnRepoSave");
  if (repoSaveBtn) {
    repoSaveBtn.addEventListener("click", saveRepositoryTemplate);
  }
  const repoSaveAsBtn = document.getElementById("btnRepoSaveAs");
  if (repoSaveAsBtn) {
    repoSaveAsBtn.addEventListener("click", saveRepositoryTemplateAs);
  }
  const repoDuplicateBtn = document.getElementById("btnRepoDuplicate");
  if (repoDuplicateBtn) {
    repoDuplicateBtn.addEventListener("click", duplicateRepositoryTemplate);
  }
  const repoImportBtn = document.getElementById("btnRepoImport");
  if (repoImportBtn) {
    repoImportBtn.addEventListener("click", triggerImportTemplateFile);
  }
  const repoExportBtn = document.getElementById("btnRepoExport");
  if (repoExportBtn) {
    repoExportBtn.addEventListener("click", exportTemplateBundle);
  }
  document.getElementById("btnCopyPreview").addEventListener("click", copyPreview);
  document.getElementById("btnRefreshHistory").addEventListener("click", async () => {
    await loadVersionHistory();
    setStatus("Template history refreshed", "ok");
  });

  if (elements.repositoryTemplateSelect) {
    elements.repositoryTemplateSelect.addEventListener("change", () => {
      state.repositorySelectedId = repositorySelectedId();
      const summary = findRepositoryTemplateSummary(state.repositorySelectedId);
      renderRepositoryMeta(summary);
      if (summary) {
        setRepositoryFormValues({ name: summary.name, author: summary.author });
      }
    });
  }

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
    renderContextSafetyBanner();
    queueAutoPreview();
  });

  elements.previewFixtureName.addEventListener("change", async () => {
    renderContextSafetyBanner();
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

  if (elements.publishChecklistReviewed) {
    elements.publishChecklistReviewed.addEventListener("change", updatePublishConfirmEnabled);
  }
  if (elements.publishChecklistReplace) {
    elements.publishChecklistReplace.addEventListener("change", updatePublishConfirmEnabled);
  }
  if (elements.publishCancelBtn) {
    elements.publishCancelBtn.addEventListener("click", closePublishModal);
  }
  if (elements.publishCloseBtn) {
    elements.publishCloseBtn.addEventListener("click", closePublishModal);
  }
  if (elements.publishConfirmBtn) {
    elements.publishConfirmBtn.addEventListener("click", async () => {
      if (!state.publishModalValidationOk) {
        setStatus("Publish blocked: validation failed", "error");
        return;
      }
      elements.publishConfirmBtn.disabled = true;
      const ok = await saveTemplate({ source: "editor-ui-publish-modal" });
      if (ok) {
        closePublishModal();
      } else {
        updatePublishConfirmEnabled();
      }
    });
  }
  if (elements.publishModal) {
    elements.publishModal.addEventListener("click", (event) => {
      if (event.target === elements.publishModal) {
        closePublishModal();
      }
    });
  }
  if (elements.btnTourNext) {
    elements.btnTourNext.addEventListener("click", () => {
      state.tourStep = Math.min(TOUR_STEPS.length - 1, state.tourStep + 1);
      renderTourStep();
    });
  }
  if (elements.btnTourPrev) {
    elements.btnTourPrev.addEventListener("click", () => {
      state.tourStep = Math.max(0, state.tourStep - 1);
      renderTourStep();
    });
  }
  if (elements.btnTourDone) {
    elements.btnTourDone.addEventListener("click", () => closeTour({ markSeen: true }));
  }
  if (elements.btnTourSkip) {
    elements.btnTourSkip.addEventListener("click", () => closeTour({ markSeen: true }));
  }
  if (elements.tourModal) {
    elements.tourModal.addEventListener("click", (event) => {
      if (event.target === elements.tourModal) {
        closeTour({ markSeen: true });
      }
    });
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.publishModal?.classList.contains("open")) {
      closePublishModal();
      return;
    }
    if (event.key === "Escape" && elements.tourModal?.classList.contains("open")) {
      closeTour({ markSeen: true });
    }
  });

  if (elements.importTemplateFile) {
    elements.importTemplateFile.addEventListener("change", async () => {
      const file = elements.importTemplateFile.files && elements.importTemplateFile.files[0];
      await importTemplateBundleFromFile(file || null);
    });
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  bindUI();
  applyTheme(loadThemePreference());
  updateValidationPane(null, true);
  renderContextSafetyBanner();
  await loadEditorBootstrap();
  maybeOpenTourOnFirstRun();
});
