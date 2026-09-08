export type Project = { id: string; name: string; location: string; constituency: string; contractor: string; cost: number; completion: number; risk: number; anomaly: string; reasons: string[] };

/** Clearly labelled, calibrated synthetic Tier 2 records for the local demo UI. */
export const projects: Project[] = [
  ["MPLAD-1042","Rural Road Strengthening","Kandukur, Telangana","Mahbubnagar","Vardhan Infra Works",248,38,87,"Cost Inflation",["Sanctioned cost is 60% above the regional baseline.","Physical completion trails the fund-release schedule.","Contractor has a concentrated share of local awards.","Multiple high-value works occur within a compact geographic cluster."]],
  ["MPLAD-1098","Community Health Centre Upgrade","Kolar, Karnataka","Kolar","Shree Buildcon",126,72,76,"Early Payment",["Fund release precedes the certified completion milestone.","Cost is materially above comparable works."]],
  ["MPLAD-1124","Drinking Water Pipeline","Buxar, Bihar","Buxar","Ganga Civil Projects",94,54,73,"Contractor Concentration",["Contractor concentration exceeds the local portfolio threshold.","Completion evidence is behind the planned schedule."]],
  ["MPLAD-1156","Solar Street Lighting","Jodhpur, Rajasthan","Jodhpur","Desert Energy Solutions",68,89,65,"Geographic Cluster",["Nearby sanctioned works form an unusual spatial cluster."]],
  ["MPLAD-1181","Government School Labs","Mysuru, Karnataka","Mysuru","EduBuild India",51,81,52,"Completion Mismatch",["Reported completion and disbursement timing require review."]],
  ["MPLAD-1207","Drainage Rehabilitation","Nadia, West Bengal","Krishnanagar","Eastern Works Ltd",77,45,48,"Payment Timing",["Payment gap is shorter than comparable project patterns."]],
  ["MPLAD-1234","Anganwadi Centre Construction","Pune, Maharashtra","Pune","Sahyadri Contractors",42,96,31,"None",["No material anomaly signals detected."]],
  ["MPLAD-1251","Public Library Modernisation","Kochi, Kerala","Ernakulam","Malabar Projects",36,92,24,"None",["No material anomaly signals detected."]],
  ["MPLAD-1278","Village Sports Complex","Gaya, Bihar","Gaya","Magadh Construction",83,62,71,"Cost Inflation",["Cost ratio is above the calibrated review threshold."]],
  ["MPLAD-1304","Flood Protection Embankment","Barpeta, Assam","Barpeta","Brahmaputra Infra",174,41,82,"Geographic Cluster",["Project is in a dense cluster of recently sanctioned works.","Completion pace is unusually slow for released funds."]],
  ["MPLAD-1321","Bus Shelter Network","Indore, Madhya Pradesh","Indore","Central Urban Works",29,100,18,"None",["No material anomaly signals detected."]],
  ["MPLAD-1349","Primary Health Sub-centre","Madurai, Tamil Nadu","Madurai","Cauvery Builders",64,68,58,"Early Payment",["Payment timing merits a routine review."]],
].map(([id,name,location,constituency,contractor,cost,completion,risk,anomaly,reasons]) => ({ id: id as string, name: name as string, location: location as string, constituency: constituency as string, contractor: contractor as string, cost: cost as number, completion: completion as number, risk: risk as number, anomaly: anomaly as string, reasons: reasons as string[] }));

export const riskClass = (score: number) => score > 70 ? "text-rose-300 border-rose-400/30 bg-rose-400/10" : score >= 40 ? "text-amber-200 border-amber-400/30 bg-amber-400/10" : "text-emerald-200 border-emerald-400/30 bg-emerald-400/10";
export const riskLabel = (score: number) => score > 70 ? "HIGH" : score >= 40 ? "MEDIUM" : "LOW";
