export type Settings = { apiUrl: string; apiKey: string };
export type UsageContext = "advertising" | "social_media" | "online_offer" | "leasing_offer";

export type ModelRangeGroup = {
  powertrain: string;
  variant_count: number;
  co2_class_best: string;
  co2_class_worst: string;
};

export type ModelRangeResult = {
  status: "verified";
  result_type: "model_range";
  usage_context: UsageContext;
  brand: string;
  model_family: string;
  variant_count: number;
  groups: ModelRangeGroup[];
  output_text: string;
  source: {
    provider: string;
    retrieved_at: string;
    model_years: number[];
    type_ids: string[];
  };
};

export type ComplianceResult = {
  status: "verified";
  confidence: number;
  powertrain: string;
  usage_context: UsageContext;
  declared_co2_g_km?: number;
  notice?: string;
  vehicle: {
    brand: string;
    model: string;
    trim: string;
    power_kw: number;
    power_ps: number | null;
    battery_kwh: number | null;
    transmission: string;
    model_year: number;
    type_code: string;
    vehicle_class?: string;
  };
  consumption: {
    combined_kwh_100km: number | null;
    combined_l_100km: number | null;
    discharged_l_100km: number | null;
    co2_g_km: number;
    co2_class: string;
    electric_range_km: number | null;
    co2_class_discharged: string | null;
  };
  energy_costs: {
    annual_cost_eur: number;
    annual_distance_km: number;
    electricity_price_eur_kwh: number;
    reference_year: number;
  };
  output_text: string;
  source: {
    provider: string;
    model_id: string;
    model_year: number;
    type_code: string;
    retrieved_at: string;
  };
};
