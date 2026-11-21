/**
 * StockPilot AI — SEC company financials API
 * Deploy as a Cloudflare Worker and bind the custom domain api.technofront.org.
 * Required Worker variable: SEC_USER_AGENT = "StockPilotAI/1.0 (contact: YOUR_EMAIL)"
 */
const ALLOWED_ORIGINS = new Set(["https://technofront.org", "https://www.technofront.org"]);
const SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json";
const SEC_DATA = "https://data.sec.gov";
const SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data/";

const METRICS = [
  { key:"revenue", label:"Revenue", kind:"duration", tags:["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet","SalesRevenueGoodsNet","SalesRevenueServicesNet"] },
  { key:"grossProfit", label:"Gross profit", kind:"duration", tags:["GrossProfit"] },
  { key:"operatingIncome", label:"Operating income", kind:"duration", tags:["OperatingIncomeLoss"] },
  { key:"netIncome", label:"Net income", kind:"duration", tags:["NetIncomeLoss"] },
  { key:"assets", label:"Total assets", kind:"instant", tags:["Assets"] },
  { key:"liabilities", label:"Total liabilities", kind:"instant", tags:["Liabilities"] },
  { key:"equity", label:"Shareholders’ equity", kind:"instant", tags:["StockholdersEquity"] },
  { key:"cash", label:"Cash and cash equivalents", kind:"instant", tags:["CashAndCashEquivalentsAtCarryingValue","CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"] },
  { key:"operatingCashFlow", label:"Cash from operating activities", kind:"duration", tags:["NetCashProvidedByUsedInOperatingActivities"] },
  { key:"investingCashFlow", label:"Cash from investing activities", kind:"duration", tags:["NetCashProvidedByUsedInInvestingActivities"] },
  { key:"financingCashFlow", label:"Cash from financing activities", kind:"duration", tags:["NetCashProvidedByUsedInFinancingActivities"] },
  { key:"currentDebt", label:"Current portion of long-term debt", kind:"instant", tags:["LongTermDebtCurrent"] },
  { key:"longTermDebt", label:"Long-term debt, non-current", kind:"instant", tags:["LongTermDebtNoncurrent"] }
];

function corsHeaders(origin) {
  const allowed = ALLOWED_ORIGINS.has(origin) ? origin : "https://technofront.org";
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin"
  };
}
function json(data, status, origin) {
  return new Response(JSON.stringify(data), { status: status || 200, headers: { ...corsHeaders(origin), "Content-Type":"application/json; charset=utf-8", "Cache-Control":"public, max-age=300" } });
}
function cleanCik(value) { return String(value || "").replace(/\D/g, "").padStart(10, "0"); }
function archiveUrl(cik, accession, document) {
  if (!accession || !document) return null;
  return SEC_ARCHIVES + String(Number(cik)) + "/" + accession.replace(/-/g, "") + "/" + encodeURIComponent(document);
}
async function secFetch(url, env) {
  if (!env.SEC_USER_AGENT || !/contact:/i.test(env.SEC_USER_AGENT)) {
    throw new Error("SEC_USER_AGENT is not configured. Add a contact email in the Worker settings.");
  }
  const response = await fetch(url, { headers: { "User-Agent": env.SEC_USER_AGENT, "Accept":"application/json" } });
  if (!response.ok) throw new Error("SEC data service returned HTTP " + response.status);
  return response.json();
}
async function searchCompanies(q, env) {
  const data = await secFetch(SEC_TICKERS, env);
  const query = q.toUpperCase().trim();
  const rows = Object.values(data);
  const exact = rows.filter(x => String(x.ticker).toUpperCase() === query);
  const starts = rows.filter(x => String(x.title).toUpperCase().includes(query) || String(x.ticker).toUpperCase().startsWith(query));
  const seen = new Set();
  return [...exact, ...starts].filter(x => {
    const id = String(x.cik_str);
    if (seen.has(id)) return false;
    seen.add(id); return true;
  }).slice(0, 12).map(x => ({ cik:cleanCik(x.cik_str), ticker:x.ticker, name:x.title }));
}
function pickFacts(facts, metric, cik) {
  for (const tag of metric.tags) {
    const item = facts[tag];
    if (!item || !item.units) continue;
    const unitName = metric.key === "shares" ? "shares" : "USD";
    const unit = item.units[unitName] || (metric.key === "shares" ? null : item.units.USD);
    if (!unit) continue;
    const eligible = unit.filter(x => ["10-K","10-Q","20-F","40-F"].includes(x.form) && x.end && x.filed);
    const filtered = eligible.filter(x => metric.kind === "instant"
      ? !x.start
      : !!x.start && ((new Date(x.end)-new Date(x.start))/(86400000)) >= 300 && ((new Date(x.end)-new Date(x.start))/(86400000)) <= 400 && x.fp === "FY");
    const byEnd = new Map();
    for (const f of filtered) {
      const prior = byEnd.get(f.end);
      if (!prior || f.filed > prior.filed) byEnd.set(f.end, f);
    }
    const result = [...byEnd.values()].sort((a,b) => b.end.localeCompare(a.end)).slice(0,3).map(f => ({
      periodEnd:f.end, fiscalYear:f.fy || null, value:f.val, unit:unitName,
      filed:f.filed, form:f.form,
      sourceUrl:archiveUrl(cik, f.accn, null)
    }));
    if (result.length) return { key:metric.key, label:metric.label, values:result, tag };
  }
  return { key:metric.key, label:metric.label, values:[], tag:null };
}
async function getCompany(cik, env) {
  const [submissions, companyFacts] = await Promise.all([
    secFetch(SEC_DATA + "/submissions/CIK" + cik + ".json", env),
    secFetch(SEC_DATA + "/api/xbrl/companyfacts/CIK" + cik + ".json", env)
  ]);
  const recent = submissions.filings && submissions.filings.recent ? submissions.filings.recent : {};
  const forms = recent.form || [];
  const filings = forms.map((form,i) => ({
    form, filed:recent.filingDate[i], reportDate:recent.reportDate[i] || null,
    accession:recent.accessionNumber[i], document:recent.primaryDocument[i]
  })).filter(x => ["10-K","10-Q","20-F","40-F"].includes(x.form))
    .slice(0,12).map(x => ({...x, url:archiveUrl(cik,x.accession,x.document)}));
  const facts = companyFacts.facts && companyFacts.facts["us-gaap"] ? companyFacts.facts["us-gaap"] : {};
  const metrics = METRICS.map(m => pickFacts(facts,m,cik));
  return {
    company:submissions.name || companyFacts.entityName || "Unknown company",
    cik, sic:submissions.sic || null, industry:submissions.sicDescription || null,
    fiscalYearEnd:submissions.fiscalYearEnd || null,
    tickers:submissions.tickers || [], exchanges:submissions.exchanges || [],
    retrievedAt:new Date().toISOString(),
    source:"U.S. Securities and Exchange Commission (SEC) EDGAR Company Facts",
    metrics, filings
  };
}
export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    if (request.method === "OPTIONS") return new Response(null,{status:204,headers:corsHeaders(origin)});
    const url = new URL(request.url);
    try {
      if (url.pathname === "/api/health") return json({ok:true,service:"StockPilot AI SEC financials API"},200,origin);
      if (url.pathname === "/api/search") {
        const q = (url.searchParams.get("q") || "").trim();
        if (q.length < 2) return json({results:[]},200,origin);
        return json({results:await searchCompanies(q,env)},200,origin);
      }
      if (url.pathname === "/api/company") {
        const cik = cleanCik(url.searchParams.get("cik"));
        if (!/^\d{10}$/.test(cik) || Number(cik) === 0) return json({error:"A valid SEC company identifier is required."},400,origin);
        return json(await getCompany(cik,env),200,origin);
      }
      return json({error:"Not found"},404,origin);
    } catch (error) {
      return json({error:error.message || "SEC data request failed"},502,origin);
    }
  }
};
