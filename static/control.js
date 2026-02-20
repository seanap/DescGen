(function () {
  "use strict";

  const tableBody = document.getElementById("operationsTableBody");
  const filterInput = document.getElementById("operationFilter");
  const clearStatusesButton = document.getElementById("clearStatuses");

  if (!tableBody) {
    return;
  }

  function withQuery(path, params) {
    const queryEntries = Object.entries(params || {}).filter(([, value]) => {
      if (value === undefined || value === null) return false;
      return String(value).trim().length > 0;
    });
    if (!queryEntries.length) {
      return path;
    }
    const query = new URLSearchParams();
    for (const [key, value] of queryEntries) {
      query.set(key, String(value).trim());
    }
    return `${path}?${query.toString()}`;
  }

  function ensureIntString(value, fieldName) {
    const text = String(value || "").trim();
    if (!text) {
      throw new Error(`${fieldName} is required.`);
    }
    if (!/^\d+$/.test(text)) {
      throw new Error(`${fieldName} must be an integer.`);
    }
    return text;
  }

  const operations = [
    {
      id: "health",
      method: "GET",
      command: "/health",
      description: "Liveness probe for the API process.",
      input: null,
      buildRequest: () => ({ url: "/health" }),
    },
    {
      id: "ready",
      method: "GET",
      command: "/ready",
      description: "Readiness checks including worker heartbeat.",
      input: null,
      buildRequest: () => ({ url: "/ready" }),
    },
    {
      id: "latest",
      method: "GET",
      command: "/latest",
      description: "Fetch latest generated activity payload.",
      input: null,
      buildRequest: () => ({ url: "/latest" }),
    },
    {
      id: "service_metrics",
      method: "GET",
      command: "/service-metrics",
      description: "Inspect provider call metrics from the latest cycle.",
      input: null,
      buildRequest: () => ({ url: "/service-metrics" }),
    },
    {
      id: "dashboard_data",
      method: "GET",
      command: "/dashboard/data.json",
      description: "Read cached dashboard payload.",
      input: null,
      buildRequest: () => ({ url: "/dashboard/data.json" }),
    },
    {
      id: "dashboard_data_force",
      method: "GET",
      command: "/dashboard/data.json?force=true",
      description: "Force dashboard payload rebuild immediately.",
      input: null,
      buildRequest: () => ({ url: "/dashboard/data.json?force=true" }),
    },
    {
      id: "rerun_latest",
      method: "POST",
      command: "/rerun/latest",
      description: "Rerun processing for the most recent activity.",
      input: null,
      buildRequest: () => ({ url: "/rerun/latest" }),
    },
    {
      id: "rerun_activity",
      method: "POST",
      command: "/rerun/activity/{activity_id}",
      description: "Rerun one specific Strava activity ID.",
      input: {
        placeholder: "activity_id e.g. 17455368360",
        required: true,
      },
      buildRequest: (value) => {
        const activityId = ensureIntString(value, "activity_id");
        return { url: `/rerun/activity/${encodeURIComponent(activityId)}` };
      },
    },
    {
      id: "rerun_optional",
      method: "POST",
      command: "/rerun",
      description: "Rerun latest or pass optional JSON activity_id.",
      input: {
        placeholder: "optional activity_id",
        required: false,
      },
      buildRequest: (value) => {
        const text = String(value || "").trim();
        if (!text) {
          return { url: "/rerun", body: {} };
        }
        const activityId = ensureIntString(text, "activity_id");
        return { url: "/rerun", body: { activity_id: Number(activityId) } };
      },
    },
    {
      id: "setup_config",
      method: "GET",
      command: "/setup/api/config",
      description: "View setup configuration and provider metadata.",
      input: null,
      buildRequest: () => ({ url: "/setup/api/config" }),
    },
    {
      id: "setup_env",
      method: "GET",
      command: "/setup/api/env",
      description: "View generated env snippet.",
      input: null,
      buildRequest: () => ({ url: "/setup/api/env" }),
    },
    {
      id: "setup_strava_status",
      method: "GET",
      command: "/setup/api/strava/status",
      description: "Check Strava OAuth/token connection status.",
      input: null,
      buildRequest: () => ({ url: "/setup/api/strava/status" }),
    },
    {
      id: "setup_strava_oauth_start",
      method: "POST",
      command: "/setup/api/strava/oauth/start",
      description: "Create Strava authorize URL. Optional redirect URI override.",
      input: {
        placeholder: "optional redirect_uri",
        required: false,
      },
      buildRequest: (value) => {
        const redirectUri = String(value || "").trim();
        if (!redirectUri) {
          return { url: "/setup/api/strava/oauth/start", body: {} };
        }
        return { url: "/setup/api/strava/oauth/start", body: { redirect_uri: redirectUri } };
      },
    },
    {
      id: "setup_strava_disconnect",
      method: "POST",
      command: "/setup/api/strava/disconnect",
      description: "Clear saved Strava access/refresh tokens.",
      input: null,
      buildRequest: () => ({ url: "/setup/api/strava/disconnect" }),
    },
    {
      id: "editor_profiles",
      method: "GET",
      command: "/editor/profiles",
      description: "List profile settings and current working profile.",
      input: null,
      buildRequest: () => ({ url: "/editor/profiles" }),
    },
    {
      id: "editor_set_working_profile",
      method: "POST",
      command: "/editor/profiles/working",
      description: "Set the active profile in editor state.",
      input: {
        placeholder: "profile_id e.g. default",
        required: true,
      },
      buildRequest: (value) => {
        const profileId = String(value || "").trim();
        if (!profileId) {
          throw new Error("profile_id is required.");
        }
        return { url: "/editor/profiles/working", body: { profile_id: profileId } };
      },
    },
    {
      id: "editor_template",
      method: "GET",
      command: "/editor/template?profile_id={profile_id}",
      description: "Read active template (optional profile_id query).",
      input: {
        placeholder: "optional profile_id",
        required: false,
      },
      buildRequest: (value) => ({
        url: withQuery("/editor/template", { profile_id: value }),
      }),
    },
    {
      id: "editor_template_default",
      method: "GET",
      command: "/editor/template/default",
      description: "Read shipped default template.",
      input: null,
      buildRequest: () => ({ url: "/editor/template/default" }),
    },
    {
      id: "editor_template_versions",
      method: "GET",
      command: "/editor/template/versions?profile_id={profile_id}&limit=30",
      description: "List template version history for a profile.",
      input: {
        placeholder: "optional profile_id",
        required: false,
      },
      buildRequest: (value) => ({
        url: withQuery("/editor/template/versions", { profile_id: value, limit: 30 }),
      }),
    },
    {
      id: "editor_fixtures",
      method: "GET",
      command: "/editor/fixtures",
      description: "List sample fixture names.",
      input: null,
      buildRequest: () => ({ url: "/editor/fixtures" }),
    },
    {
      id: "editor_snippets",
      method: "GET",
      command: "/editor/snippets",
      description: "Fetch editor snippet catalog and context modes.",
      input: null,
      buildRequest: () => ({ url: "/editor/snippets" }),
    },
    {
      id: "editor_starters",
      method: "GET",
      command: "/editor/starter-templates",
      description: "List starter templates.",
      input: null,
      buildRequest: () => ({ url: "/editor/starter-templates" }),
    },
    {
      id: "editor_context_sample",
      method: "GET",
      command: "/editor/context/sample?fixture={fixture}",
      description: "Load sample context by fixture name.",
      input: {
        placeholder: "optional fixture name",
        required: false,
      },
      buildRequest: (value) => ({
        url: withQuery("/editor/context/sample", { fixture: value }),
      }),
    },
    {
      id: "editor_schema",
      method: "GET",
      command: "/editor/schema?context_mode={mode}",
      description: "Build schema for latest/sample context mode.",
      input: {
        placeholder: "optional mode: latest|sample|latest_or_sample|fixture",
        required: false,
      },
      buildRequest: (value) => ({
        url: withQuery("/editor/schema", { context_mode: value }),
      }),
    },
    {
      id: "editor_catalog_fixture",
      method: "GET",
      command: "/editor/catalog?context_mode=fixture&fixture_name={fixture}",
      description: "Build full catalog from fixture context.",
      input: {
        placeholder: "optional fixture name (default)",
        required: false,
      },
      buildRequest: (value) => ({
        url: withQuery("/editor/catalog", { context_mode: "fixture", fixture_name: value || "default" }),
      }),
    },
    {
      id: "editor_template_export",
      method: "GET",
      command: "/editor/template/export?profile_id={profile_id}",
      description: "Export active template bundle.",
      input: {
        placeholder: "optional profile_id",
        required: false,
      },
      buildRequest: (value) => ({
        url: withQuery("/editor/template/export", { profile_id: value }),
      }),
    },
    {
      id: "repo_templates",
      method: "GET",
      command: "/editor/repository/templates",
      description: "List saved repository templates.",
      input: null,
      buildRequest: () => ({ url: "/editor/repository/templates" }),
    },
    {
      id: "repo_template_get",
      method: "GET",
      command: "/editor/repository/template/{template_id}",
      description: "Fetch one repository template record.",
      input: {
        placeholder: "template_id",
        required: true,
      },
      buildRequest: (value) => {
        const templateId = String(value || "").trim();
        if (!templateId) {
          throw new Error("template_id is required.");
        }
        return { url: `/editor/repository/template/${encodeURIComponent(templateId)}` };
      },
    },
    {
      id: "repo_template_load",
      method: "POST",
      command: "/editor/repository/template/{template_id}/load",
      description: "Load repository template payload for editor use.",
      input: {
        placeholder: "template_id",
        required: true,
      },
      buildRequest: (value) => {
        const templateId = String(value || "").trim();
        if (!templateId) {
          throw new Error("template_id is required.");
        }
        return { url: `/editor/repository/template/${encodeURIComponent(templateId)}/load` };
      },
    },
    {
      id: "repo_template_export",
      method: "GET",
      command: "/editor/repository/template/{template_id}/export",
      description: "Export one repository template bundle.",
      input: {
        placeholder: "template_id",
        required: true,
      },
      buildRequest: (value) => {
        const templateId = String(value || "").trim();
        if (!templateId) {
          throw new Error("template_id is required.");
        }
        return { url: `/editor/repository/template/${encodeURIComponent(templateId)}/export` };
      },
    },
  ];

  const rowRefs = new Map();

  function getMethodBadgeClass(method) {
    return method === "POST" ? "method-post" : "method-get";
  }

  function setRowStatus(rowRef, state, message) {
    rowRef.statusDot.classList.remove("running", "success", "error");
    if (state === "running") {
      rowRef.statusDot.classList.add("running");
    } else if (state === "success") {
      rowRef.statusDot.classList.add("success");
    } else if (state === "error") {
      rowRef.statusDot.classList.add("error");
    }
    rowRef.statusText.textContent = message || "";
  }

  function summarizeResponse(response, payload, text) {
    const statusCode = String(response.status);
    if (payload && typeof payload === "object") {
      if (!response.ok) {
        const validationErrors = payload.validation && Array.isArray(payload.validation.errors)
          ? payload.validation.errors
          : [];
        const errorText = String(
          payload.error || payload.message || validationErrors.join("; ") || response.statusText || "request failed"
        );
        return `${statusCode} ${errorText}`.trim();
      }

      const parts = [statusCode];
      if (typeof payload.status === "string" && payload.status.trim()) {
        parts.push(payload.status.trim());
      }
      const resultStatus = payload.result && typeof payload.result.status === "string"
        ? payload.result.status
        : "";
      if (resultStatus) {
        parts.push(`result:${resultStatus}`);
      }
      if (typeof payload.dashboard_refresh === "string" && payload.dashboard_refresh.trim()) {
        parts.push(`dashboard:${payload.dashboard_refresh}`);
      }
      if (typeof payload.count === "number") {
        parts.push(`count:${payload.count}`);
      }
      return parts.join(" | ");
    }

    const compact = String(text || response.statusText || "")
      .replace(/\s+/g, " ")
      .trim();
    if (!compact) {
      return `${statusCode} ${response.statusText}`.trim();
    }
    return `${statusCode} ${compact.slice(0, 170)}`.trim();
  }

  async function runOperation(op, rowRef) {
    const inputValue = rowRef.input ? rowRef.input.value.trim() : "";

    let requestSpec;
    try {
      requestSpec = op.buildRequest(inputValue);
    } catch (error) {
      setRowStatus(rowRef, "error", String(error && error.message ? error.message : error));
      return;
    }

    rowRef.button.disabled = true;
    setRowStatus(rowRef, "running", "Running...");

    const options = {
      method: op.method,
      headers: {},
    };

    if (requestSpec && requestSpec.body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(requestSpec.body);
    }

    try {
      const response = await fetch(requestSpec.url, options);
      const responseText = await response.text();

      let payload = null;
      try {
        payload = responseText ? JSON.parse(responseText) : null;
      } catch (_error) {
        payload = null;
      }

      const summary = summarizeResponse(response, payload, responseText);
      setRowStatus(rowRef, response.ok ? "success" : "error", summary);
    } catch (error) {
      setRowStatus(rowRef, "error", `Network error: ${String(error && error.message ? error.message : error)}`);
    } finally {
      rowRef.button.disabled = false;
    }
  }

  function renderOperations() {
    for (const op of operations) {
      const row = document.createElement("tr");

      const runCell = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ops-action";
      button.textContent = "Run";
      runCell.appendChild(button);
      row.appendChild(runCell);

      const methodCell = document.createElement("td");
      const methodBadge = document.createElement("span");
      methodBadge.className = `method-badge ${getMethodBadgeClass(op.method)}`;
      methodBadge.textContent = op.method;
      methodCell.appendChild(methodBadge);
      row.appendChild(methodCell);

      const commandCell = document.createElement("td");
      const commandText = document.createElement("code");
      commandText.className = "command";
      commandText.textContent = op.command;
      commandCell.appendChild(commandText);
      row.appendChild(commandCell);

      const inputCell = document.createElement("td");
      let input = null;
      if (op.input) {
        const inputWrap = document.createElement("div");
        inputWrap.className = "input-wrap";
        input = document.createElement("input");
        input.type = "text";
        input.className = "dg-focusable";
        input.placeholder = op.input.placeholder || "";
        input.required = Boolean(op.input.required);
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            button.click();
          }
        });
        inputWrap.appendChild(input);
        inputCell.appendChild(inputWrap);
      } else {
        const none = document.createElement("span");
        none.className = "input-none";
        none.textContent = "-";
        inputCell.appendChild(none);
      }
      row.appendChild(inputCell);

      const descriptionCell = document.createElement("td");
      descriptionCell.className = "description";
      descriptionCell.textContent = op.description;
      row.appendChild(descriptionCell);

      const statusCell = document.createElement("td");
      statusCell.className = "status-cell";
      const statusWrap = document.createElement("div");
      statusWrap.className = "status-wrap";
      const statusDot = document.createElement("span");
      statusDot.className = "status-dot";
      const statusText = document.createElement("span");
      statusText.className = "status-text";
      statusText.textContent = "Not run yet.";
      statusWrap.appendChild(statusDot);
      statusWrap.appendChild(statusText);
      statusCell.appendChild(statusWrap);
      row.appendChild(statusCell);

      button.addEventListener("click", () => runOperation(op, rowRefs.get(op.id)));

      const searchSource = [op.method, op.command, op.description].join(" ").toLowerCase();
      row.dataset.search = searchSource;

      tableBody.appendChild(row);
      rowRefs.set(op.id, {
        row,
        button,
        input,
        statusDot,
        statusText,
      });
    }
  }

  function applyFilter() {
    const query = String(filterInput && filterInput.value ? filterInput.value : "")
      .trim()
      .toLowerCase();

    for (const rowRef of rowRefs.values()) {
      const haystack = rowRef.row.dataset.search || "";
      const visible = !query || haystack.includes(query);
      rowRef.row.classList.toggle("is-hidden", !visible);
    }
  }

  function clearStatuses() {
    for (const rowRef of rowRefs.values()) {
      setRowStatus(rowRef, "idle", "Not run yet.");
    }
  }

  renderOperations();

  if (filterInput) {
    filterInput.addEventListener("input", applyFilter);
  }

  if (clearStatusesButton) {
    clearStatusesButton.addEventListener("click", clearStatuses);
  }
})();
