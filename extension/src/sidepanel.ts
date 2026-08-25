import { ComplianceApiError, fetchCompliance, fetchDataSheetSnippet, fetchModelRange } from "./api";
import type { ComplianceResult, ModelRangeResult, UsageContext } from "./types";

const byId = <T extends HTMLElement>(id: string): T => document.querySelector<T>(`#${id}`)!;
const form = byId<HTMLFormElement>("vehicle-form");
const input = byId<HTMLTextAreaElement>("vehicle-name");
const submit = byId<HTMLButtonElement>("submit-button");
const usageContext = byId<HTMLSelectElement>("usage-context");
const message = byId<HTMLElement>("message");
const resultSection = byId<HTMLElement>("result");
const rangeSection = byId<HTMLElement>("range-result");
let outputText = "";
let rangeOutputText = "";
let selectedTypeId: string | undefined;

async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch {
    // Nach einem Netzabruf ist die Nutzeraktivierung abgelaufen; die
    // Zwischenablage-API verweigert dann den Zugriff. Der folgende Weg
    // funktioniert auch dann und ist durch die Berechtigung clipboardWrite
    // abgedeckt.
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.top = "0";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  area.setSelectionRange(0, text.length);
  const copied = document.execCommand("copy");
  area.remove();
  if (!copied) {
    throw new Error("Der Text konnte nicht in die Zwischenablage gelegt werden.");
  }
}

function decimal(value: number, digits = 1): string {
  return new Intl.NumberFormat("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

function showMessage(text: string, kind: "loading" | "error"): void {
  message.textContent = text;
  message.className = `message ${kind}`;
  resultSection.classList.add("hidden");
  rangeSection.classList.add("hidden");
}

function showCandidates(error: ComplianceApiError): void {
  showMessage(error.message, "error");
  const context = usageContext.value as UsageContext;
  if (context === "advertising" || context === "social_media") {
    const rangeIntro = document.createElement("p");
    rangeIntro.textContent = "Für Werbung mit dem ganzen Modell:";
    message.appendChild(rangeIntro);
    const rangeButton = document.createElement("button");
    rangeButton.type = "button";
    rangeButton.className = "candidate-button";
    rangeButton.textContent = "Spanne über alle Varianten ausgeben";
    rangeButton.addEventListener("click", async () => {
      submit.disabled = true;
      showMessage("Alle Varianten des Modells werden geprüft …", "loading");
      try {
        showRange(await fetchModelRange(input.value.trim(), context));
      } catch (rangeError) {
        if (rangeError instanceof ComplianceApiError && rangeError.candidates.length) {
          showUnresolved(rangeError);
        } else {
          showMessage(rangeError instanceof Error ? rangeError.message : "Die Modellspanne konnte nicht erstellt werden.", "error");
        }
      } finally {
        submit.disabled = false;
      }
    });
    message.appendChild(rangeButton);
  }
  const intro = document.createElement("p");
  intro.textContent = "Oder ein konkretes Fahrzeug auswählen:";
  message.appendChild(intro);
  const list = document.createElement("div");
  list.className = "candidate-list";
  list.style.maxHeight = "430px";
  list.style.overflowY = "auto";
  for (const candidate of error.candidates) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "candidate-button";
    button.textContent = `${candidate.name}${candidate.model_year ? ` · MJ ${candidate.model_year}` : ""}`;
    button.addEventListener("click", async () => {
      submit.disabled = true;
      showMessage("Ausgewähltes Fahrzeug wird geprüft …", "loading");
      try {
        selectedTypeId = candidate.type_id;
        showResult(await fetchCompliance(input.value.trim(), usageContext.value as UsageContext, candidate.type_id));
      } catch (selectionError) {
        showMessage(selectionError instanceof Error ? selectionError.message : "Das Fahrzeug konnte nicht geprüft werden.", "error");
      } finally {
        submit.disabled = false;
      }
    });
    list.appendChild(button);
  }
  message.appendChild(list);
}

function showUnresolved(error: ComplianceApiError): void {
  showMessage(error.message, "error");
  const intro = document.createElement("p");
  intro.textContent = `Nicht bestätigte Varianten (${error.candidates.length}):`;
  message.appendChild(intro);
  const list = document.createElement("div");
  list.className = "candidate-list";
  list.style.maxHeight = "430px";
  list.style.overflowY = "auto";
  for (const candidate of error.candidates) {
    const item = document.createElement("p");
    item.className = "legal-note";
    item.textContent = candidate.reason ? `${candidate.name} — ${candidate.reason}` : candidate.name;
    list.appendChild(item);
  }
  message.appendChild(list);
}

const POWERTRAIN_LABELS: Record<string, string> = {
  battery_electric: "Rein elektrisch", petrol: "Benzin", diesel: "Diesel",
  hybrid: "Hybrid ohne externe Aufladung", plug_in_hybrid: "Plug-in-Hybrid",
};

function showRange(data: ModelRangeResult): void {
  message.classList.add("hidden");
  resultSection.classList.add("hidden");
  rangeSection.classList.remove("hidden");
  rangeOutputText = data.output_text;
  byId("range-title").textContent = `${data.brand} ${data.model_family}`;
  byId("range-meta").textContent = data.groups
    .map((group) => `${POWERTRAIN_LABELS[group.powertrain] ?? group.powertrain}: ${group.variant_count} · CO₂ ${
      group.co2_class_best === group.co2_class_worst
        ? group.co2_class_best
        : `${group.co2_class_best}–${group.co2_class_worst}`}`)
    .join("  |  ");
  byId("range-output").textContent = data.output_text;
  byId("range-provider").textContent = data.source.provider;
  byId("range-types").textContent = String(data.variant_count);
  byId("range-years").textContent = data.source.model_years.join(", ");
  byId("range-time").textContent = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.source.retrieved_at));
}

function showResult(data: ComplianceResult): void {
  message.classList.add("hidden");
  rangeSection.classList.add("hidden");
  resultSection.classList.remove("hidden");
  const scopeNotice = byId<HTMLElement>("scope-notice");
  scopeNotice.textContent = data.notice || "";
  scopeNotice.classList.toggle("hidden", !data.notice);
  byId("vehicle-title").textContent = `${data.vehicle.brand} ${data.vehicle.model} ${data.vehicle.trim}`;
  const ps = data.vehicle.power_ps === null ? "" : ` (${data.vehicle.power_ps} PS)`;
  const battery = data.vehicle.battery_kwh === null ? "" : ` · ${data.vehicle.battery_kwh} kWh`;
  byId("vehicle-meta").textContent = `${data.vehicle.power_kw} kW${ps}${battery} · MJ ${data.vehicle.model_year}`;
  const electric = data.consumption.combined_kwh_100km;
  const fuel = data.consumption.combined_l_100km;
  byId("consumption-label").textContent = data.powertrain === "plug_in_hybrid" ? "Verbrauch gewichtet" : "Verbrauch";
  byId("consumption").textContent = electric !== null && fuel !== null
    ? `${decimal(fuel)} l + ${decimal(electric)} kWh/100 km`
    : electric !== null ? `${decimal(electric)} kWh/100 km`
    : `${decimal(fuel ?? 0)} l/100 km`;
  // Ausgewiesen wird der ganzzahlige Wert, damit Kachel und Verbrauchstext
  // nicht auseinanderfallen.
  byId("co2").textContent = `${decimal(data.declared_co2_g_km ?? data.consumption.co2_g_km, 0)} g/km`;
  byId("co2-class").textContent = data.consumption.co2_class_discharged
    ? `${data.consumption.co2_class} / ${data.consumption.co2_class_discharged}`
    : data.consumption.co2_class;
  const rangeRow = byId("range-row");
  rangeRow.classList.toggle("hidden", data.consumption.electric_range_km === null);
  byId("range").textContent = data.consumption.electric_range_km === null ? "" : `${data.consumption.electric_range_km} km`;
  outputText = data.output_text;
  byId("output-text").textContent = outputText;
  byId("source-provider").textContent = data.source.provider;
  byId("source-type").textContent = data.source.type_code;
  byId("source-year").textContent = String(data.source.model_year);
  byId("source-time").textContent = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.source.retrieved_at));
  byId("data-sheet-actions").classList.toggle("hidden", !["online_offer", "leasing_offer"].includes(data.usage_context));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  selectedTypeId = undefined;
  submit.disabled = true;
  showMessage("Fahrzeug wird geprüft …", "loading");
  try {
    showResult(await fetchCompliance(input.value.trim(), usageContext.value as UsageContext));
  } catch (error) {
    let text = error instanceof Error && error.message === "missing_configuration"
      ? "Bitte zuerst die Verbindung zum KAHLE-Dienst einrichten."
      : error instanceof Error ? error.message : "Die Fahrzeugdaten konnten nicht geprüft werden.";
    if (error instanceof ComplianceApiError && error.candidates.length) showCandidates(error);
    else showMessage(text, "error");
  } finally {
    submit.disabled = false;
  }
});

byId<HTMLButtonElement>("copy-button").addEventListener("click", async () => {
  const feedback = byId("copy-feedback");
  try {
    await copyToClipboard(outputText);
    feedback.textContent = "✓ Verbrauchstext kopiert";
    feedback.className = "copy-feedback success-text";
  } catch (error) {
    feedback.textContent = error instanceof Error ? error.message : "Kopieren nicht möglich.";
    feedback.className = "copy-feedback error-text";
  }
});
byId<HTMLButtonElement>("settings-button").addEventListener("click", () => chrome.runtime.openOptionsPage());

async function openPrintView(): Promise<void> {
  const feedback = byId("snippet-feedback");
  feedback.textContent = "Druckansicht wird vorbereitet \u2026";
  feedback.className = "copy-feedback";
  try {
    const snippet = await fetchDataSheetSnippet(
      input.value.trim(), usageContext.value as UsageContext, selectedTypeId,
    );
    // Der Hinweis wird der Druckseite über die Sitzungsablage übergeben. Eine
    // Blob-URL erbte die Content Security Policy der Erweiterung und könnte dort
    // keinen Ereignisbehandler ausführen.
    await chrome.storage.session.set({ printSheet: snippet });
    await chrome.tabs.create({ url: chrome.runtime.getURL("print.html") });
    feedback.textContent = "";
  } catch (error) {
    feedback.textContent = error instanceof Error && error.message === "missing_configuration"
      ? "Bitte zuerst die Verbindung zum KAHLE-Dienst einrichten."
      : error instanceof Error ? error.message : "Die Druckansicht konnte nicht geöffnet werden.";
    feedback.className = "copy-feedback error-text";
  }
}

byId<HTMLButtonElement>("copy-snippet").addEventListener("click", async () => {
  const feedback = byId("snippet-feedback");
  const fallback = byId<HTMLTextAreaElement>("snippet-fallback");
  fallback.classList.add("hidden");
  feedback.textContent = "Einbettbarer Hinweis wird erstellt \u2026";
  feedback.className = "copy-feedback";

  let snippet = "";
  try {
    snippet = await fetchDataSheetSnippet(
      input.value.trim(), usageContext.value as UsageContext, selectedTypeId,
    );
  } catch (error) {
    feedback.textContent = error instanceof Error && error.message === "missing_configuration"
      ? "Bitte zuerst die Verbindung zum KAHLE-Dienst einrichten."
      : error instanceof Error ? error.message : "Der einbettbare Hinweis konnte nicht erstellt werden.";
    feedback.className = "copy-feedback error-text";
    return;
  }

  try {
    await copyToClipboard(snippet);
    feedback.textContent = "\u2713 HTML kopiert. Bei der Fahrzeugbeschreibung des Angebots einfügen.";
    feedback.className = "copy-feedback success-text";
  } catch {
    // Der Hinweis liegt vor, nur der Browser lässt das Schreiben nicht zu.
    // Er wird deshalb zum manuellen Kopieren angeboten statt verworfen.
    fallback.value = snippet;
    fallback.classList.remove("hidden");
    fallback.focus();
    fallback.select();
    feedback.textContent = "Der Browser hat das automatische Kopieren abgelehnt. Der Text unten ist markiert \u2013 bitte mit Strg+C kopieren.";
    feedback.className = "copy-feedback error-text";
  }
});

byId<HTMLButtonElement>("open-data-sheet").addEventListener("click", () => void openPrintView());

byId<HTMLButtonElement>("range-copy").addEventListener("click", async () => {
  const feedback = byId("range-copy-feedback");
  try {
    await copyToClipboard(rangeOutputText);
    feedback.textContent = "\u2713 Verbrauchstext kopiert";
    feedback.className = "copy-feedback success-text";
  } catch {
    feedback.textContent = "Kopieren nicht möglich. Der Text lässt sich oben markieren und mit Strg+C kopieren.";
    feedback.className = "copy-feedback error-text";
  }
});
