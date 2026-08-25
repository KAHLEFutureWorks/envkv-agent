// Die Druckansicht ist eine eigene Seite der Erweiterung. Als Blob geöffnete
// Dokumente erben die Content Security Policy der Erweiterung; Manifest V3
// unterbindet dort jedes onclick-Attribut, weshalb ein eingebetteter Knopf
// wirkungslos bliebe. Dieses Skript wird als eigene Datei geladen und darf
// deshalb einen Ereignisbehandler setzen.
const STORAGE_KEY = "printSheet";

async function render(): Promise<void> {
  const sheet = document.querySelector<HTMLElement>("#sheet")!;
  const hint = document.querySelector<HTMLElement>("#print-hint")!;
  const stored = await chrome.storage.session.get(STORAGE_KEY);
  const html = stored[STORAGE_KEY];
  if (typeof html !== "string" || !html) {
    hint.textContent = "Kein Hinweis gefunden. Bitte im Side Panel erneut auf „Druckansicht öffnen“.";
    return;
  }
  sheet.innerHTML = html;
  await chrome.storage.session.remove(STORAGE_KEY);
}

document.querySelector<HTMLButtonElement>("#print-button")!
  .addEventListener("click", () => window.print());

void render();
