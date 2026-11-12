// City workspace switcher: "Trading City" (this dashboard) and "Website Agency" (the separate
// WebsiteAgencyCity board on port 4310, embedded in a frame). Pure navigation: switching never
// calls this dashboard's API, so it cannot start/stop the monitor, change settings, run research
// or enable orders. The agency keeps its own server, data and rules; nothing is shared or proxied.
(() => {
  const AGENCY = "http://127.0.0.1:4310";
  const BOARD = AGENCY + "/board/?embedded=1";
  const root = document.getElementById("root");
  if (!root) return;
  const html = document.documentElement;

  const nav = document.createElement("nav");
  nav.className = "workspace-switcher";
  nav.setAttribute("aria-label", "City workspaces");
  nav.innerHTML =
    '<span class="workspace-label" aria-hidden="true">City workspaces</span>' +
    '<a href="/" data-workspace="trading">Trading City</a>' +
    '<a href="/?workspace=agency" data-workspace="agency">Website Agency</a>';

  const panel = document.createElement("section");
  panel.className = "agency-workspace";
  panel.hidden = true;
  panel.setAttribute("aria-labelledby", "agency-ws-title");
  panel.innerHTML =
    '<h1 id="agency-ws-title" class="sr-only">Website Agency workspace</h1>' +
    '<p class="workspace-note">Website Agency · separate server and data (port 4310) · <strong>sending is off</strong> · ' +
    '<a href="' + AGENCY + '/board/" target="_blank" rel="noopener">Open in its own tab</a></p>' +
    '<div class="agency-status" role="status" aria-live="polite"></div>' +
    '<div class="agency-down" hidden>' +
    '<h2>Website Agency is not reachable</h2>' +
    '<p>The agency server on <code>127.0.0.1:4310</code> did not answer, so nothing is shown here. Trading City is unaffected.</p>' +
    '<p>To start it, open a terminal in the <code>WebsiteAgencyCity</code> folder and run:</p><pre><code>python tools/serve.py 4310</code></pre>' +
    '<p><button type="button" class="agency-retry">Check again</button></p></div>' +
    '<iframe title="Website Agency operations board" hidden></iframe>';

  root.before(nav);
  root.after(panel);
  const frame = panel.querySelector("iframe");
  const down = panel.querySelector(".agency-down");
  const status = panel.querySelector(".agency-status");
  let current = "", timer = 0, loaded = false;

  const syncNavHeight = () => html.style.setProperty("--ws-nav-h", nav.offsetHeight + "px");
  new ResizeObserver(syncNavHeight).observe(nav);

  async function probe() {
    try {
      const r = await fetch(AGENCY + "/api/health", { cache: "no-store", signal: AbortSignal.timeout(3000) });
      const j = await r.json();
      return r.ok && j.ok === true && j.service === "website-agency";
    } catch { return false; }
  }

  async function check() {
    if (!loaded) status.textContent = "Checking the Website Agency server…";
    const up = await probe();
    if (current !== "agency") return;
    down.hidden = up;
    frame.hidden = !up;
    if (up) {
      status.textContent = "";
      if (!loaded) { frame.src = BOARD; loaded = true; }
    } else {
      status.textContent = "Website Agency server unavailable.";
      if (loaded) { frame.removeAttribute("src"); loaded = false; }   // never leave a dead page that looks operational
    }
  }

  function select(name, push) {
    if (name !== "agency") name = "trading";
    const changed = name !== current;
    current = name;
    const agency = name === "agency";
    root.hidden = agency;
    panel.hidden = !agency;
    html.dataset.workspace = name;
    nav.querySelectorAll("a[data-workspace]").forEach((a) => {
      if (a.dataset.workspace === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    if (push) {
      const url = new URL(location.href);
      if (agency) url.searchParams.set("workspace", "agency"); else url.searchParams.delete("workspace");
      history.pushState({ workspace: name }, "", url);
    }
    clearInterval(timer);
    if (agency) { check(); timer = setInterval(check, 20000); }
    // The trading city listens for this to pause its 3D rendering while hidden (monitoring is server-side).
    if (changed) window.dispatchEvent(new CustomEvent("workspace-change", { detail: { workspace: name } }));
  }

  nav.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-workspace]");
    if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;   // let new-tab clicks through
    e.preventDefault();
    if (a.dataset.workspace !== current) select(a.dataset.workspace, true);
  });
  panel.querySelector(".agency-retry").addEventListener("click", () => { loaded = false; check(); });
  window.addEventListener("popstate", () => select(new URLSearchParams(location.search).get("workspace"), false));
  select(new URLSearchParams(location.search).get("workspace"), false);
})();
