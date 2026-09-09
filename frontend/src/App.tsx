import { useState, type FormEvent } from "react";
import { isAuthenticated, login, logout, register } from "./api";
import { Button } from "./components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "./components/ui/dialog";
import { Input } from "./components/ui/input";
import { ContractorView } from "./ContractorView";
import { ProjectDetailView } from "./ProjectDetail";
import { RiskEngine } from "./RiskEngine";
import { UploadStory } from "./UploadStory";

type ActiveView = "dashboard" | "upload" | "contractor" | "project";
export function App() {
  const [authenticated, setAuthenticated] = useState(isAuthenticated()); const [view, setView] = useState<ActiveView>("dashboard"); const [contractorId, setContractorId] = useState<string | null>(null); const [projectId, setProjectId] = useState<string | null>(null);
  if (!authenticated) return <Login onSuccess={() => setAuthenticated(true)} />;
  if (view === "upload") return <UploadStory onBack={() => setView("dashboard")} />;
  if (view === "contractor" && contractorId) return <ContractorView contractorId={contractorId} onBack={() => setView("dashboard")} onProject={(id) => { setProjectId(id); setView("project"); }} />;
  if (view === "project" && projectId) return <ProjectDetailView projectId={projectId} onBack={() => setView("dashboard")} onContractor={(id) => { setContractorId(id); setView("contractor"); }} />;
  return <RiskEngine onUpload={() => setView("upload")} onContractor={(id) => { setContractorId(id); setView("contractor"); }} onSignOut={() => { logout(); setAuthenticated(false); }} />;
}
function Login({ onSuccess }: { onSuccess: () => void }) {
  const [error, setError] = useState(""); const [creating, setCreating] = useState(false);
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const form = new FormData(event.currentTarget); const action = creating ? register : login; void action(String(form.get("username")), String(form.get("password"))).then(onSuccess).catch((reason: Error) => setError(reason.message)); };
  return <main className="grid min-h-screen place-items-center bg-slate-50 p-4"><form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-lg border border-slate-200 bg-white p-6"><div><p className="text-lg font-semibold tracking-tight text-slate-900">MPLAD Trace</p><h1 className="mt-5 text-2xl font-semibold text-slate-900">{creating ? "Create local account" : "Sign in"}</h1><p className="mt-1 text-sm text-slate-600">Local hackathon access. Not government SSO.</p></div><div className="space-y-3"><Input name="username" defaultValue={creating ? "" : "demo"} placeholder="Username" required /><Input name="password" type="password" defaultValue={creating ? "" : "demo123"} placeholder="Password" minLength={creating ? 8 : undefined} required /></div>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}<Button className="w-full">{creating ? "Create account" : "Sign in"}</Button><button type="button" className="text-sm text-blue-700 hover:underline" onClick={() => { setCreating(!creating); setError(""); }}>{creating ? "Use demo account" : "Create a local account"}</button></form></main>;
}
export function SignOutDialog({ onSignOut }: { onSignOut: () => void }) { return <Dialog><DialogTrigger asChild><Button variant="outline">Sign out</Button></DialogTrigger><DialogContent><h2 className="text-lg font-semibold text-slate-900">Sign out?</h2><p className="mt-2 text-sm text-slate-600">This ends the local demo session in this browser.</p><div className="mt-5 flex justify-end gap-2"><Button variant="outline">Cancel</Button><Button onClick={onSignOut}>Sign out</Button></div></DialogContent></Dialog>; }
