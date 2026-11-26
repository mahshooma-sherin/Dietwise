import type { Meta, Plan, PlanRequest, PlanSummary, Rating, RecipeDetail } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

// Anonymous, per-browser id so feedback can personalise future plans without accounts.
export function userId(): string {
  let id = localStorage.getItem("dietwise:uid");
  if (!id) {
    id = crypto.randomUUID().replace(/-/g, "");
    localStorage.setItem("dietwise:uid", id);
  }
  return id;
}

export class ApiError extends Error {
  details: string[];
  constructor(message: string, details: string[] = []) {
    super(message);
    this.details = details;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: { "Content-Type": "application/json", "X-User-Id": userId(), ...(init.headers ?? {}) },
    });
  } catch {
    throw new ApiError("Can't reach the DietWise server. Check that the backend is running and try again.");
  }
  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    const d = body?.detail;
    if (typeof d === "string") throw new ApiError(d);
    if (d?.errors) throw new ApiError(d.message ?? "Request failed", d.errors);
    if (Array.isArray(d)) throw new ApiError("Some inputs are invalid.", d.map((e: any) => `${(e.loc ?? []).slice(1).join(".")}: ${e.msg}`));
    throw new ApiError(`Request failed (${res.status}).`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  generate: (body: PlanRequest) => request<Plan>("/api/meal-plans/generate", { method: "POST", body: JSON.stringify(body) }),
  plan: (id: string) => request<Plan>(`/api/meal-plans/${id}`),
  plans: (savedOnly = false) => request<PlanSummary[]>(`/api/meal-plans${savedOnly ? "?saved=true" : ""}`),
  savePlan: (id: string) => request<{ status: string; id: string }>(`/api/meal-plans/${id}/save`, { method: "POST" }),
  unsavePlan: (id: string) => request<{ status: string; id: string }>(`/api/meal-plans/${id}/save`, { method: "DELETE" }),
  recipe: (id: string, servings: number, currency: string, priceLevel: number) =>
    request<RecipeDetail>(`/api/recipes/${id}?servings=${servings}&currency=${currency}&price_level=${priceLevel}`),
  feedback: (planId: string, recipe_id: string, rating: Rating) =>
    request(`/api/meal-plans/${planId}/feedback`, { method: "POST", body: JSON.stringify({ recipe_id, rating }) }),
  myFeedback: () => request<Record<string, Rating>>("/api/feedback"),
  csvUrl: (planId: string) => `${BASE}/api/meal-plans/${planId}/shopping-list?format=csv`,
};
