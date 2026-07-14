// ===== CONFIG =====
const API_BASE = "https://mcpilot-production-ac81.up.railway.app";

// ===== HERO: route-plotting canvas =====
// Scattered, unlabeled nodes (the chaotic MCP ecosystem) resolve into a
// connected, glowing flight path with waypoints (the plan) — this is the
// literal mechanic of the product, not decoration.
(function heroCanvas() {
  const canvas = document.getElementById("route-canvas");
  const ctx = canvas.getContext("2d");
  const heroEl = canvas.parentElement;
  const reticle = document.getElementById("hero-reticle");
  const coordsEl = document.getElementById("reticle-coords");
  let w, h, dpr;

  function resize() {
    dpr = window.devicePixelRatio || 1;
    w = heroEl.clientWidth;
    h = heroEl.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // pointer tracking for parallax + HUD reticle readout
  let pointer = { x: 0.5, y: 0.5, active: false };
  let parallax = { x: 0, y: 0 }; // eased toward pointer offset for smooth drift

  heroEl.addEventListener("pointermove", (e) => {
    const rect = heroEl.getBoundingClientRect();
    pointer.x = (e.clientX - rect.left) / rect.width;
    pointer.y = (e.clientY - rect.top) / rect.height;
    pointer.active = true;

    reticle.style.left = e.clientX - rect.left + "px";
    reticle.style.top = e.clientY - rect.top + "px";
    coordsEl.textContent = `${(pointer.x * 100).toFixed(1)}, ${(pointer.y * 100).toFixed(1)}`;
  });
  heroEl.addEventListener("pointerleave", () => { pointer.active = false; });

  const scatterCount = 46;
  const scatter = Array.from({ length: scatterCount }, () => ({
    x: Math.random(),
    y: Math.random(),
    r: 1 + Math.random() * 1.6,
    phase: Math.random() * Math.PI * 2,
    depth: 0.4 + Math.random() * 0.8, // parallax depth multiplier
  }));

  const route = [
    { x: 0.08, y: 0.78 },
    { x: 0.27, y: 0.42 },
    { x: 0.48, y: 0.6 },
    { x: 0.68, y: 0.28 },
    { x: 0.9, y: 0.4 },
  ];

  let progress = 0;
  const animDuration = prefersReducedMotion ? 0 : 2800;
  const startTime = performance.now();

  function draw(now) {
    ctx.clearRect(0, 0, w, h);

    const t = prefersReducedMotion ? 1 : Math.min(1, (now - startTime) / animDuration);
    progress = easeOutQuint(t);

    // ease parallax toward pointer target for smooth, non-jittery drift
    const targetX = pointer.active ? (pointer.x - 0.5) * 18 : 0;
    const targetY = pointer.active ? (pointer.y - 0.5) * 14 : 0;
    parallax.x += (targetX - parallax.x) * 0.06;
    parallax.y += (targetY - parallax.y) * 0.06;

    scatter.forEach((n) => {
      const flicker = 0.35 + 0.25 * Math.sin(now / 900 + n.phase);
      const px = n.x * w + parallax.x * n.depth;
      const py = n.y * h + parallax.y * n.depth;
      ctx.beginPath();
      ctx.arc(px, py, n.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(130, 145, 160, ${flicker * 0.5})`;
      ctx.fill();
    });

    const pts = route.map((p) => ({
      x: p.x * w + parallax.x * 0.3,
      y: p.y * h + parallax.y * 0.3,
    }));
    const totalSegs = pts.length - 1;
    const segProgress = progress * totalSegs;

    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(110, 231, 249, 0.55)";
    ctx.shadowColor = "rgba(110, 231, 249, 0.5)";
    ctx.shadowBlur = 10;
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

    pts.forEach((p, i) => {
      const reached = segProgress >= i;
      const r = i === pts.length - 1 ? 5 : 3.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = reached ? "#e7eef5" : "rgba(130, 145, 160, 0.5)";
      ctx.fill();
      if (reached) {
        const ringPulse = 5 + Math.sin(now / 500 + i) * 1.5;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r + ringPulse, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(110, 231, 249, 0.3)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    });

    requestAnimationFrame(draw);
  }

  function easeOutQuint(x) {
    return 1 - Math.pow(1 - x, 5);
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