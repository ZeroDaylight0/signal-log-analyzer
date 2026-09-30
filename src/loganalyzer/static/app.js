import { forgetSettings, hasSavedSettings, saveSettings, unlockSettings } from "./settings.js";

const form = document.querySelector("#upload-form");
const input = document.querySelector("#log-file");
const dropZone = document.querySelector("#drop-zone");
const selected = document.querySelector("#selected-file");
const selectedName = document.querySelector("#selected-name");
const selectedSize = document.querySelector("#selected-size");
const statusBox = document.querySelector("#status");
const results = document.querySelector("#results");
const analyzeButton = document.querySelector("#analyze-button");
const buttonLabel = document.querySelector("#button-label");
const providerForm = document.querySelector("#provider-form");
const providerLocked = document.querySelector("#provider-locked");
const providerActive = document.querySelector("#provider-active");
const providerSelect = document.querySelector("#provider");
const modelInput = document.querySelector("#model");
const keyInput = document.querySelector("#api-key");
const baseUrlField = document.querySelector("#base-url-field");
const baseUrlInput = document.querySelector("#base-url");
const encryptionPassword = document.querySelector("#encryption-password");
const settingsStatus = document.querySelector("#settings-status");
const modelDefaults = {
  gemini: ["gemini-2.5-flash", "https://aistudio.google.com/app/apikey"],
  openai: ["gpt-4.1-mini", "https://platform.openai.com/api-keys"],
  anthropic: ["claude-haiku-4-5-20251001", "https://console.anthropic.com/settings/keys"],
  xai: ["grok-4.7", "https://console.x.ai/"],
  "openai-compatible": ["your-model-name", ""],
};
const providerNames = {
  gemini: "Google Gemini",
  openai: "OpenAI · ChatGPT",
  anthropic: "Anthropic · Claude",
  xai: "xAI · Grok",
  "openai-compatible": "OpenAI-compatible API",
};
let chosenFile = null;
let activeSettings = null;
let previousProvider = providerSelect.value;

function formatSize(bytes) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function chooseFile(file) {
  if (!file) return;
  chosenFile = file;
  selectedName.textContent = file.name;
  selectedSize.textContent = formatSize(file.size);
  selected.hidden = false;
  dropZone.hidden = true;
  analyzeButton.disabled = !activeSettings;
  hideStatus();
}

function clearFile() {
  chosenFile = null;
  input.value = "";
  selected.hidden = true;
  dropZone.hidden = false;
  analyzeButton.disabled = true;
}

function showStatus(element, message, loading = false, success = false) {
  element.textContent = message;
  element.classList.toggle("loading", loading);
  element.classList.toggle("success", success);
  element.hidden = false;
}

function hideStatus() {
  statusBox.hidden = true;
  statusBox.classList.remove("loading");
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function addList(parent, title, values, ordered = false) {
  if (!values?.length) return;
  const card = node("article", "result-card");
  card.append(node("h3", "", title));
  const list = document.createElement(ordered ? "ol" : "ul");
  for (const item of values) {
    const li = node("li", "", typeof item === "string" ? item : item.event);
    if (typeof item === "object" && item.line) li.textContent = `Строка ${item.line} · ${item.event}`;
    list.append(li);
  }
  card.append(list);
  parent.append(card);
}

function renderResult(result) {
  results.replaceChildren();
  const severity = (result.overall_severity || "info").toLowerCase();
  const head = node("div", "result-head");
  const heading = document.createElement("div");
  heading.append(node("div", "result-kicker", "АНАЛИЗ ЗАВЕРШЁН"));
  heading.append(node("h2", "result-title", result.filename));
  heading.append(node("div", "result-meta", `Строк проверено: ${result.log_lines}${result.truncated ? " · часть лога пропущена" : ""}`));
  const severityNames = { critical: "КРИТИЧНО", high: "ВЫСОКИЙ", medium: "СРЕДНИЙ", low: "НИЗКИЙ", info: "ИНФО" };
  head.append(heading, node("span", `severity-pill severity-${severity}`, severityNames[severity] || severity.toUpperCase()));
  results.append(head, node("p", "summary", result.summary));

  const grid = node("div", "result-grid");
  if (result.incidents?.length) {
    const card = node("article", "result-card full");
    card.append(node("h3", "", `НАХОДКИ · ${result.incidents.length}`));
    for (const incident of result.incidents) {
      const item = node("div", "incident");
      const title = node("div", "incident-title", incident.title);
      const incidentSeverity = (incident.severity || "info").toLowerCase();
      title.append(node("span", `severity-pill severity-${incidentSeverity}`, severityNames[incidentSeverity] || incidentSeverity.toUpperCase()));
      const confidence = { high: "высокая уверенность", medium: "средняя уверенность", low: "низкая уверенность" };
      item.append(title, node("p", "", `${incident.explanation} · ${confidence[incident.confidence] || incident.confidence}`));
      for (const evidence of incident.evidence || []) {
        item.append(node("div", "evidence", `${evidence.line ? `Строка ${evidence.line} · ` : ""}${evidence.text}`));
      }
      card.append(item);
    }
    grid.append(card);
  }
  addList(grid, "ХРОНОЛОГИЯ", result.timeline);
  addList(grid, "СЛЕДУЮЩИЕ ШАГИ", result.recommendations, true);
  addList(grid, "ОГОВОРКИ", result.caveats);
  results.append(grid);

  const actions = node("div", "result-actions");
  const download = node("button", "secondary-button", "Скачать отчёт JSON ↓");
  download.type = "button";
  download.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(result.filename || "log").replace(/[^a-zA-Z0-9._-]/g, "_")}.analysis.json`;
    link.click();
    URL.revokeObjectURL(url);
  });
  actions.append(download);
  results.append(actions);
  results.hidden = false;
}

function showLocked() {
  activeSettings = null;
  providerActive.hidden = true;
  providerForm.hidden = true;
  providerLocked.hidden = false;
  document.querySelector("#unlock-password").value = "";
  analyzeButton.disabled = true;
}

function showEditor(settings = null) {
  providerActive.hidden = true;
  providerLocked.hidden = true;
  providerForm.hidden = false;
  document.querySelector("#cancel-settings").hidden = !settings;
  if (settings) {
    providerSelect.value = settings.provider;
    modelInput.value = settings.model;
    keyInput.value = settings.api_key;
    baseUrlInput.value = settings.base_url || "";
    encryptionPassword.value = "";
    previousProvider = settings.provider;
  }
  updateProviderFields();
}

function showActive(settings) {
  activeSettings = settings;
  providerForm.hidden = true;
  providerLocked.hidden = true;
  providerActive.hidden = false;
  document.querySelector("#provider-badge").textContent = settings.provider.toUpperCase();
  document.querySelector("#provider-summary-text").textContent = `${providerNames[settings.provider]} · ${settings.model}`;
  keyInput.value = "";
  encryptionPassword.value = "";
  analyzeButton.disabled = !chosenFile;
}

function updateProviderFields() {
  const provider = providerSelect.value;
  baseUrlField.hidden = provider !== "openai-compatible";
  baseUrlInput.required = provider === "openai-compatible";
  modelInput.placeholder = `Например, ${modelDefaults[provider][0]}`;
  const providerConsole = document.querySelector("#provider-console");
  providerConsole.hidden = !modelDefaults[provider][1];
  if (modelDefaults[provider][1]) providerConsole.href = modelDefaults[provider][1];
  if (!modelInput.value) {
    modelInput.value = modelDefaults[provider][0];
  } else if (provider !== previousProvider && modelInput.value === modelDefaults[previousProvider][0]) {
    modelInput.value = modelDefaults[provider][0];
  }
  previousProvider = provider;
}

function settingsFromForm() {
  const settings = {
    provider: providerSelect.value,
    model: modelInput.value.trim(),
    api_key: keyInput.value.trim(),
  };
  if (settings.provider === "openai-compatible") settings.base_url = baseUrlInput.value.trim();
  return settings;
}

providerSelect.addEventListener("change", updateProviderFields);
document.querySelector("#edit-settings").addEventListener("click", () => showEditor(activeSettings));
document.querySelector("#lock-settings").addEventListener("click", showLocked);
document.querySelector("#forget-settings").addEventListener("click", () => {
  if (!window.confirm("Удалить зашифрованные настройки с этого браузера?")) return;
  forgetSettings();
  activeSettings = null;
  providerActive.hidden = true;
  providerLocked.hidden = true;
  showEditor();
  showStatus(settingsStatus, "Сохранённые настройки удалены.", false, true);
});
document.querySelector("#cancel-settings").addEventListener("click", () => showActive(activeSettings));

document.querySelector("#unlock-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const password = document.querySelector("#unlock-password");
  try {
    const settings = await unlockSettings(password.value);
    showActive(settings);
    settingsStatus.hidden = true;
  } catch (error) {
    showStatus(settingsStatus, error.message || "Не удалось открыть настройки.");
  } finally {
    password.value = "";
  }
});

providerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const settings = settingsFromForm();
  const password = encryptionPassword.value;
  if (!settings.api_key) {
    showStatus(settingsStatus, "Введите API-ключ выбранного провайдера.");
    return;
  }
  if (settings.provider === "openai-compatible" && !settings.base_url) {
    showStatus(settingsStatus, "Укажите API Base URL для выбранного сервиса.");
    return;
  }
  try {
    await saveSettings(settings, password);
    showStatus(settingsStatus, "Настройки зашифрованы и сохранены в этом браузере.", false, true);
    showActive(settings);
  } catch (error) {
    showStatus(settingsStatus, error.message || "Не удалось сохранить настройки.");
  }
});

input.addEventListener("change", () => chooseFile(input.files?.[0]));
document.querySelector("#remove-file").addEventListener("click", clearFile);
dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragging"));
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
  chooseFile(event.dataTransfer.files?.[0]);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!chosenFile || !activeSettings) return;
  if (chosenFile.size > 1_048_576) {
    showStatus(statusBox, "Файл больше 1 МБ. Выберите файл поменьше.");
    return;
  }

  const body = new FormData();
  body.append("file", chosenFile);
  body.append("settings", JSON.stringify(activeSettings));
  analyzeButton.disabled = true;
  buttonLabel.textContent = "Анализируем…";
  showStatus(statusBox, `Файл отправляется в ${providerNames[activeSettings.provider]}.`, true);
  results.hidden = true;
  try {
    const response = await fetch("/api/analyze", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Не удалось выполнить анализ.");
    renderResult(payload);
    hideStatus();
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showStatus(statusBox, error.message || "Не удалось завершить анализ.");
  } finally {
    analyzeButton.disabled = !chosenFile || !activeSettings;
    buttonLabel.textContent = "Разобрать лог";
  }
});

if (!globalThis.crypto?.subtle) {
  showStatus(settingsStatus, "Этот браузер не поддерживает шифрование настроек. Откройте приложение через localhost в современном браузере.");
  providerForm.hidden = true;
} else if (hasSavedSettings()) {
  showLocked();
} else {
  showEditor();
}
