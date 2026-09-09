import { useState, type FormEvent } from "react";
import { isAuthenticated, login, logout, register } from "./api";
import { ContractorView } from "./ContractorView";
import { RiskEngine } from "./RiskEngine";
import { UploadStory } from "./UploadStory";

type ActiveView = "dashboard" | "upload" | "contractor";

export function App() {
  const [authenticated, setAuthenticated] = useState(isAuthenticated());
  const [activeView, setActiveView] = useState<ActiveView>("dashboard");
  const [contractorId, setContractorId] = useState<string | null>(null);
  if (!authenticated) return <Login onSuccess={() => setAuthenticated(true)} />;
  if (activeView === "upload") return <><button type="button" onClick={() => setActiveView("dashboard")} className="fixed left-4 top-4 z-10 rounded border border-cyan-400 bg-slate-950 px-2 py-1 text-xs text-cyan-100">Return to dashboard</button><UploadStory /></>;
  if (activeView === "contractor" && contractorId) return <ContractorView contractorId={contractorId} onBack={() => setActiveView("dashboard")} onProject={() => setActiveView("dashboard")} />;
  return <><button type="button" onClick={() => setActiveView("upload")} className="fixed left-6 top-[26rem] z-10 hidden w-52 border-t border-slate-700 pt-5 text-left text-sm text-slate-400 hover:text-cyan-100 lg:block">Upload file</button><button type="button" onClick={() => { logout(); setAuthenticated(false); }} className="fixed right-5 top-5 z-10 rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:border-cyan-400">Sign out</button><RiskEngine onContractor={(id) => { setContractorId(id); setActiveView("contractor"); }} /></>;
}

function Login({ onSuccess }: { onSuccess: () => void }) {
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const username = String(form.get("username"));
    const password = String(form.get("password"));
    void (creating ? register(username, password) : login(username, password)).then(onSuccess).catch((reason: Error) => setError(reason.message));
  };
  return <main className="grid min-h-screen place-items-center bg-slate-950 p-5 text-slate-100"><form onSubmit={submit} className="grid w-full max-w-sm gap-4 rounded-2xl border border-slate-800 bg-slate-900 p-7"><p className="text-xs font-semibold tracking-[.2em] text-cyan-300">MPLAD TRACE</p><h1 className="text-2xl font-semibold">{creating ? "Create local account" : "Sign in"}</h1><p className="text-sm text-slate-400">Local hackathon accounts only; this is not government SSO.</p><input name="username" defaultValue={creating ? "" : "demo"} placeholder="Username" className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm" required /><input name="password" type="password" defaultValue={creating ? "" : "demo123"} placeholder="Password" minLength={creating ? 8 : undefined} className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm" required />{error && <p className="text-sm text-rose-200">{error}</p>}<button className="rounded-md border border-slate-700 px-3 py-2 text-sm hover:border-cyan-400">{creating ? "Create account" : "Sign in"}</button><button type="button" className="text-sm text-cyan-200 hover:underline" onClick={() => { setCreating(value => !value); setError(""); }}>{creating ? "Use the demo account instead" : "Create a local account"}</button></form></main>;
}
