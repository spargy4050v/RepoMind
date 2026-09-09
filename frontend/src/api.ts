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

export interface Reason {
  code: string;
  text: string;
}

export interface ProjectDetail extends ProjectListItem {
  units: number | null;
  unit_type: string | null;
  regional_baseline_cost_inr: number;
  recommended_date: string | null;
  sanction_date: string | null;
  start_date: string | null;
  completion_certified_date: string | null;
  fund_release_date: string | null;
  planned_duration_days: number | null;
  location: { type: "Point"; coordinates: [number, number] };
  reasons: Reason[];
  nearby_projects: string[];
}

export interface ContractorDetail {
  contractor_id: string;
  total_projects: number;
  avg_risk_score: number;
  flagged_project_count: number;
  constituencies: string[];
  projects: string[];
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
const TOKEN_KEY = "mplad_trace_demo_token";

async function request<T>(path: string): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: string } | null;
    throw new Error(body?.error ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
  if (!response.ok) throw new Error((await response.json().catch(() => ({ error: "Invalid username or password" })) as { error: string }).error);
  localStorage.setItem(TOKEN_KEY, (await response.json() as { token: string }).token);
}
export async function register(username: string, password: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
  if (!response.ok) throw new Error((await response.json().catch(() => ({ error: "Unable to create account" })) as { error: string }).error);
  localStorage.setItem(TOKEN_KEY, (await response.json() as { token: string }).token);
}
export function isAuthenticated(): boolean { return Boolean(localStorage.getItem(TOKEN_KEY)); }
export function logout(): void { localStorage.removeItem(TOKEN_KEY); }

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

export function getProject(projectId: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/projects/${encodeURIComponent(projectId)}`);
}

export function getContractor(contractorId: string): Promise<ContractorDetail> {
  return request<ContractorDetail>(`/contractors/${encodeURIComponent(contractorId)}`);
}
export interface AuditEntry { timestamp: string; user: string; action: string; input_summary: string; risk_score: number | null; risk_tier: "green" | "amber" | "red" | null; reasons: Reason[]; upload_id: number | null; }
export interface Portfolio { tiers: Record<string, number>; states: Record<string, number>; work_categories: Record<string, number>; contractors: Record<string, number>; high_risk_reason_codes: Record<string, number>; synthetic: boolean; }
export function getHistory(): Promise<AuditEntry[]> { return request<AuditEntry[]>("/history"); }
export function getPortfolio(): Promise<Portfolio> { return request<Portfolio>("/analysis/portfolio"); }
export interface ExternalContextStatus { enabled: boolean; available: boolean; message: string; }
export function getExternalContextStatus(): Promise<ExternalContextStatus> { return request<ExternalContextStatus>("/context/external-status"); }
export interface UploadResult { risk_score: number; risk_tier: "green" | "amber" | "red"; reasons: Reason[]; }
export interface UploadBatch { upload_id: number; record_count: number; results: UploadResult[]; message: string; }
export interface Extraction { format: string; record: Record<string, string>; confidence: Record<string, "high" | "low">; source: { text: string; tables: string[][] }; }
export interface StoryResult extends UploadResult { story: { deterministic: string; ai_generated: boolean }; evidence: { confirmed_record: Record<string, unknown>; confidence: Record<string, string>; source: Extraction["source"] }; }
export interface StoryBatch { upload_id: number; record_count: number; results: StoryResult[]; message: string; }
async function upload(payload: object): Promise<UploadBatch> { const response = await fetch(`${API_BASE_URL}/verify/upload`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) ?? ""}` }, body: JSON.stringify(payload) }); if (!response.ok) throw new Error(((await response.json()) as { error?: string }).error ?? "Verification failed"); return response.json() as Promise<UploadBatch>; }
export function verifyRecord(record: Record<string, unknown>): Promise<UploadBatch> { return upload({ record }); }
export function verifyRecords(records: Record<string, unknown>[]): Promise<UploadBatch> { return upload({ records }); }
export function getUpload(uploadId: number): Promise<UploadBatch & { created_at: string }> { return request<UploadBatch & { created_at: string }>(`/uploads/${uploadId}`); }
export async function extractFile(file: File): Promise<Extraction> { const response = await fetch(`${API_BASE_URL}/upload/extract`, { method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) ?? ""}`, "X-Filename": file.name }, body: file }); if (!response.ok) throw new Error(((await response.json()) as { error?: string }).error ?? "Could not extract the file"); return response.json() as Promise<Extraction>; }
export async function scoreExtraction(record: Record<string, unknown>, extraction: Extraction): Promise<StoryBatch> { const response = await fetch(`${API_BASE_URL}/upload/score`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) ?? ""}` }, body: JSON.stringify({ record, extraction }) }); if (!response.ok) throw new Error(((await response.json()) as { error?: string }).error ?? "Could not score the confirmed record"); return response.json() as Promise<StoryBatch>; }
export interface Simulation { risk_score: number; reasons: Reason[]; breakdown: Record<string, number>; }
export interface Alert { alert_id: number; project_id: string; anomaly_type: string; risk_score: number; severity: "green" | "amber" | "red"; status: "new" | "under_review" | "investigating" | "resolved"; }
export function simulate(values: Record<string, number>): Promise<Simulation> { return fetch(`${API_BASE_URL}/simulate`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) ?? ""}` }, body: JSON.stringify(values) }).then(async response => { if (!response.ok) throw new Error(((await response.json()) as { error?: string }).error ?? "Simulation failed"); return response.json(); }); }
export function getAlerts(status?: string): Promise<Alert[]> { return request<Alert[]>(`/alerts${status && status !== "all" ? `?status=${status}` : ""}`); }
export function updateAlert(id: number, status: Alert["status"]): Promise<Alert> { return fetch(`${API_BASE_URL}/alerts/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) ?? ""}` }, body: JSON.stringify({ status }) }).then(async response => { if (!response.ok) throw new Error(((await response.json()) as { error?: string }).error ?? "Alert update failed"); return response.json(); }); }
