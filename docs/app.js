const API_URL = "https://llmfoundry.straivedemo.com/openai/v1/chat/completions";
const MODEL_NAME = "gpt-5";

const state = {
  analysis: null,
  playbooks: null,
  samples: [],
  selectedSampleId: null,
  activeFilter: "all",
  generatedDraft: null,
  streamAbortController: null,
  isGenerating: false,
  charts: {},
};

const CATEGORY_COLORS = {
  development_program: "#0d7a74",
  shipment_logistics: "#bf5a36",
  inspection_quality: "#cf9d29",
  documents_commercial: "#355c7d",
  production_status: "#6c7a3b",
  costing_pricing: "#8c3c24",
  collaboration_misc: "#61737a",
  internal_approval: "#4d4f63",
  other: "#b7a28b",
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  try {
    const { analysis, playbooks, samples } = await loadDashboardData();

    state.analysis = analysis;
    state.playbooks = playbooks;
    state.samples = samples;
    state.selectedSampleId = samples[0]?.id ?? null;

    bindControls();
    renderSummary();
    renderDraftStudio();
  } catch (error) {
    console.error(error);
    setStatus(
      "error",
      "The dashboard data could not be loaded. Check the static files under docs/data/."
    );
  }
}

async function loadDashboardData() {
  try {
    const analysis = readInlineJson("analysis-data");
    const playbooks = readInlineJson("playbooks-data");
    const samples = readInlineJson("samples-data");

    if (!analysis || !playbooks || !samples) {
      throw new Error("Embedded dashboard data is missing.");
    }

    return { analysis, playbooks, samples };
  } catch (error) {
    console.warn("Inline dashboard data failed to parse, falling back to hosted JSON files.", error);

    const [analysis, playbooks, samples] = await Promise.all([
      fetchJson("./data/analysis.json"),
      fetchJson("./data/response_playbooks.json"),
      fetchJson("./data/sample_emails.json"),
    ]);

    return { analysis, playbooks, samples };
  }
}

function readInlineJson(id) {
  const node = document.getElementById(id);
  if (!node?.textContent?.trim()) {
    return null;
  }
  return JSON.parse(node.textContent);
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: ${response.status}`);
  }
  return response.json();
}

function bindControls() {
  document.getElementById("generateButton").addEventListener("click", generateDraft);
  document.getElementById("copyButton").addEventListener("click", copyDraft);
}

function renderSummary() {
  const { analysis, playbooks } = state;
  const messageCount = analysis.messageCount;
  const externalCount = analysis.externalMessageCount;
  const reviewOnlyCount = analysis.automationCandidates
    .filter((item) => item.automationFit === "Human review required")
    .reduce((sum, item) => sum + item.count, 0);
  const draftableCount = analysis.messageCount - reviewOnlyCount;

  setText("heroMessageCount", formatNumber(messageCount));
  setText("heroDraftableCount", formatNumber(draftableCount));
  setText("heroExternalCount", formatNumber(externalCount));
  setText("heroManualCount", formatNumber(reviewOnlyCount));

  setText("statMessageCount", formatNumber(messageCount));
  setText("statExternalShare", formatPercent(externalCount / messageCount));
  setText("statDraftCoverage", formatPercent(draftableCount / messageCount));
  setText("statReviewCount", formatNumber(reviewOnlyCount));

  renderObservationList(analysis.observations);
  renderSubjectList(analysis.topSubjects);
  renderPlaybookList(analysis.automationCandidates, playbooks);
  renderCharts();
}

function renderObservationList(items) {
  const list = document.getElementById("observationList");
  list.innerHTML = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderSubjectList(items) {
  const list = document.getElementById("subjectList");
  list.innerHTML = items
    .slice(0, 8)
    .map(
      (item) => `
        <article class="subject-row">
          <div>
            <strong>${escapeHtml(item.value || "(No subject)")}</strong>
          </div>
          <span class="count">${formatNumber(item.count)}</span>
        </article>
      `
    )
    .join("");
}

function renderPlaybookList(candidates, playbooks) {
  const list = document.getElementById("playbookList");
  list.innerHTML = candidates
    .map((item) => {
      const details = playbooks[item.category];
      return `
        <article class="playbook-card">
          <header>
            <strong>${formatCategory(item.category)}</strong>
            <span class="fit-badge">${escapeHtml(item.automationFit)}</span>
          </header>
          <p>${escapeHtml(details.description)}</p>
        </article>
      `;
    })
    .join("");
}

function renderCharts() {
  if (typeof Chart === "undefined") {
    renderChartFallback("categoryChart");
    renderChartFallback("directionChart");
    renderChartFallback("domainChart");
    return;
  }
  renderCategoryChart();
  renderDirectionChart();
  renderDomainChart();
}

function renderChartFallback(id) {
  const canvas = document.getElementById(id);
  const parent = canvas?.parentElement;
  if (!canvas || !parent) {
    return;
  }
  canvas.style.display = "none";
  if (!parent.querySelector(".chart-fallback")) {
    const note = document.createElement("div");
    note.className = "chart-fallback";
    note.textContent = "Chart library could not be loaded. The summary cards and tables are still available.";
    parent.appendChild(note);
  }
}

function renderCategoryChart() {
  const labels = Object.keys(state.analysis.categoryCounts);
  const data = Object.values(state.analysis.categoryCounts);
  const colors = labels.map((label) => CATEGORY_COLORS[label] || "#999999");

  replaceChart("categoryChart", {
    type: "doughnut",
    data: {
      labels: labels.map(formatCategory),
      datasets: [
        {
          data,
          backgroundColor: colors,
          borderWidth: 0,
          hoverOffset: 8,
        },
      ],
    },
    options: baseChartOptions({
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 14, usePointStyle: true } },
      },
    }),
  });
}

function renderDirectionChart() {
  const entries = Object.entries(state.analysis.directionCounts);
  replaceChart("directionChart", {
    type: "bar",
    data: {
      labels: entries.map(([label]) => formatDirection(label)),
      datasets: [
        {
          label: "Messages",
          data: entries.map(([, value]) => value),
          borderRadius: 14,
          backgroundColor: ["#0d7a74", "#bf5a36", "#355c7d", "#cf9d29"],
        },
      ],
    },
    options: baseChartOptions({
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { color: "rgba(22, 51, 62, 0.08)" },
          ticks: { color: "#5d716e" },
        },
        y: {
          grid: { display: false },
          ticks: { color: "#16333e" },
        },
      },
    }),
  });
}

function renderDomainChart() {
  const entries = state.analysis.topExternalDomains.slice(0, 7);
  replaceChart("domainChart", {
    type: "bar",
    data: {
      labels: entries.map((item) => item.value),
      datasets: [
        {
          label: "Touches",
          data: entries.map((item) => item.count),
          borderRadius: 12,
          backgroundColor: "#0d4f59",
        },
      ],
    },
    options: baseChartOptions({
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#5d716e", maxRotation: 25, minRotation: 25 },
        },
        y: {
          grid: { color: "rgba(22, 51, 62, 0.08)" },
          ticks: { color: "#5d716e" },
        },
      },
    }),
  });
}

function baseChartOptions(extra = {}) {
  return {
    maintainAspectRatio: false,
    layout: { padding: 6 },
    plugins: {
      tooltip: {
        backgroundColor: "#10242c",
        titleFont: { family: "Space Grotesk" },
        bodyFont: { family: "Source Sans 3" },
      },
    },
    ...extra,
  };
}

function replaceChart(id, config) {
  if (state.charts[id]) {
    state.charts[id].destroy();
  }
  const ctx = document.getElementById(id);
  state.charts[id] = new Chart(ctx, config);
}

function renderDraftStudio() {
  renderFilterChips();
  renderSampleList();
  renderSelectedEmail();
}

function renderFilterChips() {
  const container = document.getElementById("filterChips");
  const categories = ["all", ...new Set(state.samples.map((item) => item.category))];
  container.innerHTML = categories
    .map((category) => {
      const isActive = state.activeFilter === category;
      return `
        <button
          class="chip ${isActive ? "active" : ""}"
          data-filter="${category}"
          type="button"
        >
          ${category === "all" ? "All Samples" : formatCategory(category)}
        </button>
      `;
    })
    .join("");

  container.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      state.activeFilter = chip.dataset.filter;
      const filtered = getFilteredSamples();
      if (!filtered.some((item) => item.id === state.selectedSampleId)) {
        state.selectedSampleId = filtered[0]?.id ?? null;
      }
      renderDraftStudio();
    });
  });
}

function renderSampleList() {
  const list = document.getElementById("sampleList");
  const filtered = getFilteredSamples();
  list.innerHTML = filtered
    .map((sample) => {
      const active = sample.id === state.selectedSampleId;
      return `
        <article class="sample-card ${active ? "active" : ""}" data-sample-id="${sample.id}">
          <header>
            <div>
              <strong>${escapeHtml(sample.subject)}</strong>
            </div>
            <span class="pill">${formatCategory(sample.category)}</span>
          </header>
          <p>${escapeHtml(sample.summary)}</p>
          <div class="sample-meta">
            <small><strong>From:</strong> ${escapeHtml(sample.from)}</small>
            <small><strong>Date:</strong> ${formatDate(sample.date)}</small>
            <small><strong>Direction:</strong> ${formatDirection(sample.direction)}</small>
          </div>
        </article>
      `;
    })
    .join("");

  list.querySelectorAll(".sample-card").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedSampleId = card.dataset.sampleId;
      state.generatedDraft = null;
      renderSampleList();
      renderSelectedEmail();
      renderGeneratedDraft();
      setStatus("neutral", "Sample changed. Generate a new GPT-5 draft when ready.");
    });
  });
}

function renderSelectedEmail() {
  const sample = getSelectedSample();
  if (!sample) {
    return;
  }

  setText("selectedSubject", sample.subject);
  setText("selectedCategory", formatCategory(sample.category));

  document.getElementById("selectedMeta").innerHTML = [
    metaItem("From", sample.from),
    metaItem("To", sample.to.join(", ")),
    metaItem("Date", formatDate(sample.date)),
    metaItem("Direction", formatDirection(sample.direction)),
  ].join("");

  document.getElementById("selectedBody").textContent = sample.body;
}

function metaItem(label, value) {
  return `
    <div class="meta-item">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderGeneratedDraft() {
  const payload = state.generatedDraft;
  const copyButton = document.getElementById("copyButton");
  const generateButton = document.getElementById("generateButton");
  generateButton.disabled = state.isGenerating;

  if (!payload) {
    setText("intentSummary", "No draft generated yet.");
    document.getElementById("draftText").textContent = "No draft generated yet.";
    renderTagList("missingList", []);
    renderTagList("flagList", []);
    copyButton.disabled = true;
    return;
  }

  setText("intentSummary", payload.intent_summary || "No intent summary returned.");
  document.getElementById("draftText").textContent =
    payload.draft_email || "The model did not return a draft body.";
  renderTagList("missingList", payload.missing_information || []);
  renderTagList("flagList", payload.review_flags || []);
  copyButton.disabled = !(payload.draft_email || payload.reply_subject);
}

function renderTagList(id, values) {
  const list = document.getElementById(id);
  const safeValues = values.length ? values : ["None"];
  list.innerHTML = safeValues.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function getFilteredSamples() {
  if (state.activeFilter === "all") {
    return state.samples;
  }
  return state.samples.filter((sample) => sample.category === state.activeFilter);
}

function getSelectedSample() {
  return state.samples.find((sample) => sample.id === state.selectedSampleId);
}

async function generateDraft() {
  if (state.isGenerating) {
    return;
  }
  const sample = getSelectedSample();
  if (!sample) {
    setStatus("error", "No sample email is selected.");
    return;
  }

  const playbook = state.playbooks[sample.category] || state.playbooks.other;
  const project = document.getElementById("projectField").value.trim() || "my-test-project";
  const token = document.getElementById("tokenField").value.trim();
  const useSession = document.getElementById("useSession").checked;
  const generateButton = document.getElementById("generateButton");
  const copyButton = document.getElementById("copyButton");

  state.isGenerating = true;
  state.generatedDraft = {
    category: sample.category,
    intent_summary: "Streaming draft...",
    reply_subject: `Re: ${sample.subject}`,
    draft_email: "",
    missing_information: [],
    review_flags: [],
  };
  generateButton.disabled = true;
  copyButton.disabled = true;
  renderGeneratedDraft();

  setStatus("loading", "Streaming GPT-5 draft from Straive LLM Foundry...");

  const systemPrompt = [
    "You write professional operational email replies for an apparel sourcing and export team.",
    "Keep replies concise, factual, and usable by a COO or merchandising team.",
    "Do not invent shipment dates, prices, approvals, quantities, or inspection results.",
    "If information is missing, ask only the minimum follow-up needed.",
    "Return plain text only in this exact order and format.",
    "Start with the draft so the UI can stream it immediately.",
    "Format exactly as:",
    "DRAFT:",
    "<draft body>",
    "",
    "SUBJECT: <reply subject>",
    "INTENT: <one sentence summary>",
    "MISSING INFO:",
    "- <item>",
    "",
    "REVIEW FLAGS:",
    "- <item>",
    "",
    "CATEGORY: <category>",
    "If a section has nothing to add, write a single bullet with None.",
  ].join(" ");

  const userPrompt = [
    `Category: ${sample.category}`,
    `Category guidance: ${playbook.description}`,
    `Response style: ${playbook.response_style}`,
    `Must not assume: ${playbook.must_not_assume.join(", ")}`,
    "",
    "Email metadata:",
    `Subject: ${sample.subject}`,
    `From: ${sample.from}`,
    `To: ${sample.to.join(", ")}`,
    `Cc: ${(sample.cc || []).join(", ") || "(none)"}`,
    `Date: ${sample.date}`,
    `Direction: ${sample.direction}`,
    `Summary: ${sample.summary}`,
    "",
    "Email body:",
    sample.body,
  ].join("\n");

  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}:${project}`;
  }

  const payload = {
    model: MODEL_NAME,
    reasoning_effort: "minimal",
    stream: true,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userPrompt },
    ],
  };

  try {
    state.streamAbortController = new AbortController();
    const response = await fetch(API_URL, {
      method: "POST",
      headers,
      credentials: useSession ? "include" : "omit",
      signal: state.streamAbortController.signal,
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = `Request failed with status ${response.status}`;
      try {
        errorMessage = JSON.parse(errorText)?.error?.message || errorMessage;
      } catch {}
      throw new Error(errorMessage);
    }

    const content = await readChatCompletionStream(response, (rawContent) => {
      const partial = parseStructuredDraftResponse(rawContent);

      state.generatedDraft = {
        ...state.generatedDraft,
        draft_email: partial.draft_email || rawContent,
        reply_subject: partial.reply_subject || state.generatedDraft.reply_subject,
        intent_summary: partial.intent_summary || "Streaming draft...",
      };
      renderGeneratedDraft();
    });

    const parsed = parseStructuredDraftResponse(content);

    state.generatedDraft = {
      category: parsed.category || sample.category,
      intent_summary: parsed.intent_summary || sample.summary,
      reply_subject: parsed.reply_subject || `Re: ${sample.subject}`,
      draft_email: parsed.draft_email || content || "",
      missing_information: parsed.missing_information || [],
      review_flags: parsed.review_flags || [],
    };

    renderGeneratedDraft();
    setStatus(
      "success",
      "Draft generated successfully. Review the missing-information and review-flag panels before using it."
    );
  } catch (error) {
    console.error(error);
    state.generatedDraft = {
      ...state.generatedDraft,
      intent_summary: "Draft failed.",
      review_flags: [
        `Generation error: ${error.message}`,
      ],
    };
    renderGeneratedDraft();
    setStatus(
      "error",
      `Draft generation failed: ${error.message}. If you are hosting on GitHub Pages, make sure the user is already logged in to Straive or paste a temporary test token locally.`
    );
  } finally {
    state.isGenerating = false;
    state.streamAbortController = null;
    generateButton.disabled = false;
    renderGeneratedDraft();
  }
}

function safeJsonParse(content) {
  try {
    return JSON.parse(content);
  } catch {
    return {
      draft_email: content,
      missing_information: [],
      review_flags: ["Response was not valid JSON. Review manually."],
    };
  }
}

async function readChatCompletionStream(response, onContent) {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Streaming is not available in this browser.");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let accumulated = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) {
        continue;
      }

      const payload = trimmed.slice(5).trim();
      if (!payload || payload === "[DONE]") {
        continue;
      }

      const parsed = JSON.parse(payload);
      const delta = parsed?.choices?.[0]?.delta?.content;
      if (!delta) {
        continue;
      }

      accumulated += delta;
      onContent(accumulated);
      await yieldForPaint();
    }
  }

  return accumulated;
}

async function yieldForPaint() {
  await new Promise((resolve) => {
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(() => resolve());
    } else {
      setTimeout(resolve, 0);
    }
  });
}

function parseStructuredDraftResponse(text) {
  const normalized = text.replace(/\r\n/g, "\n");
  const draftEmail = extractSection(
    normalized,
    "DRAFT:",
    ["\nSUBJECT:", "\nINTENT:", "\nMISSING INFO:", "\nREVIEW FLAGS:", "\nCATEGORY:"]
  );
  const replySubject = extractSingleLineSection(normalized, "SUBJECT:");
  const intentSummary = extractSingleLineSection(normalized, "INTENT:");
  const missingInformation = extractBulletSection(
    normalized,
    "MISSING INFO:",
    ["\nREVIEW FLAGS:", "\nCATEGORY:"]
  );
  const reviewFlags = extractBulletSection(
    normalized,
    "REVIEW FLAGS:",
    ["\nCATEGORY:"]
  );
  const category = extractSingleLineSection(normalized, "CATEGORY:");

  return {
    draft_email: draftEmail,
    reply_subject: replySubject,
    intent_summary: intentSummary,
    missing_information: missingInformation,
    review_flags: reviewFlags,
    category,
  };
}

function extractSection(text, label, nextLabels) {
  const start = text.indexOf(label);
  if (start === -1) {
    return "";
  }
  const from = start + label.length;
  let end = text.length;
  for (const marker of nextLabels) {
    const idx = text.indexOf(marker, from);
    if (idx !== -1 && idx < end) {
      end = idx;
    }
  }
  return text.slice(from, end).trim();
}

function extractSingleLineSection(text, label) {
  const section = extractSection(text, label, ["\n"]);
  return section.trim();
}

function extractBulletSection(text, label, nextLabels) {
  const section = extractSection(text, label, nextLabels);
  if (!section) {
    return [];
  }
  return section
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/^-+\s*/, ""))
    .filter((line) => line && line.toLowerCase() !== "none");
}

async function copyDraft() {
  if (!state.generatedDraft?.draft_email) {
    return;
  }
  const fullText = `${state.generatedDraft.reply_subject}\n\n${state.generatedDraft.draft_email}`;
  await navigator.clipboard.writeText(fullText);
  setStatus("success", "Draft copied to clipboard.");
}

function setStatus(kind, message) {
  const banner = document.getElementById("statusBanner");
  if (!banner) {
    return;
  }
  banner.className = `status-banner ${kind}`;
  banner.textContent = message;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = value;
  }
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatPercent(value) {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatCategory(value) {
  return value
    .split("_")
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDirection(value) {
  return value
    .split("_")
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
