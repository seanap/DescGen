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
      "🚄 🏋️ {{ intervals.fitness }} | 💦 {{ intervals.fatigue }} | 🎯 {{ intervals.load }} | 📈 {{ intervals.ramp_display }} | 🗿 {{ intervals.form_percent_display }} - {{ intervals.form_class }} {{ intervals.form_class_emoji }}",
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
const CATALOG_FAVORITES_KEY = "auto_stat_description_editor_catalog_favorites_v1";
const CATALOG_RECENTS_KEY = "auto_stat_description_editor_catalog_recents_v1";

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
    title: "Use Snippet Palette",
    body:
      "Use snippet inserts and field tokens to build templates quickly without leaving the editor.",
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
  profiles: [],
  workingProfileId: "default",
  repositoryTemplates: [],
  repositorySelectedId: "",
  repositoryLoadedTemplateId: "",
  versions: [],
  fixtures: [],
  helperTransforms: [],
  schema: null,
  schemaSource: null,
  schemaSearchTimer: null,
  schemaSortKey: "group",
  schemaSortDir: "asc",
  catalogScope: "all",
  catalogRows: [],
  sections: SECTION_LIBRARY.map((x) => ({ ...x })),
  snippets: FALLBACK_SNIPPETS,
  autoPreview: true,
  autoPreviewTimer: null,
  previewRequestId: 0,
  previewCharLimit: 2200,
  previewDiffEnabled: false,
  activePreviewCacheKey: "",
  activePreviewTemplate: "",
  activePreviewRendered: "",
  lastValidationOk: null,
  editorTouched: false,
  selectedCatalogPath: "",
  publishModalValidationOk: false,
  tourStep: 0,
  catalogFavorites: new Set(),
  catalogRecents: [],
  commandPaletteItems: [],
  commandPaletteActiveIndex: 0,
};

const elements = {
  leftDrawer: document.getElementById("leftDrawer"),
  profileWorkspaceSection: document.getElementById("profileWorkspaceSection"),
  profileWorkspaceMeta: document.getElementById("profileWorkspaceMeta"),
  profileList: document.getElementById("profileList"),
  drawerBackdrop: document.getElementById("drawerBackdrop"),
  btnDrawerToggle: document.getElementById("btnDrawerToggle"),
  btnProfileDrawerToggle: document.getElementById("btnProfileDrawerToggle"),
  btnDrawerClose: document.getElementById("btnDrawerClose"),
  btnSettingsToggle: document.getElementById("btnSettingsToggle"),
  btnSettingsClose: document.getElementById("btnSettingsClose"),
  settingsPanel: document.getElementById("settingsPanel"),
  topStatus: document.getElementById("topStatus"),
  contextModeValue: document.getElementById("contextModeValue"),
  contextFixtureValue: document.getElementById("contextFixtureValue"),
  contextSchemaValue: document.getElementById("contextSchemaValue"),
  contextSaveValue: document.getElementById("contextSaveValue"),
  contextPublishValue: document.getElementById("contextPublishValue"),
  templateEditor: document.getElementById("templateEditor"),
  previewText: document.getElementById("previewText"),
  previewMeta: document.getElementById("previewMeta"),
  previewCharLimit: document.getElementById("previewCharLimit"),
  previewCharMeterFill: document.getElementById("previewCharMeterFill"),
  previewCharCount: document.getElementById("previewCharCount"),
  previewDiffToggle: document.getElementById("previewDiffToggle"),
  previewDiffMeta: document.getElementById("previewDiffMeta"),
  previewDiffText: document.getElementById("previewDiffText"),
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
  schemaStabilityFilter: document.getElementById("schemaStabilityFilter"),
  schemaCostTierFilter: document.getElementById("schemaCostTierFilter"),
  schemaFreshnessFilter: document.getElementById("schemaFreshnessFilter"),
  advancedFiltersWrap: document.getElementById("advancedFiltersWrap"),
  btnToggleAdvancedFilters: document.getElementById("btnToggleAdvancedFilters"),
  catalogScopePills: document.getElementById("catalogScopePills"),
  catalogQuickPicks: document.getElementById("catalogQuickPicks"),
  schemaKeyboardHint: document.getElementById("schemaKeyboardHint"),
  schemaInspector: document.getElementById("schemaInspector"),
  previewContextMode: document.getElementById("previewContextMode"),
  previewFixtureName: document.getElementById("previewFixtureName"),
  contextSafetyBanner: document.getElementById("contextSafetyBanner"),
  repositoryTemplateSelect: document.getElementById("repositoryTemplateSelect"),
  repositoryTemplateMeta: document.getElementById("repositoryTemplateMeta"),
  repoTemplateNameInput: document.getElementById("repoTemplateNameInput"),
  repoTemplateAuthorInput: document.getElementById("repoTemplateAuthorInput"),
  importTemplateFile: document.getElementById("importTemplateFile"),
  simpleSections: document.getElementById("simpleSections"),
  snippetList: document.getElementById("snippetList"),
  currentTemplateDisplay: document.getElementById("currentTemplateDisplay"),
  currentProfileDisplay: document.getElementById("currentProfileDisplay"),
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
  versionDiffModal: document.getElementById("versionDiffModal"),
  versionDiffCloseBtn: document.getElementById("versionDiffCloseBtn"),
  versionDiffMeta: document.getElementById("versionDiffMeta"),
  versionDiffView: document.getElementById("versionDiffView"),
  commandPaletteModal: document.getElementById("commandPaletteModal"),
  commandPaletteCloseBtn: document.getElementById("commandPaletteCloseBtn"),
  commandPaletteSearch: document.getElementById("commandPaletteSearch"),
  commandPaletteMeta: document.getElementById("commandPaletteMeta"),
  commandPaletteList: document.getElementById("commandPaletteList"),
  tourModal: document.getElementById("tourModal"),
  tourStepTitle: document.getElementById("tourStepTitle"),
  tourStepBody: document.getElementById("tourStepBody"),
  tourStepCounter: document.getElementById("tourStepCounter"),
  btnTour: document.getElementById("btnTour"),
  btnPreview: document.getElementById("btnPreview"),
  btnSave: document.getElementById("btnSave"),
  btnTourSkip: document.getElementById("btnTourSkip"),
  btnTourPrev: document.getElementById("btnTourPrev"),
  btnTourNext: document.getElementById("btnTourNext"),
  btnTourDone: document.getElementById("btnTourDone"),
};

function setStatus(text, tone = "neutral") {
  elements.topStatus.textContent = text;
  elements.topStatus.dataset.tone = tone;
}

function updateContextChips() {
  const previewMode = String(elements.previewContextMode?.value || "sample");
  const schemaMode = String(elements.schemaContextMode?.value || "sample");
  const fixture = selectedFixtureName();
  const schemaSource = state.schemaSource ? ` (${state.schemaSource})` : "";

  if (elements.contextModeValue) {
    elements.contextModeValue.textContent = previewMode;
  }
  if (elements.contextFixtureValue) {
    elements.contextFixtureValue.textContent = fixture;
  }
  if (elements.contextSchemaValue) {
    elements.contextSchemaValue.textContent = `${schemaMode}${schemaSource}`;
  }
  if (elements.contextSaveValue) {
    const dirty = state.editorTouched ? "Dirty" : "Saved";
    elements.contextSaveValue.textContent = dirty;
  }
  if (elements.contextPublishValue) {
    let publish = "Not checked";
    if (state.lastValidationOk === true) publish = "Ready";
    if (state.lastValidationOk === false) publish = "Blocked";
    elements.contextPublishValue.textContent = publish;
  }
}

function updateCurrentTemplateDisplay(name = "") {
  if (!elements.currentTemplateDisplay) return;
  const explicit = String(name || "").trim();
  if (explicit) {
    elements.currentTemplateDisplay.textContent = explicit;
    return;
  }
  const fromInput = String(elements.repoTemplateNameInput?.value || "").trim();
  if (fromInput) {
    elements.currentTemplateDisplay.textContent = fromInput;
    return;
  }
  elements.currentTemplateDisplay.textContent = String(state.templateName || "Auto Stat Template");
}

function currentProfileId() {
  return String(state.workingProfileId || "default").trim() || "default";
}

function currentProfileLabel() {
  const profileId = currentProfileId();
  const found = Array.isArray(state.profiles)
    ? state.profiles.find((item) => String(item.profile_id || "") === profileId)
    : null;
  if (found && String(found.label || "").trim()) return String(found.label);
  return profileId.charAt(0).toUpperCase() + profileId.slice(1);
}

function updateCurrentProfileDisplay() {
  if (!elements.currentProfileDisplay) return;
  elements.currentProfileDisplay.textContent = currentProfileLabel();
}

async function loadProfiles() {
  const res = await requestJSON("/editor/profiles");
  if (!res.ok) {
    setStatus("Failed to load profile workspace", "error");
    return false;
  }
  state.profiles = Array.isArray(res.payload.profiles) ? res.payload.profiles : [];
  state.workingProfileId = String(res.payload.working_profile_id || "default");
  renderProfileWorkspace();
  updateCurrentProfileDisplay();
  return true;
}

function renderProfileWorkspace() {
  if (!elements.profileList) return;
  elements.profileList.innerHTML = "";
  const profiles = Array.isArray(state.profiles) ? [...state.profiles] : [];
  profiles.sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0));
  if (elements.profileWorkspaceMeta) {
    elements.profileWorkspaceMeta.textContent = `Working profile: ${currentProfileLabel()} (${currentProfileId()})`;
  }
  if (profiles.length === 0) {
    const empty = document.createElement("div");
    empty.className = "meta";
    empty.textContent = "No profiles available.";
    elements.profileList.appendChild(empty);
    return;
  }

  for (const profile of profiles) {
    const profileId = String(profile.profile_id || "");
    const row = document.createElement("div");
    row.className = "field";

    const body = document.createElement("div");
    const key = document.createElement("div");
    key.className = "field-key";
    key.textContent = `${profile.label || profileId} (${profileId})`;

    const type = document.createElement("div");
    type.className = "field-type";
    type.textContent = `Priority ${profile.priority ?? 0} | ${profile.enabled ? "Enabled" : "Disabled"}${profile.locked ? " | Locked" : ""}`;

    const source = document.createElement("div");
    source.className = "field-source";
    source.textContent = String(profile.criteria?.description || "");

    body.appendChild(key);
    body.appendChild(type);
    body.appendChild(source);

    const controls = document.createElement("div");
    controls.className = "row-controls";

    const enabledLabel = document.createElement("label");
    enabledLabel.className = "toggle-inline";
    const enabledInput = document.createElement("input");
    enabledInput.type = "checkbox";
    enabledInput.checked = Boolean(profile.enabled);
    enabledInput.disabled = Boolean(profile.locked);
    enabledInput.addEventListener("change", async () => {
      const previousWorking = currentProfileId();
      const res = await requestJSON(`/editor/profiles/${encodeURIComponent(profileId)}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: Boolean(enabledInput.checked) }),
      });
      if (!res.ok) {
        setStatus(res.payload?.error || "Profile update failed", "error");
        await loadProfiles();
        return;
      }
      setStatus(`Profile ${profile.label || profileId} updated`, "ok");
      await loadProfiles();
      if (currentProfileId() !== previousWorking) {
        await loadEditorBootstrap();
      }
    });
    enabledLabel.appendChild(enabledInput);
    enabledLabel.append(" Enabled");

    const workingBtn = document.createElement("button");
    workingBtn.className = "field-insert";
    workingBtn.textContent = profileId === currentProfileId() ? "Working" : "Set Working";
    workingBtn.disabled = profileId === currentProfileId() || !Boolean(profile.enabled);
    workingBtn.addEventListener("click", async () => {
      if (state.editorTouched) {
        const ok = window.confirm(
          "Switch working profile and replace editor content with that profile template?"
        );
        if (!ok) return;
      }
      const setRes = await requestJSON("/editor/profiles/working", {
        method: "POST",
        body: JSON.stringify({ profile_id: profileId }),
      });
      if (!setRes.ok) {
        setStatus(setRes.payload?.error || "Failed to switch working profile", "error");
        return;
      }
      await loadProfiles();
      await loadEditorBootstrap();
      setStatus(`Working profile set: ${profile.label || profileId}`, "ok");
    });

    controls.appendChild(enabledLabel);
    controls.appendChild(workingBtn);

    row.appendChild(body);
    row.appendChild(controls);
    elements.profileList.appendChild(row);
  }
}

function setButtonTone(button, tone) {
  if (!button) return;
  button.classList.remove("btn-primary", "btn-secondary", "btn-ghost");
  if (tone === "primary") {
    button.classList.add("btn-primary");
    return;
  }
  if (tone === "secondary") {
    button.classList.add("btn-secondary");
    return;
  }
  button.classList.add("btn-ghost");
}

function updateActionEmphasis() {
  const saveButton = elements.btnSave;
  const previewButton = elements.btnPreview;
  if (!saveButton || !previewButton) return;

  if (state.editorTouched) {
    setButtonTone(saveButton, "primary");
    setButtonTone(previewButton, "secondary");
    return;
  }
  if (!state.autoPreview) {
    setButtonTone(previewButton, "primary");
    setButtonTone(saveButton, "secondary");
    return;
  }
  setButtonTone(saveButton, "secondary");
  setButtonTone(previewButton, "ghost");
}

function closeDrawer() {
  if (!elements.leftDrawer || !elements.drawerBackdrop) return;
  elements.leftDrawer.classList.remove("open");
  elements.leftDrawer.setAttribute("aria-hidden", "true");
  elements.drawerBackdrop.classList.remove("open");
  elements.drawerBackdrop.setAttribute("aria-hidden", "true");
}

function openDrawer() {
  if (!elements.leftDrawer || !elements.drawerBackdrop) return;
  elements.leftDrawer.classList.add("open");
  elements.leftDrawer.setAttribute("aria-hidden", "false");
  elements.drawerBackdrop.classList.add("open");
  elements.drawerBackdrop.setAttribute("aria-hidden", "false");
}

function openProfileWorkspace() {
  openDrawer();
  loadProfiles();
  if (elements.profileWorkspaceSection) {
    elements.profileWorkspaceSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function toggleDrawer() {
  if (!elements.leftDrawer) return;
  const open = elements.leftDrawer.classList.contains("open");
  if (open) {
    closeDrawer();
  } else {
    openDrawer();
  }
}

function closeSettingsPanel() {
  if (!elements.settingsPanel) return;
  elements.settingsPanel.classList.remove("open");
  elements.settingsPanel.setAttribute("aria-hidden", "true");
}

function openSettingsPanel() {
  if (!elements.settingsPanel) return;
  elements.settingsPanel.classList.add("open");
  elements.settingsPanel.setAttribute("aria-hidden", "false");
}

function toggleSettingsPanel() {
  if (!elements.settingsPanel) return;
  const open = elements.settingsPanel.classList.contains("open");
  if (open) {
    closeSettingsPanel();
  } else {
    openSettingsPanel();
  }
}

function setEditorDirty(isDirty) {
  state.editorTouched = Boolean(isDirty);
  updateContextChips();
  updateActionEmphasis();
}

function currentPreviewCharLimit() {
  const raw = Number.parseInt(String(elements.previewCharLimit?.value || state.previewCharLimit), 10);
  const next = Number.isFinite(raw) ? Math.min(20000, Math.max(100, raw)) : 2200;
  state.previewCharLimit = next;
  if (elements.previewCharLimit) {
    elements.previewCharLimit.value = String(next);
  }
  return next;
}

function updatePreviewCharMeter() {
  const renderedLength = String(elements.previewText?.textContent || "").length;
  const limit = currentPreviewCharLimit();
  const ratio = limit > 0 ? Math.min(1, renderedLength / limit) : 0;

  if (elements.previewCharMeterFill) {
    elements.previewCharMeterFill.style.width = `${Math.round(ratio * 100)}%`;
    elements.previewCharMeterFill.dataset.over = renderedLength > limit ? "1" : "0";
  }
  if (elements.previewCharCount) {
    const status = renderedLength > limit ? " (over limit)" : "";
    elements.previewCharCount.dataset.over = renderedLength > limit ? "1" : "0";
    elements.previewCharCount.textContent = `${renderedLength} / ${limit} chars${status}`;
  }
}

function currentPreviewContextKey() {
  const mode = String(elements.previewContextMode?.value || "sample");
  const fixture = selectedFixtureName();
  return `${currentProfileId()}|${mode}|${fixture}`;
}

function clearActivePreviewCache() {
  state.activePreviewCacheKey = "";
  state.activePreviewTemplate = "";
  state.activePreviewRendered = "";
}

async function ensureActivePreviewBaseline() {
  const key = currentPreviewContextKey();
  if (
    state.activePreviewCacheKey === key &&
    state.activePreviewTemplate === state.templateActive
  ) {
    return { ok: true, preview: state.activePreviewRendered };
  }

  const contextMode = elements.previewContextMode.value || "sample";
  const fixtureName = selectedFixtureName();
  const res = await requestJSON("/editor/preview", {
    method: "POST",
    body: JSON.stringify({
      template: state.templateActive || "",
      context_mode: contextMode,
      fixture_name: fixtureName,
      profile_id: currentProfileId(),
    }),
  });
  if (!res.ok) {
    return { ok: false, error: res.payload?.error || "Baseline preview failed" };
  }
  state.activePreviewCacheKey = key;
  state.activePreviewTemplate = state.templateActive;
  state.activePreviewRendered = String(res.payload.preview || "");
  return { ok: true, preview: state.activePreviewRendered };
}

async function updatePreviewDiff(currentRendered = "") {
  if (!elements.previewDiffToggle || !elements.previewDiffMeta || !elements.previewDiffText) return;
  if (!elements.previewDiffToggle.checked) {
    elements.previewDiffMeta.textContent = "Diff disabled.";
    elements.previewDiffText.classList.add("is-hidden");
    elements.previewDiffText.textContent = "";
    return;
  }

  const baseline = await ensureActivePreviewBaseline();
  if (!baseline.ok) {
    elements.previewDiffMeta.textContent = `Diff unavailable: ${baseline.error}`;
    elements.previewDiffText.classList.add("is-hidden");
    elements.previewDiffText.textContent = "";
    return;
  }

  const diffRows = computeLineDiff(String(baseline.preview || ""), String(currentRendered || ""));
  const summary = summarizeLineDiff(diffRows);
  elements.previewDiffMeta.textContent =
    `Diff vs active output: +${summary.added} / -${summary.removed} / unchanged ${summary.unchanged} / changed~ ${summary.changed}`;
  elements.previewDiffText.textContent = renderDiffRows(diffRows, 180);
  elements.previewDiffText.classList.remove("is-hidden");
}

function loadCatalogPreferences() {
  try {
    const favoriteRaw = localStorage.getItem(CATALOG_FAVORITES_KEY);
    const recentRaw = localStorage.getItem(CATALOG_RECENTS_KEY);
    const favorites = JSON.parse(favoriteRaw || "[]");
    const recents = JSON.parse(recentRaw || "[]");
    if (Array.isArray(favorites)) {
      state.catalogFavorites = new Set(
        favorites
          .map((item) => String(item || "").trim())
          .filter(Boolean),
      );
    }
    if (Array.isArray(recents)) {
      state.catalogRecents = recents
        .map((item) => String(item || "").trim())
        .filter(Boolean)
        .slice(0, 15);
    }
  } catch (_err) {
    state.catalogFavorites = new Set();
    state.catalogRecents = [];
  }
}

function saveCatalogFavorites() {
  try {
    localStorage.setItem(
      CATALOG_FAVORITES_KEY,
      JSON.stringify(Array.from(state.catalogFavorites.values()).slice(0, 300)),
    );
  } catch (_err) {
    // Ignore localStorage failures.
  }
}

function saveCatalogRecents() {
  try {
    localStorage.setItem(CATALOG_RECENTS_KEY, JSON.stringify(state.catalogRecents.slice(0, 15)));
  } catch (_err) {
    // Ignore localStorage failures.
  }
}

function isFavoriteField(path) {
  const key = String(path || "").trim();
  if (!key) return false;
  return state.catalogFavorites.has(key);
}

function toggleFavoriteField(path) {
  const key = String(path || "").trim();
  if (!key) return;
  if (state.catalogFavorites.has(key)) {
    state.catalogFavorites.delete(key);
    setStatus(`Removed favorite: ${key}`, "ok");
  } else {
    state.catalogFavorites.add(key);
    setStatus(`Added favorite: ${key}`, "ok");
  }
  saveCatalogFavorites();
  renderCatalogQuickPicks();
  renderSchemaCatalog(elements.schemaSearch.value || "");
}

function noteRecentField(path) {
  const key = String(path || "").trim();
  if (!key) return;
  state.catalogRecents = [key, ...state.catalogRecents.filter((item) => item !== key)].slice(0, 15);
  saveCatalogRecents();
  renderCatalogQuickPicks();
}

function renderCatalogQuickPicks() {
  if (!elements.catalogQuickPicks) return;
  const favorites = Array.from(state.catalogFavorites.values()).slice(0, 8);
  const recents = state.catalogRecents.slice(0, 8);
  const favoritesText = favorites.length > 0
    ? `Favorites (${state.catalogFavorites.size}): ${favorites.join(", ")}`
    : "Favorites: none";
  const recentsText = recents.length > 0
    ? `Recent inserts: ${recents.join(", ")}`
    : "Recent inserts: none";
  elements.catalogQuickPicks.textContent = `${favoritesText} • ${recentsText}`;
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
  updateContextChips();
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
  setEditorDirty(true);
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
  let stableCount = 0;
  let experimentalCount = 0;
  for (const group of schema.groups || []) {
    for (const field of group.fields || []) {
      if (field.curated) curatedCount += 1;
      const stability = String(field.stability || "").toLowerCase();
      if (stability === "stable") stableCount += 1;
      if (stability === "experimental") experimentalCount += 1;
    }
  }
  const parts = [];
  parts.push(`Groups: ${(facets.groups || []).length}`);
  parts.push(`Fields: ${schema.field_count || 0}`);
  parts.push(`Curated: ${curatedCount}`);
  parts.push(`Stable: ${stableCount}`);
  parts.push(`Experimental: ${experimentalCount}`);
  parts.push(`Sources: ${(facets.sources || []).length}`);
  parts.push(`Tags: ${(facets.tags || []).length}`);
  parts.push(`Overlaps: ${overlaps.length}`);
  elements.catalogDiagnostics.textContent = parts.join(" • ");
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
  setSelectOptions(
    elements.schemaStabilityFilter,
    Array.isArray(facets.stability) ? facets.stability.slice() : [],
    "All Stability Levels",
  );
  setSelectOptions(
    elements.schemaCostTierFilter,
    Array.isArray(facets.cost_tiers) ? facets.cost_tiers.slice() : [],
    "All Cost Tiers",
  );
  setSelectOptions(
    elements.schemaFreshnessFilter,
    Array.isArray(facets.freshness) ? facets.freshness.slice() : [],
    "All Freshness",
  );
  renderCatalogQuickPicks();
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
  noteRecentField(path);
  setStatus(`Inserted ${path}`, "ok");
  queueAutoPreview();
}

function setSelectValueIfPresent(select, value, fallback = "all") {
  if (!select) return;
  const target = String(value || fallback);
  const exists = Array.from(select.options || []).some((option) => option.value === target);
  select.value = exists ? target : fallback;
}

function resetCatalogFilters(options = {}) {
  const { announce = true } = options;
  setSelectValueIfPresent(elements.schemaSourceFilter, "all");
  setSelectValueIfPresent(elements.schemaGroupFilter, "all");
  setSelectValueIfPresent(elements.schemaTypeFilter, "all");
  setSelectValueIfPresent(elements.schemaTagFilter, "all");
  setSelectValueIfPresent(elements.schemaStabilityFilter, "all");
  setSelectValueIfPresent(elements.schemaCostTierFilter, "all");
  setSelectValueIfPresent(elements.schemaFreshnessFilter, "all");
  state.catalogScope = "all";
  updateScopePills();
  renderSchemaCatalog(elements.schemaSearch.value || "");
  if (announce) {
    setStatus("Catalog filters reset", "ok");
  }
}

function updateScopePills() {
  if (!elements.catalogScopePills) return;
  const pills = elements.catalogScopePills.querySelectorAll(".scope-pill");
  for (const pill of pills) {
    const scope = String(pill.dataset.scope || "all");
    pill.classList.toggle("is-active", state.catalogScope !== "custom" && scope === state.catalogScope);
  }
}

function applyCatalogScope(scope, options = {}) {
  const { announce = true } = options;
  const value = String(scope || "all");
  state.catalogScope = value;
  updateScopePills();
  renderSchemaCatalog(elements.schemaSearch.value || "");
  if (announce) {
    const label = value.replaceAll("_", " ");
    setStatus(`Catalog scope: ${label}`, "ok");
  }
}

function fieldAppearsInTemplate(path, templateText) {
  const key = String(path || "").trim();
  if (!key) return false;
  const haystack = String(templateText || "");
  if (!haystack) return false;
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(^|[^A-Za-z0-9_])${escaped}([^A-Za-z0-9_]|$)`);
  return pattern.test(haystack);
}

function schemaSortValue(record, key) {
  const field = record?.field || {};
  if (key === "path") return String(field.path || "");
  if (key === "source") return String(record?.source || "");
  if (key === "group") return String(record?.group || "");
  if (key === "type") return String(field.type || "");
  if (key === "stability") return String(field.stability || "");
  if (key === "cost") return String(field.cost_tier || "");
  if (key === "freshness") return String(field.freshness || "");
  if (key === "sample") return stringifySample(field.sample);
  return String(field.path || "");
}

function cycleSchemaSort(key) {
  const nextKey = String(key || "path");
  if (state.schemaSortKey !== nextKey) {
    state.schemaSortKey = nextKey;
    state.schemaSortDir = "asc";
  } else if (state.schemaSortDir === "asc") {
    state.schemaSortDir = "desc";
  } else {
    state.schemaSortDir = "asc";
  }
  renderSchemaCatalog(elements.schemaSearch.value || "");
}

function selectedCatalogIndex() {
  if (!Array.isArray(state.catalogRows) || state.catalogRows.length === 0) return -1;
  return state.catalogRows.findIndex((row) => String(row.field.path || "") === state.selectedCatalogPath);
}

function selectCatalogIndex(index, options = {}) {
  if (!Array.isArray(state.catalogRows) || state.catalogRows.length === 0) return;
  const { ensureVisible = true } = options;
  const bounded = Math.max(0, Math.min(state.catalogRows.length - 1, Number(index) || 0));
  const target = state.catalogRows[bounded];
  const path = String(target?.field?.path || "");
  if (!path) return;
  state.selectedCatalogPath = path;
  renderSchemaCatalog(elements.schemaSearch.value || "", { ensureSelectionVisible: ensureVisible });
}

function moveCatalogSelection(delta) {
  if (!Array.isArray(state.catalogRows) || state.catalogRows.length === 0) return;
  const current = selectedCatalogIndex();
  const start = current >= 0 ? current : 0;
  selectCatalogIndex(start + delta, { ensureVisible: true });
}

function insertSelectedCatalogField() {
  const index = selectedCatalogIndex();
  if (index < 0) return;
  const record = state.catalogRows[index];
  const path = String(record?.field?.path || "");
  if (!path) return;
  insertFieldWithTransform(path, "{{ {path} }}");
}

function focusSchemaSearch() {
  if (!elements.schemaSearch) return;
  elements.schemaSearch.focus();
  elements.schemaSearch.select();
}

function hasAnyModalOpen() {
  return Boolean(
    elements.publishModal?.classList.contains("open") ||
    elements.tourModal?.classList.contains("open") ||
    elements.versionDiffModal?.classList.contains("open") ||
    elements.commandPaletteModal?.classList.contains("open"),
  );
}

function isTypingContext(target) {
  if (!target) return false;
  const tag = String(target.tagName || "").toLowerCase();
  if (target.isContentEditable) return true;
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  return false;
}

function isCatalogFocusContext() {
  const active = document.activeElement;
  if (!active) return false;
  if (active === document.body) return true;
  if (active === elements.schemaList || active === elements.schemaInspector || active === elements.schemaSearch) {
    return true;
  }
  if (elements.schemaList?.contains(active) || elements.schemaInspector?.contains(active)) return true;
  return false;
}

function getFilteredSchemaRows(filterText = "") {
  const schema = state.schema;
  if (!schema || !Array.isArray(schema.groups) || schema.groups.length === 0) {
    return [];
  }

  const q = String(filterText || "").trim().toLowerCase();
  const sourceFilter = elements.schemaSourceFilter.value || "all";
  const groupFilter = elements.schemaGroupFilter.value || "all";
  const typeFilter = elements.schemaTypeFilter.value || "all";
  const tagFilter = elements.schemaTagFilter.value || "all";
  const stabilityFilter = elements.schemaStabilityFilter.value || "all";
  const costTierFilter = elements.schemaCostTierFilter.value || "all";
  const freshnessFilter = elements.schemaFreshnessFilter.value || "all";
  const curatedOnly = state.catalogScope === "curated";
  const stableOnly = state.catalogScope === "stable";
  const favoritesOnly = state.catalogScope === "favorites";
  const inTemplateOnly = state.catalogScope === "in_template";
  const templateText = inTemplateOnly ? getEditorText() : "";

  const rows = [];
  for (const group of schema.groups) {
    const groupName = String(group.group || "");
    const groupSource = String(group.source || "");
    if (groupFilter !== "all" && groupName !== groupFilter) {
      continue;
    }
    for (const field of group.fields || []) {
      const path = String(field.path || "").trim();
      if (!path) continue;
      const fieldSource = String(field.source || groupSource || "Unknown");
      const fieldType = String(field.type || "");
      const fieldTags = Array.isArray(field.tags) ? field.tags.map((tag) => String(tag)) : [];
      const fieldStability = String(field.stability || "");
      const fieldCostTier = String(field.cost_tier || "");
      const fieldFreshness = String(field.freshness || "");
      const isFavorite = isFavoriteField(path);

      if (sourceFilter !== "all" && fieldSource !== sourceFilter) continue;
      if (typeFilter !== "all" && fieldType !== typeFilter) continue;
      if (tagFilter !== "all" && !fieldTags.includes(tagFilter)) continue;
      if (curatedOnly && !field.curated) continue;
      if (stableOnly && fieldStability !== "stable") continue;
      if (stabilityFilter !== "all" && fieldStability !== stabilityFilter) continue;
      if (costTierFilter !== "all" && fieldCostTier !== costTierFilter) continue;
      if (freshnessFilter !== "all" && fieldFreshness !== freshnessFilter) continue;
      if (favoritesOnly && !isFavorite) continue;
      if (inTemplateOnly && !fieldAppearsInTemplate(path, templateText)) continue;

      if (q) {
        const alternatives = Array.isArray(field.alternatives)
          ? field.alternatives.map((alt) => String(alt))
          : [];
        const match = (
          path.toLowerCase().includes(q) ||
          String(field.label || "").toLowerCase().includes(q) ||
          String(field.description || "").toLowerCase().includes(q) ||
          fieldType.toLowerCase().includes(q) ||
          fieldSource.toLowerCase().includes(q) ||
          String(field.source_note || "").toLowerCase().includes(q) ||
          String(field.metric_key || "").toLowerCase().includes(q) ||
          fieldStability.toLowerCase().includes(q) ||
          fieldCostTier.toLowerCase().includes(q) ||
          fieldFreshness.toLowerCase().includes(q) ||
          String(field.units || "").toLowerCase().includes(q) ||
          groupName.toLowerCase().includes(q) ||
          fieldTags.join(" ").toLowerCase().includes(q) ||
          alternatives.join(" ").toLowerCase().includes(q)
        );
        if (!match) continue;
      }

      rows.push({
        group: groupName,
        source: fieldSource,
        field,
      });
    }
  }

  rows.sort((a, b) => {
    const left = schemaSortValue(a, state.schemaSortKey);
    const right = schemaSortValue(b, state.schemaSortKey);
    const base = String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: "base" });
    const direction = state.schemaSortDir === "desc" ? -1 : 1;
    if (base !== 0) return base * direction;
    const groupCmp = String(a.group || "").localeCompare(String(b.group || ""));
    if (groupCmp !== 0) return groupCmp;
    return String(a.field.path || "").localeCompare(String(b.field.path || ""));
  });
  return rows;
}

function renderSchemaInspector(record) {
  if (!elements.schemaInspector) return;
  const pane = elements.schemaInspector;
  pane.innerHTML = "";

  const title = document.createElement("h3");
  title.textContent = "Field Inspector";
  pane.appendChild(title);

  if (!record) {
    const empty = document.createElement("p");
    empty.className = "subtext";
    empty.textContent = "Select a field from the table to inspect details.";
    pane.appendChild(empty);
    return;
  }

  const { field, group, source } = record;
  const path = String(field.path || "");
  const token = `{{ ${path} }}`;

  const line = document.createElement("div");
  line.className = "inspector-path";
  line.textContent = token;
  pane.appendChild(line);

  const desc = document.createElement("p");
  desc.className = "subtext";
  desc.textContent = field.description || "No field description.";
  pane.appendChild(desc);

  const badges = document.createElement("div");
  badges.className = "inspector-badges";
  const badgeValues = [
    { label: source || "Unknown", type: "" },
    { label: group || "misc", type: "" },
    { label: String(field.type || "unknown"), type: "" },
    { label: String(field.stability || "medium"), type: String(field.stability || "medium").toLowerCase() },
    { label: `cost:${String(field.cost_tier || "medium")}`, type: String(field.cost_tier || "medium").toLowerCase() },
    { label: `fresh:${String(field.freshness || "activity")}`, type: "" },
  ];
  for (const item of badgeValues) {
    const badge = document.createElement("span");
    badge.className = `badge ${item.type}`.trim();
    badge.textContent = item.label;
    badges.appendChild(badge);
  }
  pane.appendChild(badges);

  const actions = document.createElement("div");
  actions.className = "inline-actions";

  const insertBtn = document.createElement("button");
  insertBtn.type = "button";
  insertBtn.className = "field-insert";
  insertBtn.textContent = "Insert";
  insertBtn.addEventListener("click", () => {
    insertFieldWithTransform(path, "{{ {path} }}");
  });
  actions.appendChild(insertBtn);

  const favoriteBtn = document.createElement("button");
  favoriteBtn.type = "button";
  favoriteBtn.className = "field-favorite";
  favoriteBtn.textContent = isFavoriteField(path) ? "★ Favorite" : "☆ Favorite";
  favoriteBtn.addEventListener("click", () => {
    toggleFavoriteField(path);
    renderSchemaInspector(record);
  });
  actions.appendChild(favoriteBtn);

  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "field-insert";
  copyBtn.textContent = "Copy Token";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(token);
      setStatus(`Copied token: ${path}`, "ok");
    } catch (_err) {
      setStatus("Clipboard copy failed", "error");
    }
  });
  actions.appendChild(copyBtn);
  pane.appendChild(actions);

  if (Array.isArray(state.helperTransforms) && state.helperTransforms.length > 0) {
    const transformRow = document.createElement("div");
    transformRow.className = "inspector-transform";
    const transformSelect = document.createElement("select");
    transformSelect.className = "field-transform";
    for (const transform of state.helperTransforms) {
      const option = document.createElement("option");
      option.value = String(transform.template || "{{ {path} }}");
      option.textContent = String(transform.label || transform.id || "Transform");
      transformSelect.appendChild(option);
    }
    const transformBtn = document.createElement("button");
    transformBtn.type = "button";
    transformBtn.className = "field-insert";
    transformBtn.textContent = "Insert As";
    transformBtn.addEventListener("click", () => {
      insertFieldWithTransform(path, transformSelect.value);
    });
    transformRow.appendChild(transformSelect);
    transformRow.appendChild(transformBtn);
    pane.appendChild(transformRow);
  }

  const details = document.createElement("div");
  details.className = "inspector-details";
  const rows = [];
  rows.push(`Label: ${field.label || path}`);
  rows.push(`Source: ${source}${field.source_note ? ` (${field.source_note})` : ""}`);
  rows.push(`Metric key: ${field.metric_key || "none"}`);
  rows.push(`Units: ${field.units || "none"}`);
  const tags = Array.isArray(field.tags) ? field.tags : [];
  rows.push(`Tags: ${tags.length > 0 ? tags.join(", ") : "none"}`);
  const alternatives = Array.isArray(field.alternatives) ? field.alternatives : [];
  rows.push(`Alternatives: ${alternatives.length > 0 ? alternatives.join(", ") : "none"}`);
  rows.push(`Sample: ${stringifySample(field.sample)}`);
  details.textContent = rows.join("\n");
  pane.appendChild(details);
}

function renderSchemaCatalog(filterText = "", options = {}) {
  const { ensureSelectionVisible = false } = options;
  const schema = state.schema;
  elements.schemaList.innerHTML = "";

  if (!schema || !Array.isArray(schema.groups) || schema.groups.length === 0) {
    const contextMode = elements.schemaContextMode.value || "sample";
    elements.schemaMeta.textContent =
      `No schema fields available. Try context mode '${contextMode}' or run one worker cycle to populate latest payload context.`;
    state.catalogRows = [];
    if (elements.schemaKeyboardHint) {
      elements.schemaKeyboardHint.textContent = "Keyboard: Ctrl+F search · ↑/↓ navigate · Enter insert · → inspect · Ctrl+K commands";
    }
    renderSchemaInspector(null);
    return;
  }

  const rows = getFilteredSchemaRows(filterText);
  state.catalogRows = rows.slice();
  const sourceText = state.schemaSource ? ` | context: ${state.schemaSource}` : "";

  if (rows.length === 0) {
    const activeFilters = [];
    const sourceValue = elements.schemaSourceFilter.value || "all";
    const groupValue = elements.schemaGroupFilter.value || "all";
    const typeValue = elements.schemaTypeFilter.value || "all";
    const tagValue = elements.schemaTagFilter.value || "all";
    if (sourceValue !== "all") activeFilters.push(`source=${sourceValue}`);
    if (groupValue !== "all") activeFilters.push(`group=${groupValue}`);
    if (typeValue !== "all") activeFilters.push(`type=${typeValue}`);
    if (tagValue !== "all") activeFilters.push(`tag=${tagValue}`);
    if (elements.schemaStabilityFilter.value !== "all") activeFilters.push(`stability=${elements.schemaStabilityFilter.value}`);
    if (elements.schemaCostTierFilter.value !== "all") activeFilters.push(`cost=${elements.schemaCostTierFilter.value}`);
    if (elements.schemaFreshnessFilter.value !== "all") activeFilters.push(`freshness=${elements.schemaFreshnessFilter.value}`);
    if (state.catalogScope !== "all") activeFilters.push(`scope=${state.catalogScope}`);
    const filterTextLabel = activeFilters.length > 0 ? ` with filters (${activeFilters.join(", ")})` : "";
    elements.schemaMeta.textContent = `No fields matched${filterTextLabel}${sourceText}.`;
    state.selectedCatalogPath = "";
    state.catalogRows = [];
    if (elements.schemaKeyboardHint) {
      elements.schemaKeyboardHint.textContent = "Keyboard: Ctrl+F search · ↑/↓ navigate · Enter insert · → inspect · Ctrl+K commands | 0 rows";
    }
    renderSchemaInspector(null);
    return;
  }

  const selectedExists = rows.some((row) => String(row.field.path || "") === state.selectedCatalogPath);
  if (!selectedExists) {
    state.selectedCatalogPath = String(rows[0].field.path || "");
  }

  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const headers = [
    { label: "★", key: null },
    { label: "Field", key: "path" },
    { label: "Source", key: "source" },
    { label: "Group", key: "group" },
    { label: "Type", key: "type" },
    { label: "Stability", key: "stability" },
    { label: "Cost", key: "cost" },
    { label: "Freshness", key: "freshness" },
    { label: "Example", key: "sample" },
    { label: "Action", key: null },
  ];
  for (const header of headers) {
    const th = document.createElement("th");
    if (!header.key) {
      th.textContent = header.label;
      headRow.appendChild(th);
      continue;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sort-head-btn";
    const active = state.schemaSortKey === header.key;
    const arrow = active ? (state.schemaSortDir === "desc" ? " ↓" : " ↑") : "";
    button.textContent = `${header.label}${arrow}`;
    button.title = `Sort by ${header.label}`;
    button.addEventListener("click", () => cycleSchemaSort(header.key));
    th.appendChild(button);
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  let selectedRecord = null;

  for (const record of rows) {
    const { field, group, source } = record;
    const path = String(field.path || "");
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.dataset.path = path;
    if (path === state.selectedCatalogPath) {
      row.classList.add("is-selected");
      selectedRecord = record;
    }
    row.addEventListener("click", () => {
      state.selectedCatalogPath = path;
      renderSchemaCatalog(elements.schemaSearch.value || "");
    });
    row.addEventListener("dblclick", () => {
      insertFieldWithTransform(path, "{{ {path} }}");
    });

    const favCell = document.createElement("td");
    const favBtn = document.createElement("button");
    favBtn.className = "field-favorite";
    favBtn.type = "button";
    favBtn.title = isFavoriteField(path) ? "Remove favorite" : "Add favorite";
    favBtn.textContent = isFavoriteField(path) ? "★" : "☆";
    favBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      state.selectedCatalogPath = path;
      toggleFavoriteField(path);
    });
    favCell.appendChild(favBtn);
    row.appendChild(favCell);

    const fieldCell = document.createElement("td");
    const fieldLabel = document.createElement("div");
    fieldLabel.textContent = field.label || path;
    const fieldPath = document.createElement("div");
    fieldPath.className = "mono";
    fieldPath.textContent = path;
    fieldCell.appendChild(fieldLabel);
    fieldCell.appendChild(fieldPath);
    row.appendChild(fieldCell);

    const sourceCell = document.createElement("td");
    sourceCell.textContent = source || "Unknown";
    row.appendChild(sourceCell);

    const groupCell = document.createElement("td");
    groupCell.textContent = group || "misc";
    row.appendChild(groupCell);

    const typeCell = document.createElement("td");
    typeCell.textContent = String(field.type || "");
    row.appendChild(typeCell);

    const stabilityCell = document.createElement("td");
    const stabilityBadge = document.createElement("span");
    const stabilityLabel = String(field.stability || "medium");
    stabilityBadge.className = `badge ${stabilityLabel.toLowerCase()}`;
    stabilityBadge.textContent = stabilityLabel;
    stabilityCell.appendChild(stabilityBadge);
    row.appendChild(stabilityCell);

    const costCell = document.createElement("td");
    costCell.textContent = String(field.cost_tier || "medium");
    row.appendChild(costCell);

    const freshCell = document.createElement("td");
    freshCell.textContent = String(field.freshness || "activity");
    row.appendChild(freshCell);

    const sampleCell = document.createElement("td");
    const sampleText = stringifySample(field.sample);
    sampleCell.className = "mono";
    sampleCell.textContent = sampleText.length > 56 ? `${sampleText.slice(0, 56)}…` : sampleText;
    sampleCell.title = sampleText;
    row.appendChild(sampleCell);

    const actionCell = document.createElement("td");
    const insertBtn = document.createElement("button");
    insertBtn.className = "field-insert";
    insertBtn.type = "button";
    insertBtn.textContent = "Insert";
    insertBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      insertFieldWithTransform(path, "{{ {path} }}");
      state.selectedCatalogPath = path;
    });
    actionCell.appendChild(insertBtn);
    row.appendChild(actionCell);

    tbody.appendChild(row);
  }

  table.appendChild(tbody);
  elements.schemaList.appendChild(table);
  elements.schemaMeta.textContent = `${rows.length} fields shown${sourceText}`;
  if (elements.schemaKeyboardHint) {
    elements.schemaKeyboardHint.textContent =
      `Keyboard: Ctrl+F search · ↑/↓ navigate · Enter insert · → inspect · Ctrl+K commands | ${rows.length} rows`;
  }

  if (!selectedRecord && rows.length > 0) {
    selectedRecord = rows[0];
  }
  renderSchemaInspector(selectedRecord);
  if (ensureSelectionVisible) {
    const selectedRow = elements.schemaList.querySelector("tbody tr.is-selected");
    selectedRow?.scrollIntoView({ block: "nearest" });
    selectedRow?.focus({ preventScroll: true });
  }
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

function closeVersionDiffModal() {
  if (!elements.versionDiffModal) return;
  elements.versionDiffModal.classList.remove("open");
  elements.versionDiffModal.setAttribute("aria-hidden", "true");
}

async function openVersionDiffModal(versionId) {
  if (!elements.versionDiffModal || !versionId) return;
  elements.versionDiffModal.classList.add("open");
  elements.versionDiffModal.setAttribute("aria-hidden", "false");
  if (elements.versionDiffMeta) elements.versionDiffMeta.textContent = "Loading diff...";
  if (elements.versionDiffView) elements.versionDiffView.textContent = "";

  const res = await requestJSON(
    `/editor/template/version/${encodeURIComponent(versionId)}?profile_id=${encodeURIComponent(currentProfileId())}`
  );
  if (!res.ok) {
    if (elements.versionDiffMeta) elements.versionDiffMeta.textContent = `Failed to load version ${versionId}`;
    return;
  }
  const template = String(res.payload?.version?.template || "");
  const diffRows = computeLineDiff(getEditorText(), template);
  const summary = summarizeLineDiff(diffRows);
  if (elements.versionDiffMeta) {
    elements.versionDiffMeta.textContent =
      `Editor vs ${versionId}: +${summary.added} / -${summary.removed} / unchanged ${summary.unchanged} / changed~ ${summary.changed}`;
  }
  if (elements.versionDiffView) {
    elements.versionDiffView.textContent = renderDiffRows(diffRows, 260);
  }
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
      profile_id: currentProfileId(),
    }),
  });

  setPublishValidationSummary(validationRes.payload || {}, validationRes.ok);
  state.publishModalValidationOk = Boolean(validationRes.ok);
  state.lastValidationOk = Boolean(validationRes.ok);
  updateContextChips();
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
  updateContextChips();
}

function selectedFixtureName() {
  return (elements.previewFixtureName.value || "default").trim().toLowerCase();
}

function renderTemplateMeta(meta) {
  if (!meta) {
    elements.templateMeta.textContent = "No template metadata.";
    updateCurrentTemplateDisplay(state.templateName);
    updateCurrentProfileDisplay();
    return;
  }
  const lines = [];
  lines.push(`Name: ${meta.name || "Auto Stat Template"}`);
  lines.push(`Version: ${meta.current_version || "none"}`);
  lines.push(`Updated: ${meta.updated_at_utc || "unknown"}`);
  lines.push(`By: ${meta.updated_by || "unknown"} | Source: ${meta.source || "unknown"}`);
  elements.templateMeta.textContent = lines.join("\n");
  updateCurrentTemplateDisplay(String(meta.name || state.templateName || "").trim());
  updateCurrentProfileDisplay();
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
  updateCurrentTemplateDisplay(String(name || "").trim());
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
  setEditorDirty(false);
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

    const diffBtn = document.createElement("button");
    diffBtn.className = "field-insert";
    diffBtn.textContent = "Diff";
    diffBtn.addEventListener("click", async () => {
      await openVersionDiffModal(String(version.version_id || ""));
    });

    controls.appendChild(loadBtn);
    controls.appendChild(rollbackBtn);
    controls.appendChild(diffBtn);

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
  const res = await requestJSON(
    `/editor/template/versions?limit=40&profile_id=${encodeURIComponent(currentProfileId())}`
  );
  if (!res.ok) {
    setStatus("Failed to load template history", "error");
    return;
  }
  state.versions = Array.isArray(res.payload.versions) ? res.payload.versions : [];
  renderVersionHistory();
}

async function loadTemplateVersion(versionId) {
  if (!versionId) return;
  const res = await requestJSON(
    `/editor/template/version/${encodeURIComponent(versionId)}?profile_id=${encodeURIComponent(currentProfileId())}`
  );
  if (!res.ok) {
    setStatus("Failed to load version", "error");
    return;
  }
  const record = res.payload.version || {};
  setEditorText(record.template || "");
  setEditorDirty(false);
  updateCurrentTemplateDisplay(record.name || `Version ${versionId}`);
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
      profile_id: currentProfileId(),
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
    setEditorDirty(true);
    setStatus("Loaded local draft", "ok");
    queueAutoPreview();
  } catch (_err) {
    setStatus("Draft load failed", "error");
  }
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

function closeCommandPalette() {
  if (!elements.commandPaletteModal) return;
  elements.commandPaletteModal.classList.remove("open");
  elements.commandPaletteModal.setAttribute("aria-hidden", "true");
}

function commandPaletteActions() {
  return [
    {
      id: "preview",
      title: "Run Preview",
      description: "Render current template with active preview context",
      run: async () => previewTemplate({ force: true }),
    },
    {
      id: "validate",
      title: "Validate Template",
      description: "Run validation checks and hints",
      run: async () => validateTemplate(),
    },
    {
      id: "publish",
      title: "Open Publish Modal",
      description: "Review validation + diff before publish",
      run: async () => openPublishModal(),
    },
    {
      id: "focus-data",
      title: "Focus Data Search",
      description: "Jump to Available Data search box",
      run: async () => focusSchemaSearch(),
    },
    {
      id: "toggle-drawer",
      title: "Toggle Workspace Drawer",
      description: "Show/hide Template Repository, History, and Links",
      run: async () => toggleDrawer(),
    },
    {
      id: "load-active",
      title: "Load Active Template",
      description: "Replace editor with active template",
      run: async () => {
        setEditorText(state.templateActive);
        setEditorDirty(false);
        queueAutoPreview();
      },
    },
    {
      id: "load-default",
      title: "Load Default Template",
      description: "Replace editor with default template",
      run: async () => {
        setEditorText(state.templateDefault);
        setEditorDirty(state.templateDefault !== state.templateActive);
        queueAutoPreview();
      },
    },
    {
      id: "save-draft",
      title: "Save Draft",
      description: "Store current template in browser local draft",
      run: async () => saveDraft(),
    },
    {
      id: "toggle-theme",
      title: "Toggle Theme",
      description: "Switch between dark and light mode",
      run: async () => {
        const next = document.body.dataset.theme === "dark" ? "light" : "dark";
        applyTheme(next);
      },
    },
    {
      id: "toggle-autopreview",
      title: state.autoPreview ? "Disable Auto-preview" : "Enable Auto-preview",
      description: "Toggle automatic preview refresh on edits",
      run: async () => {
        state.autoPreview = !state.autoPreview;
        if (elements.autoPreviewToggle) {
          elements.autoPreviewToggle.checked = state.autoPreview;
        }
        updateActionEmphasis();
        if (state.autoPreview) queueAutoPreview();
      },
    },
  ];
}

function renderCommandPaletteList(items) {
  if (!elements.commandPaletteList) return;
  elements.commandPaletteList.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "meta";
    empty.textContent = "No commands found.";
    elements.commandPaletteList.appendChild(empty);
    return;
  }
  state.commandPaletteActiveIndex = Math.max(0, Math.min(items.length - 1, state.commandPaletteActiveIndex));
  items.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "command-item";
    if (index === state.commandPaletteActiveIndex) {
      row.classList.add("is-active");
    }
    row.addEventListener("click", async () => {
      state.commandPaletteActiveIndex = index;
      await executeCommandPaletteSelection();
    });

    const title = document.createElement("div");
    title.className = "command-item-title";
    title.textContent = item.title;
    row.appendChild(title);

    const desc = document.createElement("div");
    desc.className = "command-item-desc";
    desc.textContent = item.description;
    row.appendChild(desc);

    elements.commandPaletteList.appendChild(row);
  });
  if (elements.commandPaletteMeta) {
    elements.commandPaletteMeta.textContent = `${items.length} command(s) available`;
  }
}

function updateCommandPaletteResults() {
  const all = commandPaletteActions();
  const q = String(elements.commandPaletteSearch?.value || "").trim().toLowerCase();
  const filtered = all.filter((item) => {
    if (!q) return true;
    return (
      item.title.toLowerCase().includes(q) ||
      item.description.toLowerCase().includes(q) ||
      item.id.toLowerCase().includes(q)
    );
  });
  state.commandPaletteItems = filtered;
  state.commandPaletteActiveIndex = 0;
  renderCommandPaletteList(filtered);
}

async function executeCommandPaletteSelection() {
  if (!Array.isArray(state.commandPaletteItems) || state.commandPaletteItems.length === 0) return;
  const index = Math.max(0, Math.min(state.commandPaletteItems.length - 1, state.commandPaletteActiveIndex));
  const selected = state.commandPaletteItems[index];
  if (!selected) return;
  closeCommandPalette();
  try {
    await selected.run();
    setStatus(`Command executed: ${selected.title}`, "ok");
  } catch (_err) {
    setStatus(`Command failed: ${selected.title}`, "error");
  }
}

function openCommandPalette() {
  if (!elements.commandPaletteModal) return;
  elements.commandPaletteModal.classList.add("open");
  elements.commandPaletteModal.setAttribute("aria-hidden", "false");
  if (elements.commandPaletteSearch) {
    elements.commandPaletteSearch.value = "";
    elements.commandPaletteSearch.focus();
  }
  updateCommandPaletteResults();
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
  const [profilesRes, activeRes, defaultRes, schemaRes, snippetRes, fixtureRes, versionsRes, repositoryRes] = await Promise.all([
    requestJSON("/editor/profiles"),
    requestJSON("/editor/template"),
    requestJSON("/editor/template/default"),
    requestJSON(`/editor/catalog?context_mode=${encodeURIComponent(schemaMode)}&fixture_name=${encodeURIComponent(fixtureName)}`),
    requestJSON("/editor/snippets"),
    requestJSON("/editor/fixtures"),
    requestJSON("/editor/template/versions?limit=40"),
    requestJSON("/editor/repository/templates"),
  ]);

  if (!activeRes.ok || !defaultRes.ok) {
    setStatus("Failed to load templates", "error");
    return;
  }

  if (profilesRes.ok) {
    state.profiles = Array.isArray(profilesRes.payload.profiles) ? profilesRes.payload.profiles : [];
    state.workingProfileId = String(profilesRes.payload.working_profile_id || "default");
    renderProfileWorkspace();
  }

  state.templateActive = decodeEscapedNewlines(activeRes.payload.template || "");
  state.templateDefault = decodeEscapedNewlines(defaultRes.payload.template || "");
  state.templateMeta = activeRes.payload || null;
  state.workingProfileId = String(activeRes.payload.profile_id || state.workingProfileId || "default");
  renderProfileWorkspace();
  state.templateName = String(activeRes.payload.name || "Auto Stat Template");
  state.lastValidationOk = null;
  clearActivePreviewCache();

  setEditorText(state.templateActive);
  setEditorDirty(false);
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
  state.catalogScope = "all";
  updateScopePills();
  renderCatalogQuickPicks();
  renderSchemaCatalog("");
  renderSimpleSections();
  renderSnippets();
  renderTemplateMeta(state.templateMeta);
  renderVersionHistory();
  updateCurrentProfileDisplay();

  state.autoPreview = true;
  elements.autoPreviewToggle.checked = true;
  updateActionEmphasis();

  const isCustom = Boolean(activeRes.payload.is_custom);
  const sourceLabel = state.schemaSource ? ` | schema: ${state.schemaSource}` : "";
  setStatus((isCustom ? "Loaded custom template" : "Loaded default template") + sourceLabel, "ok");
  renderContextSafetyBanner();
  updateContextChips();

  await previewTemplate({ force: true });
}

async function validateTemplate() {
  const template = getEditorText();
  const contextMode = elements.previewContextMode.value || "sample";
  const fixtureName = selectedFixtureName();
  const res = await requestJSON("/editor/validate", {
    method: "POST",
    body: JSON.stringify({
      template,
      context_mode: contextMode,
      fixture_name: fixtureName,
      profile_id: currentProfileId(),
    }),
  });

  updateValidationPane(res.payload, res.ok);
  state.lastValidationOk = Boolean(res.ok);
  updateContextChips();
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
    body: JSON.stringify({
      template,
      context_mode: contextMode,
      fixture_name: fixtureName,
      profile_id: currentProfileId(),
    }),
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
    updatePreviewCharMeter();
    state.lastValidationOk = false;
    updateContextChips();
    await updatePreviewDiff(elements.previewText.textContent || "");
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
  state.lastValidationOk = true;
  updateContextChips();
  updatePreviewCharMeter();
  await updatePreviewDiff(rendered);
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
  const contextMode = elements.previewContextMode.value || "sample";
  const fixtureName = selectedFixtureName();
  const res = await requestJSON("/editor/template", {
    method: "PUT",
    body: JSON.stringify({
      template,
      author: author || "editor-user",
      source,
      name: name || "Auto Stat Template",
      context_mode: contextMode,
      fixture_name: fixtureName,
      profile_id: currentProfileId(),
    }),
  });

  if (!res.ok) {
    updateValidationPane(res.payload, false);
    setStatus("Save failed", "error");
    return false;
  }

  updateValidationPane(res.payload, true);
  state.workingProfileId = String(res.payload.profile_id || state.workingProfileId || "default");
  state.templateActive = template;
  state.templateMeta = res.payload.active || state.templateMeta;
  state.templateName = String(name || state.templateName || "Auto Stat Template");
  state.lastValidationOk = true;
  clearActivePreviewCache();
  setEditorDirty(false);
  renderTemplateMeta(state.templateMeta);
  updateCurrentProfileDisplay();
  await loadVersionHistory();
  await updatePreviewDiff(elements.previewText.textContent || "");
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
  if (elements.schemaInspector) {
    elements.schemaInspector.tabIndex = -1;
  }
  if (elements.btnDrawerToggle) {
    elements.btnDrawerToggle.addEventListener("click", openDrawer);
  }
  if (elements.btnProfileDrawerToggle) {
    elements.btnProfileDrawerToggle.addEventListener("click", openProfileWorkspace);
  }
  if (elements.btnDrawerClose) {
    elements.btnDrawerClose.addEventListener("click", closeDrawer);
  }
  if (elements.drawerBackdrop) {
    elements.drawerBackdrop.addEventListener("click", closeDrawer);
  }
  if (elements.btnSettingsToggle) {
    elements.btnSettingsToggle.addEventListener("click", toggleSettingsPanel);
  }
  if (elements.btnSettingsClose) {
    elements.btnSettingsClose.addEventListener("click", closeSettingsPanel);
  }
  document.addEventListener("click", (event) => {
    if (!elements.settingsPanel?.classList.contains("open")) return;
    const target = event.target;
    if (!(target instanceof Node)) return;
    if (elements.settingsPanel.contains(target)) return;
    if (elements.btnSettingsToggle?.contains(target)) return;
    closeSettingsPanel();
  });
  if (elements.btnToggleAdvancedFilters && elements.advancedFiltersWrap) {
    elements.btnToggleAdvancedFilters.addEventListener("click", () => {
      const isHidden = elements.advancedFiltersWrap.classList.toggle("is-hidden");
      elements.btnToggleAdvancedFilters.textContent = isHidden ? "Show Advanced Filters" : "Hide Advanced Filters";
    });
  }
  if (elements.catalogScopePills) {
    elements.catalogScopePills.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (!target.classList.contains("scope-pill")) return;
      const scope = String(target.dataset.scope || "all");
      applyCatalogScope(scope, { announce: true });
    });
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });

  document.getElementById("btnLoadActive").addEventListener("click", () => {
    setEditorText(state.templateActive);
    setEditorDirty(false);
    setStatus("Loaded active template", "ok");
    queueAutoPreview();
  });

  document.getElementById("btnLoadDefault").addEventListener("click", () => {
    setEditorText(state.templateDefault);
    setEditorDirty(state.templateDefault !== state.templateActive);
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
    setEditorDirty(true);
    setStatus("Formatted: normalized whitespace and blank lines", "ok");
    queueAutoPreview();
  });

  document.getElementById("btnValidate").addEventListener("click", validateTemplate);
  document.getElementById("btnPreview").addEventListener("click", () => previewTemplate({ force: true }));
  document.getElementById("btnSave").addEventListener("click", openPublishModal);
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
  if (elements.repoTemplateNameInput) {
    elements.repoTemplateNameInput.addEventListener("input", () => {
      updateCurrentTemplateDisplay(elements.repoTemplateNameInput.value || "");
    });
  }

  document.getElementById("btnSimpleApply").addEventListener("click", () => {
    setEditorText(buildTemplateFromSimple());
    setEditorDirty(true);
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
    if (state.schemaSearchTimer) {
      clearTimeout(state.schemaSearchTimer);
    }
    const value = event.target.value || "";
    state.schemaSearchTimer = setTimeout(() => {
      renderSchemaCatalog(value);
    }, 130);
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
  elements.schemaStabilityFilter.addEventListener("change", () => {
    renderSchemaCatalog(elements.schemaSearch.value || "");
  });
  elements.schemaCostTierFilter.addEventListener("change", () => {
    renderSchemaCatalog(elements.schemaSearch.value || "");
  });
  elements.schemaFreshnessFilter.addEventListener("change", () => {
    renderSchemaCatalog(elements.schemaSearch.value || "");
  });
  const btnCatalogResetFilters = document.getElementById("btnCatalogResetFilters");
  if (btnCatalogResetFilters) {
    btnCatalogResetFilters.addEventListener("click", () => {
      resetCatalogFilters({ announce: true });
    });
  }

  elements.schemaContextMode.addEventListener("change", async () => {
    await loadSchema(elements.schemaContextMode.value || "sample");
    setStatus("Catalog context changed", "ok");
    updateContextChips();
  });

  elements.previewContextMode.addEventListener("change", () => {
    clearActivePreviewCache();
    renderContextSafetyBanner();
    updateContextChips();
    queueAutoPreview();
  });

  elements.previewFixtureName.addEventListener("change", async () => {
    clearActivePreviewCache();
    renderContextSafetyBanner();
    await loadSchema(elements.schemaContextMode.value || "sample");
    updateContextChips();
    queueAutoPreview();
  });

  elements.autoPreviewToggle.addEventListener("change", () => {
    state.autoPreview = elements.autoPreviewToggle.checked;
    updateActionEmphasis();
    setStatus(state.autoPreview ? "Auto-preview enabled" : "Auto-preview disabled", "ok");
    if (state.autoPreview) {
      queueAutoPreview();
    }
  });

  if (elements.previewDiffToggle) {
    elements.previewDiffToggle.addEventListener("change", async () => {
      state.previewDiffEnabled = Boolean(elements.previewDiffToggle.checked);
      if (!state.previewDiffEnabled) {
        if (elements.previewDiffMeta) elements.previewDiffMeta.textContent = "Diff disabled.";
        if (elements.previewDiffText) {
          elements.previewDiffText.classList.add("is-hidden");
          elements.previewDiffText.textContent = "";
        }
      } else {
        await updatePreviewDiff(elements.previewText.textContent || "");
      }
    });
  }

  elements.themeToggle.addEventListener("change", () => {
    applyTheme(elements.themeToggle.checked ? "dark" : "light");
    setStatus(elements.themeToggle.checked ? "Dark mode enabled" : "Light mode enabled", "ok");
  });

  elements.templateEditor.addEventListener("input", () => {
    setEditorDirty(true);
    if (state.catalogScope === "in_template") {
      renderSchemaCatalog(elements.schemaSearch.value || "");
    }
    queueAutoPreview();
  });

  if (elements.previewCharLimit) {
    elements.previewCharLimit.addEventListener("input", () => {
      updatePreviewCharMeter();
    });
    elements.previewCharLimit.addEventListener("change", () => {
      updatePreviewCharMeter();
    });
  }

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
  if (elements.versionDiffCloseBtn) {
    elements.versionDiffCloseBtn.addEventListener("click", closeVersionDiffModal);
  }
  if (elements.versionDiffModal) {
    elements.versionDiffModal.addEventListener("click", (event) => {
      if (event.target === elements.versionDiffModal) {
        closeVersionDiffModal();
      }
    });
  }
  if (elements.commandPaletteCloseBtn) {
    elements.commandPaletteCloseBtn.addEventListener("click", closeCommandPalette);
  }
  if (elements.commandPaletteModal) {
    elements.commandPaletteModal.addEventListener("click", (event) => {
      if (event.target === elements.commandPaletteModal) {
        closeCommandPalette();
      }
    });
  }
  if (elements.commandPaletteSearch) {
    elements.commandPaletteSearch.addEventListener("input", () => {
      updateCommandPaletteResults();
    });
    elements.commandPaletteSearch.addEventListener("keydown", async (event) => {
      if (!Array.isArray(state.commandPaletteItems) || state.commandPaletteItems.length === 0) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        state.commandPaletteActiveIndex = Math.min(
          state.commandPaletteItems.length - 1,
          state.commandPaletteActiveIndex + 1,
        );
        renderCommandPaletteList(state.commandPaletteItems);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        state.commandPaletteActiveIndex = Math.max(0, state.commandPaletteActiveIndex - 1);
        renderCommandPaletteList(state.commandPaletteItems);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        await executeCommandPaletteSelection();
      }
    });
  }
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (elements.commandPaletteModal?.classList.contains("open")) {
        closeCommandPalette();
      } else {
        openCommandPalette();
      }
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f" && !hasAnyModalOpen()) {
      if (!isTypingContext(event.target)) {
        event.preventDefault();
        focusSchemaSearch();
      }
      return;
    }
    if (event.key === "Escape" && elements.publishModal?.classList.contains("open")) {
      closePublishModal();
      return;
    }
    if (event.key === "Escape" && elements.tourModal?.classList.contains("open")) {
      closeTour({ markSeen: true });
      return;
    }
    if (event.key === "Escape" && elements.versionDiffModal?.classList.contains("open")) {
      closeVersionDiffModal();
      return;
    }
    if (event.key === "Escape" && elements.commandPaletteModal?.classList.contains("open")) {
      closeCommandPalette();
      return;
    }
    if (event.key === "Escape" && elements.leftDrawer?.classList.contains("open")) {
      closeDrawer();
      return;
    }
    if (event.key === "Escape" && elements.settingsPanel?.classList.contains("open")) {
      closeSettingsPanel();
      return;
    }
    if (hasAnyModalOpen()) {
      return;
    }
    if (isTypingContext(event.target)) {
      return;
    }
    if (!isCatalogFocusContext()) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveCatalogSelection(1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveCatalogSelection(-1);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      insertSelectedCatalogField();
      return;
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      elements.schemaInspector?.focus();
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
  loadCatalogPreferences();
  bindUI();
  updateActionEmphasis();
  applyTheme(loadThemePreference());
  updateValidationPane(null, true);
  renderContextSafetyBanner();
  updateContextChips();
  updatePreviewCharMeter();
  await loadEditorBootstrap();
  maybeOpenTourOnFirstRun();
});
