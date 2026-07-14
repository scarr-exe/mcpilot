// ===== CONFIG =====
const API_BASE = "https://mcpilot-production.up.railway.app";

// ===== HERO: route-plotting canvas =====
// Scattered, unlabeled nodes (the chaotic MCP ecosystem) resolve into a
// connected, glowing flight path with waypoints (the plan) — this is the
// literal mechanic of the product, not decoration.
(function heroCanvas() {
  const canvas = document.getElementById("route-canvas");
  const ctx = canvas.getContext("2d");
  let w, h, dpr;

  function resize() {
    dpr = window.devicePixelRatio || 1;
    w = canvas.parentElement.clientWidth;
    h = canvas.parentElement.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // scattered background nodes (the "unmapped ecosystem")
  const scatterCount = 46;
  const scatter = Array.from({ length: scatterCount }, () => ({
    x: Math.random(),
    y: Math.random(),
    r: 1 + Math.random() * 1.6,
    phase: Math.random() * Math.PI * 2,
  }));

  // the plotted flight path — 5 waypoints, positions as fractions of canvas
  const route = [
    { x: 0.08, y: 0.78 },
    { x: 0.27, y: 0.42 },
    { x: 0.48, y: 0.6 },
    { x: 0.68, y: 0.28 },
    { x: 0.9, y: 0.4 },
  ];

  let progress = 0; // 0..1, how much of the route is drawn in
  const animDuration = prefersReducedMotion ? 0 : 2600;
  const startTime = performance.now();

  function draw(now) {
    ctx.clearRect(0, 0, w, h);

    const t = prefersReducedMotion ? 1 : Math.min(1, (now - startTime) / animDuration);
    progress = easeOutCubic(t);

    // background scatter, gently pulsing
    scatter.forEach((n) => {
      const flicker = 0.35 + 0.25 * Math.sin(now / 900 + n.phase);
      ctx.beginPath();
      ctx.arc(n.x * w, n.y * h, n.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(130, 145, 160, ${flicker * 0.5})`;
      ctx.fill();
    });

    // route line, drawn progressively
    const pts = route.map((p) => ({ x: p.x * w, y: p.y * h }));
    const totalSegs = pts.length - 1;
    const segProgress = progress * totalSegs;

    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(110, 231, 249, 0.55)";
    ctx.shadowColor = "rgba(110, 231, 249, 0.5)";
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 0; i < totalSegs; i++) {
      if (segProgress > i) {
        const segT = Math.min(1, segProgress - i);
        const x = pts[i].x + (pts[i + 1].x - pts[i].x) * segT;
        const y = pts[i].y + (pts[i + 1].y - pts[i].y) * segT;
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // waypoint nodes — lit up once the route reaches them
    pts.forEach((p, i) => {
      const reached = segProgress >= i;
      const r = i === pts.length - 1 ? 5 : 3.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = reached ? "#e7eef5" : "rgba(130, 145, 160, 0.5)";
      ctx.fill();
      if (reached) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, r + 5, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(110, 231, 249, 0.35)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    });

    if (t < 1 || !prefersReducedMotion) {
      requestAnimationFrame(draw);
    }
  }

  function easeOutCubic(x) {
    return 1 - Math.pow(1 - x, 3);
  }

  requestAnimationFrame(draw);
})();

// ===== LIVE DEMO =====
const form = document.getElementById("plan-form");
const goalInput = document.getElementById("goal-input");
const submitBtn = document.getElementById("submit-btn");
const statusLine = document.getElementById("status-line");
const resultPanel = document.getElementById("result-panel");
const briefingEl = document.getElementById("tab-briefing");
const rawEl = document.getElementById("raw-json");

// tab switching
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
  });
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const goal = goalInput.value.trim();
  if (!goal) return;

  submitBtn.disabled = true;
  submitBtn.textContent = "Plotting route...";
  statusLine.textContent = "Contacting MCPilot — decomposing, discovering, ranking, plotting...";
  statusLine.classList.remove("error");
  resultPanel.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE}/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `Request failed (${res.status})`);
    }

    const data = await res.json();
    renderResult(data);
    statusLine.textContent = `Route plotted — ${data.capabilities.length} capabilities, ${Object.keys(data.recommendations).length} matched.`;
  } catch (err) {
    statusLine.textContent = `Route failed: ${err.message}`;
    statusLine.classList.add("error");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Plot route";
  }
});

// Builds a plain-English "briefing" directly from the real explanation/
// reason/notes text the backend already generated — no extra LLM call,
// no fabricated summary, just the real output reformatted for reading.
function renderResult(data) {
  resultPanel.classList.remove("hidden");
  rawEl.textContent = JSON.stringify(data, null, 2);

  let html = "";

  html += `<h4>GOAL</h4><p class="briefing-highlight">${escapeHtml(data.goal)}</p>`;

  html += `<h4>CAPABILITIES IDENTIFIED</h4><p>${data.capabilities.map(escapeHtml).join(", ")}</p>`;

  if (data.unmatched_capabilities && data.unmatched_capabilities.length) {
    html += `<h4>NO MATCH FOUND</h4><p>${data.unmatched_capabilities.map(escapeHtml).join(", ")} — the registry currently has no MCP servers covering ${data.unmatched_capabilities.length === 1 ? "this capability" : "these capabilities"}.</p>`;
  }

  const recEntries = Object.entries(data.recommendations || {});
  if (recEntries.length) {
    html += `<h4>TOP RECOMMENDATIONS</h4>`;
    recEntries.forEach(([cap, candidates]) => {
      const top = candidates[0];
      if (!top) return;
      html += `<p><span class="briefing-highlight">${escapeHtml(cap)}</span> → <span class="briefing-highlight">${escapeHtml(top.repo_full_name)}</span> (score ${top.score}). ${escapeHtml(top.explanation || "")}</p>`;
    });
  }

  if (data.workflow && data.workflow.length) {
    html += `<h4>FLIGHT PATH</h4>`;
    data.workflow.forEach((step) => {
      html += `<p>Step ${step.step}: <span class="briefing-highlight">${escapeHtml(step.capability)}</span> via ${escapeHtml(step.mcp)}. ${escapeHtml(step.reason)}</p>`;
    });
  }

  if (data.architecture) {
    html += `<h4>SUGGESTED ARCHITECTURE</h4>`;
    html += `<p><span class="briefing-highlight">Reasoning layer:</span> ${escapeHtml(data.architecture.reasoning_layer)}</p>`;
    html += `<p><span class="briefing-highlight">Memory:</span> ${escapeHtml(data.architecture.memory)}</p>`;
    html += `<p><span class="briefing-highlight">External tools:</span> ${escapeHtml(data.architecture.external_tools)}</p>`;
    html += `<p><span class="briefing-highlight">Notes:</span> ${escapeHtml(data.architecture.notes)}</p>`;
  }

  briefingEl.innerHTML = html;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}