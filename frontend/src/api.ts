export interface ProjectListItem {
  project_id: string;
  mp_constituency: string;
  state: string;
  work_category: string;
  contractor_id: string;
  sanctioned_cost_inr: number;
  risk_score: number;
  top_anomaly_type: string | null;
}

export interface ProjectListResponse {
  total: number;
  page: number;
  page_size: number;
  results: ProjectListItem[];
}

export interface Summary {
  total_projects: number;
  total_flagged: number;
  total_sanctioned_inr: number;
  avg_risk_score: number;
}

export interface ProjectFilters {
  page: number;
  pageSize: number;
  state: string;
  workCategory: string;
  minRisk: string;
  sortBy: "risk_score" | "sanctioned_cost_inr" | "completion_certified_date";
  order: "asc" | "desc";
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: string } | null;
    throw new Error(body?.error ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function getProjects(filters: ProjectFilters): Promise<ProjectListResponse> {
  const query = new URLSearchParams({
    page: String(filters.page),
    page_size: String(filters.pageSize),
    sort_by: filters.sortBy,
    order: filters.order,
  });
  if (filters.state.trim()) query.set("state", filters.state.trim());
  if (filters.workCategory.trim()) query.set("work_category", filters.workCategory.trim());
  if (filters.minRisk) query.set("min_risk", filters.minRisk);
  return request<ProjectListResponse>(`/projects?${query.toString()}`);
}

export function getSummary(): Promise<Summary> {
  return request<Summary>("/stats/summary");
}
