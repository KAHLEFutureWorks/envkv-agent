import { loadSettings } from "./api";

const form = document.querySelector<HTMLFormElement>("#settings-form")!;
const urlInput = document.querySelector<HTMLInputElement>("#api-url")!;
const keyInput = document.querySelector<HTMLInputElement>("#api-key")!;
const feedback = document.querySelector<HTMLElement>("#settings-feedback")!;

void loadSettings().then((settings) => {
  urlInput.value = settings.apiUrl;
  keyInput.value = settings.apiKey;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const apiUrl = urlInput.value.trim().replace(/\/$/, "");
  const isLocal = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(apiUrl);
  if (!apiUrl.startsWith("https://") && !isLocal) {
    feedback.textContent = "Im Betrieb ist ausschließlich eine HTTPS-Adresse zulässig.";
    feedback.className = "copy-feedback error-text";
    return;
  }
  await chrome.storage.local.set({ apiUrl, apiKey: keyInput.value.trim() });
  feedback.textContent = "✓ Verbindung gespeichert";
  feedback.className = "copy-feedback success-text";
});
