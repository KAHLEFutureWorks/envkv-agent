import { loadSettings } from "./api";

const form = document.querySelector<HTMLFormElement>("#settings-form")!;
const urlInput = document.querySelector<HTMLInputElement>("#api-url")!;
const keyInput = document.querySelector<HTMLInputElement>("#api-key")!;
const feedback = document.querySelector<HTMLElement>("#settings-feedback")!;

const note = document.querySelector<HTMLElement>("#managed-note")!;
const saveButton = form.querySelector<HTMLButtonElement>('button[type="submit"]')!;

void loadSettings().then((settings) => {
  urlInput.value = settings.apiUrl;
  keyInput.value = settings.apiKey;

  // Werte aus der Unternehmensrichtlinie gewinnen beim Lesen immer. Sie hier
  // bearbeitbar zu lassen, würde ein Speichern vortäuschen, das folgenlos bleibt.
  if (settings.managedUrl) {
    urlInput.readOnly = true;
  }
  if (settings.managedKey) {
    keyInput.readOnly = true;
  }
  if (settings.managedUrl || settings.managedKey) {
    note.textContent = "Die Verbindung wird von der IT über eine Unternehmensrichtlinie vorgegeben "
      + "und muss hier nicht eingetragen werden. Vorgegebene Felder lassen sich nicht ändern.";
    note.classList.remove("hidden");
  }
  if (settings.managedUrl && settings.managedKey) {
    saveButton.disabled = true;
    saveButton.textContent = "Durch Unternehmensrichtlinie vorgegeben";
  }
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
