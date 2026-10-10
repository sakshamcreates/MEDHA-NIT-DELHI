/** Typed client for the ARUNYA API. Never invents data: every function
 *  returns exactly what the backend sent, and throws ApiError on failure —
 *  callers must render loading/error/empty states, never fake success. */

const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    });
  } catch {
    throw new ApiError(0, 'Could not reach the server. Is the API running?');
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON */
  }
  if (!res.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface OccupationSummary {
  id: string;
  title: string;
  domain: string;
  education_required: string;
  demand_trend: string;
}

export interface SkillSummary {
  skill_id: string;
  label: string;
}

export interface SkillEvidence {
  type: 'direct' | 'contextual';
  span: string | null;
  note?: string | null;
  start?: number | null;
  end?: number | null;
}

export interface SkillPrediction {
  skill_id: string;
  label: string;
  score: number;
  confidence: 'high' | 'review';
  method: 'phrase_match' | 'contextual_inference';
  evidence: SkillEvidence;
  occupation_context: { occupation_id: string; title: string; score: number }[];
  notes: string[];
}

export interface ExtractResponse {
  model: { name: string; version: string; [k: string]: unknown };
  skills: SkillPrediction[];
  abstained: boolean;
  abstention_reason: string | null;
  evaluation_note: string;
}

export interface RecommendResponse {
  target_occupation: {
    id: string;
    title: string;
    domain: string;
    education_required: string;
    salary_lpa_median: number;
    salary_percentiles: Record<string, number>;
    demand_trend: string;
    qualifying_exams: string[];
    top_cities: string[];
    bright_outlook: boolean;
    remote_friendly: boolean;
  };
  matched_skills: { skill_id: string; label: string }[];
  missing_skills: { skill_id: string; label: string }[];
  skill_overlap: { dice: number; n_matched: number; n_required: number; n_profile: number };
  explanation: string;
  pathway: {
    skill_id: string;
    label: string;
    priority_score: number;
    transferability: number;
    demand_weight: number;
    why: string;
    next_steps: { text: string; source: 'dataset' | 'heuristic_suggestion' }[];
  }[];
  education: { required: string; qualifying_exams: string[]; profile_education: string | null; note: string };
  heuristic_rank_score: number;
  score_breakdown: Record<string, number>;
  score_note: string;
  twelve_month_feasibility: { available: boolean; reason: string; what_is_needed: string };
  warnings: string[];
}

export interface MarketSignals {
  n_occupations: number;
  n_domains: number;
  salary_by_domain: { domain: string; n_occupations: number; median_lpa: number; p25_lpa: number; p75_lpa: number }[];
  demand_by_domain: { domain: string; trend: string; n_occupations: number }[];
  source: string;
  unit: string;
  caveats: string[];
}

export const api = {
  health: () => apiFetch<{ status: string; evaluation_note: string }>('/api/health'),
  occupations: (params?: { domain?: string; q?: string }) => {
    const qs = new URLSearchParams();
    if (params?.domain) qs.set('domain', params.domain);
    if (params?.q) qs.set('q', params.q);
    const s = qs.toString();
    return apiFetch<OccupationSummary[]>(`/api/occupations${s ? `?${s}` : ''}`);
  },
  skills: () => apiFetch<SkillSummary[]>('/api/skills'),
  extract: (text: string, top_k = 10) =>
    apiFetch<ExtractResponse>('/api/skills/extract', {
      method: 'POST',
      body: JSON.stringify({ text, top_k }),
    }),
  recommend: (skill_ids: string[], target_occupation_id: string, profile_education?: string | null) =>
    apiFetch<RecommendResponse>('/api/career/recommend', {
      method: 'POST',
      body: JSON.stringify({ skill_ids, target_occupation_id, profile_education: profile_education ?? null }),
    }),
  marketSignals: () => apiFetch<MarketSignals>('/api/market/signals'),
};

export { API_BASE };
