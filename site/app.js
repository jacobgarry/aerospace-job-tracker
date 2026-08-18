const fallbackJobs = [
  { company: "Anduril", title: "2027 Early Career Mechanical Engineer", url: "https://boards.greenhouse.io/andurilindustries/jobs/5136984007?gh_jid=5136984007", location: "United States" },
  { company: "RTX", title: "Mechanical Engineer I", url: "https://globalhr.wd5.myworkdayjobs.com/en-US/REC_RTX_Ext_Gateway/job/US-AZ-TUCSON-928--1151-E-Hermans-Rd--MULTI-PURPOSE-FAC-928/Mechanical-Engineer-I_01866696", location: "Tucson, AZ" },
  { company: "Boeing", title: "Flight Sciences Engineer — Guidance, Navigation, and Control (GNC)", url: "https://jobs.boeing.com/job/bingen/flight-sciences-engineer-guidance-navigation-and-control-gnc/185/99278879664", location: "United States" },
  { company: "Sierra Space", title: "Mechanical Engineer I", url: "https://sierraspace.wd1.myworkdayjobs.com/en-US/Sierra_Space_External_Career_Site/job/Louisville-CO/Mechanical-Engineer-I_R26073", location: "Louisville, CO" },
];

const list = document.querySelector("#job-list");
const empty = document.querySelector("#empty-state");
const search = document.querySelector("#job-search");
const metric = document.querySelector("#metric-jobs");
const updated = document.querySelector("#updated-at");
const filters = [...document.querySelectorAll("[data-filter]")];
let jobs = [];
let activeFilter = "all";

function repairWorkdayUrl(job) {
  const value = { ...job };
  const url = String(value.url || "");
  if (url.startsWith("https://globalhr.wd5.myworkdayjobs.com/job/")) {
    value.url = url.replace(
      "https://globalhr.wd5.myworkdayjobs.com/job/",
      "https://globalhr.wd5.myworkdayjobs.com/en-US/REC_RTX_Ext_Gateway/job/",
    );
  } else if (url.startsWith("https://sierraspace.wd1.myworkdayjobs.com/job/")) {
    value.url = url.replace(
      "https://sierraspace.wd1.myworkdayjobs.com/job/",
      "https://sierraspace.wd1.myworkdayjobs.com/en-US/Sierra_Space_External_Career_Site/job/",
    );
  } else if (url.startsWith("https://blueorigin.wd5.myworkdayjobs.com/job/")) {
    value.url = url.replace(
      "https://blueorigin.wd5.myworkdayjobs.com/job/",
      "https://blueorigin.wd5.myworkdayjobs.com/en-US/BlueOrigin/job/",
    );
  }
  return value;
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function categoryFor(title = "") {
  const value = title.toLowerCase();
  if (/gnc|guidance|navigation|flight|avionics|controls?/.test(value)) return "flight";
  if (/\b(propulsion|engine|thermal|fluids?)\b/.test(value)) return "propulsion";
  if (/mechanical|structures?|stress|manufacturing|design engineer/.test(value)) return "mechanical";
  if (/systems?|integration|safety|autonomy|uas|software|electrical/.test(value)) return "systems";
  return "other";
}

function levelBadge(title = "") {
  if (/2027|new grad|early career/i.test(title)) return "2027 NEW GRAD";
  if (/associate/i.test(title)) return "ASSOCIATE";
  if (/engineer\s*(i|1)(\b|\s|—|-)/i.test(title)) return "ENGINEER I";
  return "ENTRY LEVEL";
}

function formatListingDate(value) {
  if (!value) return "Not listed";
  const dateOnly = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const parsed = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function isGenuineEntryLevelJob(job) {
  const title = String(job.title || "");
  const url = String(job.url || "");
  const blocked = /\b(senior|sr\.?|principal|staff|lead|chief|manager|director|supervisor|vice president|vp|head of|engineer\s+(ii|iii|iv|v|[2-9])|intern(ship)?|co-?op|2026)\b/i;
  const target = /\b(aerospace|mechanical|systems?|controls?|gnc|guidance|navigation|flight|test|uas|uav|autonomy|autonomous|propulsion|structures?|stress|integration|avionics|manufacturing|design|electrical|software|safety|production)\b/i;
  const content = /\b(career story|meet |passion for|ways to inspire|thrill of|in alabama|in california|life at|talent community|newsletter|event|blog)\b/i;
  return /^https?:\/\//i.test(url) && target.test(title) && !blocked.test(title) && !content.test(title) && !/\/job\/(IN|GB|CA|AU|PL|CZ|DE|FR|SG|PH|MX|BR)-/i.test(url);
}

function render() {
  const query = search.value.trim().toLowerCase();
  const visible = jobs.filter((job) => {
    const matchesText = `${job.company} ${job.title} ${job.location || ""}`.toLowerCase().includes(query);
    const matchesFilter = activeFilter === "all" || categoryFor(job.title) === activeFilter;
    return matchesText && matchesFilter;
  });

  list.innerHTML = visible.map((job, index) => {
    const companyClass = job.company.toLowerCase().replace(/[^a-z0-9]+/g, "");
    const category = categoryFor(job.title);
    const location = job.location || "See posting";
    const posted = formatListingDate(job.posted_date);
    const due = formatListingDate(job.due_date);
    const firstSeen = !job.posted_date && job.first_seen ? `<span>First seen: ${escapeHtml(formatListingDate(job.first_seen))}</span>` : "";
    return `<article class="job-card ${index === 0 && /2027|new grad|early career/i.test(job.title) ? "featured" : ""}">
      <div class="company-logo ${companyClass}">${escapeHtml(job.company.slice(0, 1).toUpperCase())}</div>
      <div class="job-main"><div class="job-meta"><span>${escapeHtml(job.company.toUpperCase())}</span><b>${levelBadge(job.title)}</b></div><h3>${escapeHtml(job.title)}</h3><p>${escapeHtml(category === "flight" ? "Flight / GNC" : category[0].toUpperCase() + category.slice(1))} · ${escapeHtml(location)}</p><div class="job-dates"><span>Posted: ${escapeHtml(posted)}</span><span>Deadline: ${escapeHtml(due)}</span>${firstSeen}</div></div>
      <a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer" aria-label="Open ${escapeHtml(job.title)} at ${escapeHtml(job.company)}">↗</a>
    </article>`;
  }).join("");
  empty.hidden = visible.length !== 0;
}

async function loadJobs() {
  try {
    const feedRoot = "https://raw.githubusercontent.com/jacobgarry/aerospace-job-tracker/main/aerospace-job-tracker/data/";
    let response = await fetch(`${feedRoot}current_jobs.json`, { cache: "no-store" });
    if (!response.ok) response = await fetch(`${feedRoot}new_jobs.json`, { cache: "no-store" });
    if (!response.ok) throw new Error("Job feed unavailable");
    const result = await response.json();
    jobs = (Array.isArray(result) ? result : result.jobs || [])
      .map(repairWorkdayUrl)
      .filter(isGenuineEntryLevelJob);
    if (!jobs.length) jobs = fallbackJobs;
    updated.textContent = `Updated ${new Date().toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
  } catch {
    jobs = fallbackJobs;
    updated.textContent = "Showing a recent verified snapshot";
  }
  metric.textContent = jobs.length;
  render();
}

search.addEventListener("input", render);
filters.forEach((button) => button.addEventListener("click", () => {
  activeFilter = button.dataset.filter;
  filters.forEach((item) => item.classList.toggle("active", item === button));
  render();
}));

loadJobs();
