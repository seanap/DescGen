const state = {
  payload: null,
};

const elements = {
  statusBox: document.getElementById("statusBox"),
  providersGrid: document.getElementById("providersGrid"),
  stravaStatus: document.getElementById("stravaStatus"),
  envSnippet: document.getElementById("envSnippet"),
  btnOpenEditor: document.getElementById("btnOpenEditor"),
  btnReload: document.getElementById("btnReload"),
  btnSave: document.getElementById("btnSave"),
  btnStravaConnect: document.getElementById("btnStravaConnect"),
  btnStravaDisconnect: document.getElementById("btnStravaDisconnect"),
  btnRefreshEnv: document.getElementById("btnRefreshEnv"),
  btnCopyEnv: document.getElementById("btnCopyEnv"),
};

function setStatus(text, tone = "neutral") {
  if (!elements.statusBox) return;
  elements.statusBox.textContent = String(text || "").trim() || "Ready";
  elements.statusBox.classList.remove("ok", "error");
  if (tone === "ok") elements.statusBox.classList.add("ok");
  if (tone === "error") elements.statusBox.classList.add("error");
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
    return { ok: false, status: 0, payload: { error: String(error) } };
  }

  const payload = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, payload };
}

function titleCase(text) {
  return String(text || "")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function providerTitle(providerId) {
  const labels = {
    general: "General",
    strava: "Strava",
    garmin: "Garmin",
    intervals: "Intervals.icu",
    weather: "WeatherAPI",
    smashrun: "Smashrun",
    crono: "Crono API",
  };
  return labels[String(providerId || "")] || titleCase(providerId);
}

function keyLabel(key) {
  const labels = {
    INTERVALS_USER_ID: "Intervals Athlete ID",
    STRAVA_CLIENT_ID: "Strava Client ID",
    STRAVA_CLIENT_SECRET: "Strava Client Secret",
    STRAVA_REFRESH_TOKEN: "Strava Refresh Token",
    STRAVA_ACCESS_TOKEN: "Strava Access Token",
    GARMIN_EMAIL: "Garmin Email",
    GARMIN_PASSWORD: "Garmin Password",
    WEATHER_API_KEY: "Weather API Key",
    SMASHRUN_ACCESS_TOKEN: "Smashrun Access Token",
    CRONO_API_BASE_URL: "Crono API Base URL",
    CRONO_API_KEY: "Crono API Key",
    TIMEZONE: "Timezone",
  };
  if (labels[key]) return labels[key];
  return titleCase(key);
}

function isSecretKey(key) {
  const secretKeys = Array.isArray(state.payload?.secret_keys) ? state.payload.secret_keys : [];
  return secretKeys.includes(key);
}

function currentFieldValue(key) {
  const values = state.payload?.values || {};
  return values[key];
}

function maskedFieldValue(key) {
  const values = state.payload?.masked_values || {};
  return values[key];
}

function secretFieldPresent(key) {
  const present = state.payload?.secret_presence || {};
  return Boolean(present[key]);
}

function renderProviders() {
  if (!elements.providersGrid) return;
  elements.providersGrid.innerHTML = "";

  const providerFields = state.payload?.provider_fields || {};
  const providerLinks = state.payload?.provider_links || {};
  const providerIds = Object.keys(providerFields).sort((a, b) => {
    if (a === "general") return -1;
    if (b === "general") return 1;
    return a.localeCompare(b);
  });

  for (const providerId of providerIds) {
    const fields = Array.isArray(providerFields[providerId]) ? providerFields[providerId] : [];
    const card = document.createElement("section");
    card.className = "card";

    const head = document.createElement("div");
    head.className = "provider-head";

    const title = document.createElement("h3");
    title.className = "provider-title";
    title.textContent = providerTitle(providerId);
    head.appendChild(title);

    const link = String(providerLinks[providerId] || "").trim();
    if (link) {
      const anchor = document.createElement("a");
      anchor.className = "provider-link";
      anchor.href = link;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = "Docs";
      head.appendChild(anchor);
    }

    card.appendChild(head);

    for (const key of fields) {
      const field = document.createElement("div");
      field.className = "field";

      const label = document.createElement("label");
      label.setAttribute("for", `field-${key}`);
      label.textContent = keyLabel(key);
      field.appendChild(label);

      const current = currentFieldValue(key);
      const secret = isSecretKey(key);
      const boolField = key.startsWith("ENABLE_");

      if (boolField) {
        const wrap = document.createElement("label");
        wrap.className = "toggle";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.id = `field-${key}`;
        input.dataset.setupKey = key;
        input.dataset.fieldType = "bool";
        input.checked = Boolean(current);
        wrap.appendChild(input);
        wrap.append(` Enabled (${key})`);
        field.appendChild(wrap);
      } else {
        const input = document.createElement("input");
        input.type = secret ? "password" : "text";
        input.id = `field-${key}`;
        input.dataset.setupKey = key;
        input.dataset.fieldType = secret ? "secret" : "text";
        input.autocomplete = "off";

        if (secret) {
          input.value = "";
          const present = secretFieldPresent(key);
          input.placeholder = present ? "(saved) enter new value to replace" : "not set";
          const masked = String(maskedFieldValue(key) || "").trim();
          if (present && masked) {
            const note = document.createElement("div");
            note.className = "mask-note";
            note.textContent = `Current: ${masked}`;
            field.appendChild(note);
          }
        } else {
          input.value = typeof current === "string" ? current : "";
        }

        field.appendChild(input);
      }

      card.appendChild(field);
    }

    elements.providersGrid.appendChild(card);
  }
}

function renderStravaStatus() {
  if (!elements.stravaStatus) return;
  const strava = state.payload?.strava || {};
  const clientConfigured = Boolean(strava.client_configured);
  const connected = Boolean(strava.connected);

  if (connected) {
    elements.stravaStatus.textContent = "Strava OAuth: connected";
  } else if (clientConfigured) {
    elements.stravaStatus.textContent = "Strava OAuth: ready to connect";
  } else {
    elements.stravaStatus.textContent = "Strava OAuth: add client ID + secret first";
  }
}

function collectSaveValues() {
  const updates = {};
  const nodes = elements.providersGrid
    ? elements.providersGrid.querySelectorAll("[data-setup-key]")
    : [];

  for (const node of nodes) {
    const key = String(node.dataset.setupKey || "").trim();
    const fieldType = String(node.dataset.fieldType || "text");
    if (!key) continue;

    if (fieldType === "bool") {
      updates[key] = Boolean(node.checked);
      continue;
    }
    if (fieldType === "secret") {
      const text = String(node.value || "").trim();
      if (!text) continue;
      updates[key] = text;
      continue;
    }
    updates[key] = String(node.value || "").trim();
  }

  return updates;
}

async function loadConfig() {
  setStatus("Loading setup config...");
  const res = await requestJSON("/setup/api/config");
  if (!res.ok) {
    setStatus(res.payload?.error || "Failed to load setup config.", "error");
    return false;
  }
  state.payload = res.payload;
  renderProviders();
  renderStravaStatus();
  setStatus("Setup config loaded.", "ok");
  return true;
}

async function saveConfig() {
  const values = collectSaveValues();
  setStatus("Saving setup values...");
  const res = await requestJSON("/setup/api/config", {
    method: "PUT",
    body: JSON.stringify({ values }),
  });
  if (!res.ok) {
    setStatus(res.payload?.error || "Save failed.", "error");
    return;
  }
  state.payload = res.payload;
  renderProviders();
  renderStravaStatus();
  setStatus("Setup values saved.", "ok");
  await refreshEnvSnippet();
}

async function refreshEnvSnippet() {
  const res = await requestJSON("/setup/api/env");
  if (!res.ok) {
    setStatus(res.payload?.error || "Failed to build env snippet.", "error");
    return;
  }
  if (elements.envSnippet) {
    elements.envSnippet.value = String(res.payload.env || "");
  }
}

async function startStravaOAuth() {
  setStatus("Starting Strava OAuth...");
  const res = await requestJSON("/setup/api/strava/oauth/start", {
    method: "POST",
    body: JSON.stringify({
      redirect_uri: `${window.location.origin}/setup/strava/callback`,
    }),
  });
  if (!res.ok) {
    setStatus(res.payload?.error || "Failed to start Strava OAuth.", "error");
    return;
  }
  const authorizeUrl = String(res.payload.authorize_url || "").trim();
  if (!authorizeUrl) {
    setStatus("OAuth authorize URL is missing.", "error");
    return;
  }
  window.location.assign(authorizeUrl);
}

async function disconnectStrava() {
  const ok = window.confirm("Disconnect Strava tokens saved by setup wizard?");
  if (!ok) return;
  setStatus("Disconnecting Strava tokens...");
  const res = await requestJSON("/setup/api/strava/disconnect", { method: "POST" });
  if (!res.ok) {
    setStatus(res.payload?.error || "Failed to disconnect Strava tokens.", "error");
    return;
  }
  await loadConfig();
  await refreshEnvSnippet();
  setStatus("Strava tokens disconnected.", "ok");
}

async function copyEnvSnippet() {
  const text = String(elements.envSnippet?.value || "");
  if (!text.trim()) {
    setStatus("No env snippet to copy.", "error");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    setStatus("Copied env snippet to clipboard.", "ok");
  } catch (_error) {
    setStatus("Clipboard copy failed. Copy manually from the text area.", "error");
  }
}

function applyQueryStatus() {
  const params = new URLSearchParams(window.location.search);
  const oauth = String(params.get("strava_oauth") || "").trim().toLowerCase();
  const reason = String(params.get("reason") || "").trim();
  if (!oauth) return;
  if (oauth === "connected") {
    setStatus("Strava OAuth connected successfully.", "ok");
  } else {
    const suffix = reason ? ` (${reason})` : "";
    setStatus(`Strava OAuth failed${suffix}.`, "error");
  }
  params.delete("strava_oauth");
  params.delete("reason");
  const next = params.toString();
  const cleanUrl = `${window.location.pathname}${next ? `?${next}` : ""}`;
  window.history.replaceState({}, "", cleanUrl);
}

function bindEvents() {
  elements.btnOpenEditor?.addEventListener("click", () => {
    window.location.assign("/editor");
  });
  elements.btnReload?.addEventListener("click", async () => {
    await loadConfig();
    await refreshEnvSnippet();
  });
  elements.btnSave?.addEventListener("click", saveConfig);
  elements.btnStravaConnect?.addEventListener("click", startStravaOAuth);
  elements.btnStravaDisconnect?.addEventListener("click", disconnectStrava);
  elements.btnRefreshEnv?.addEventListener("click", refreshEnvSnippet);
  elements.btnCopyEnv?.addEventListener("click", copyEnvSnippet);
}

async function init() {
  bindEvents();
  await loadConfig();
  await refreshEnvSnippet();
  applyQueryStatus();
}

init();
