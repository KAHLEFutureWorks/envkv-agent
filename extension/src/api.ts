import type { ComplianceResult, ModelRangeResult, Settings, UsageContext } from "./types";

export class ComplianceApiError extends Error {
  constructor(message: string, readonly candidates: Array<{ type_id?: string; name: string; model_year?: string; reason?: string }>) {
    super(message);
  }
}

export async function loadSettings(): Promise<Settings> {
  const stored = await chrome.storage.local.get(["apiUrl", "apiKey"]);
  let managed: Record<string, unknown> = {};
  try {
    managed = await chrome.storage.managed.get(["apiUrl", "apiKey"]);
  } catch {
    // Lokal geladene Erweiterungen besitzen üblicherweise noch keine Unternehmensrichtlinie.
  }
  return {
    apiUrl: typeof managed.apiUrl === "string" ? managed.apiUrl :
      typeof stored.apiUrl === "string" ? stored.apiUrl : "http://127.0.0.1:8088",
    apiKey: typeof managed.apiKey === "string" ? managed.apiKey :
      typeof stored.apiKey === "string" ? stored.apiKey : "",
  };
}

export async function fetchCompliance(vehicleName: string, usageContext: UsageContext, selectedTypeId?: string): Promise<ComplianceResult> {
  const settings = await loadSettings();
  if (!settings.apiKey) throw new Error("missing_configuration");
  const response = await fetch(`${settings.apiUrl.replace(/\/$/, "")}/api/v1/vehicle/compliance`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": settings.apiKey },
    body: JSON.stringify({ vehicle_name: vehicleName, usage_context: usageContext, selected_type_id: selectedTypeId }),
  });
  const body = (await response.json().catch(() => ({}))) as {
    detail?: string | { message?: string; candidates?: Array<{ type_id?: string; name: string; model_year?: string; reason?: string }> };
  } & Partial<ComplianceResult>;
  if (!response.ok) {
    if (typeof body.detail === "object" && body.detail !== null) {
      throw new ComplianceApiError(
        body.detail.message || "Die Anfrage muss manuell geprüft werden.",
        body.detail.candidates || [],
      );
    }
    throw new ComplianceApiError(
      typeof body.detail === "string" ? body.detail : "Die Anfrage konnte nicht verarbeitet werden.",
      [],
    );
  }
  return body as ComplianceResult;
}

export async function fetchDataSheetSnippet(
  vehicleName: string,
  usageContext: UsageContext,
  selectedTypeId?: string,
): Promise<string> {
  const settings = await loadSettings();
  if (!settings.apiKey) throw new Error("missing_configuration");
  const response = await fetch(`${settings.apiUrl.replace(/\/$/, "")}/api/v1/vehicle/data-sheet-snippet.html`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": settings.apiKey },
    body: JSON.stringify({ vehicle_name: vehicleName, usage_context: usageContext, selected_type_id: selectedTypeId }),
  });
  if (!response.ok) throw new Error("Der einbettbare EnVKV-Hinweis konnte nicht erstellt werden.");
  return response.text();
}

export async function fetchModelRange(
  vehicleName: string,
  usageContext: UsageContext,
): Promise<ModelRangeResult> {
  const settings = await loadSettings();
  if (!settings.apiKey) throw new Error("missing_configuration");
  const response = await fetch(`${settings.apiUrl.replace(/\/$/, "")}/api/v1/vehicle/model-range`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": settings.apiKey },
    body: JSON.stringify({ vehicle_name: vehicleName, usage_context: usageContext }),
  });
  const body = (await response.json().catch(() => ({}))) as {
    detail?: string | { message?: string; candidates?: Array<{ type_id?: string; name: string; model_year?: string; reason?: string }> };
  } & Partial<ModelRangeResult>;
  if (!response.ok) {
    if (typeof body.detail === "object" && body.detail !== null) {
      throw new ComplianceApiError(
        body.detail.message || "Die Modellspanne muss manuell geprüft werden.",
        body.detail.candidates || [],
      );
    }
    throw new ComplianceApiError(
      typeof body.detail === "string" ? body.detail : "Die Modellspanne konnte nicht erstellt werden.",
      [],
    );
  }
  return body as ModelRangeResult;
}
