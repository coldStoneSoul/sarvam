/* ═══════════════════════════════════════════════════════════════
   MSME Negotiation AI – Core Wizard Script
   Steps: 1 Upload → 2 Review/Edit → 3 AI Analysis → 4 Draft
   
   Split into modules:
     script.js       – core wizard, upload, extraction, prediction, draft
     chat.js         – chat sidebar with dual-context modes
     negotiation.js  – multi-round negotiation engine
     voice.js        – ASR/TTS voice input for form fields
   ═══════════════════════════════════════════════════════════════ */

// ── State (shared across modules via globals) ──
let currentStep = 1;
let selectedFiles = [];
let extractedTextContent = "";   // OCR'd text from step 1
let currentPrediction = null;    // XGBoost result from step 3
let currentCaseData = {};        // user-edited fields from step 2

marked.setOptions({ breaks: true, gfm: true });

// ── DOM refs ──
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const fileListEl = document.getElementById("fileList");
const extractBtn = document.getElementById("extractBtn");
const sendChatBtn = document.getElementById("sendChat");

// ══════════════════════════════════════════════════════════════
// STEP MANAGEMENT
// ══════════════════════════════════════════════════════════════
function goToStep(n) {
  currentStep = n;
  // panels
  for (let i = 1; i <= 4; i++) {
    const panel = document.getElementById("step" + i);
    panel.classList.toggle("active", i === n);
  }
  // dots & labels
  document.querySelectorAll(".step-dot").forEach(d => {
    const s = +d.dataset.step;
    d.classList.remove("active", "done");
    if (s === n) d.classList.add("active");
    else if (s < n) d.classList.add("done");
  });
  document.querySelectorAll(".step-label").forEach((l, i) => {
    l.classList.remove("active", "done");
    if (i + 1 === n) l.classList.add("active");
    else if (i + 1 < n) l.classList.add("done");
  });
  // lines
  document.querySelectorAll(".step-line").forEach(l => {
    const ln = +l.dataset.line;
    l.classList.toggle("done", ln < n);
  });
  // scroll to top of wizard
  document.getElementById("stepIndicator").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetWizard() {
  selectedFiles = [];
  extractedTextContent = "";
  currentPrediction = null;
  currentCaseData = {};
  renderFileList();
  goToStep(1);
}

// ══════════════════════════════════════════════════════════════
// STEP 1: FILE UPLOAD
// ══════════════════════════════════════════════════════════════
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", e => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", e => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) addFiles(fileInput.files);
  fileInput.value = "";
});

function addFiles(fileListObj) {
  for (const f of fileListObj) {
    if (!selectedFiles.some(s => s.name === f.name && s.size === f.size)) {
      selectedFiles.push(f);
    }
  }
  renderFileList();
}

function removeFile(idx) { selectedFiles.splice(idx, 1); renderFileList(); }
function clearAllFiles() { selectedFiles = []; renderFileList(); }

function renderFileList() {
  if (!selectedFiles.length) {
    fileListEl.style.display = "none";
    extractBtn.disabled = true;
    return;
  }
  fileListEl.style.display = "block";
  extractBtn.disabled = false;
  const totalSize = selectedFiles.reduce((a, f) => a + f.size, 0);
  let html = `<div class="flex justify-between items-center mb-2 text-sm">
    <span><span class="font-semibold">${selectedFiles.length}</span> file${selectedFiles.length > 1 ? "s" : ""} selected
    <span class="text-slate-400">(${(totalSize / 1024 / 1024).toFixed(2)} MB)</span></span>
    <button class="text-red-500 hover:underline text-xs font-semibold" onclick="clearAllFiles()">✕ Clear all</button>
  </div>`;
  selectedFiles.forEach((f, i) => {
    html += `<div class="flex items-center gap-2 border border-gray-200 rounded-md px-3 py-2 mb-1 bg-slate-50 text-sm">
      <span>📎</span>
      <span class="flex-1 truncate" title="${f.name}">${f.name}</span>
      <span class="text-slate-400">${(f.size / 1024 / 1024).toFixed(2)} MB</span>
      <button class="text-red-500 font-bold px-2" onclick="removeFile(${i})">✕</button>
    </div>`;
  });
  fileListEl.innerHTML = html;
}

function showStepStatus(stepNum, type, msg) {
  const el = document.getElementById("step" + stepNum + "Status");
  if (!el) return;
  el.className = "block rounded-lg px-4 py-3 mt-3 text-sm font-medium" +
    (type === "loading" ? " bg-indigo-50 text-indigo-700" :
      type === "success" ? " bg-green-50 text-green-700" :
        type === "error" ? " bg-red-50 text-red-700" : "");
  el.innerHTML = msg;
}

// ── Extract button (Step 1 → Step 2) ──
extractBtn.addEventListener("click", async () => {
  if (!selectedFiles.length) return;
  extractBtn.disabled = true;
  showStepStatus(1, "loading", '<span class="spinner"></span> Extracting case data from document… this may take a moment.');

  const formData = new FormData();
  formData.append("file", selectedFiles[0]);  // use first file for extraction

  try {
    const resp = await fetch("/api/extract-fields", { method: "POST", body: formData });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || "Extraction failed");
    }
    const data = await resp.json();

    // Store extracted text
    extractedTextContent = data.text_content || "";

    // Populate editable fields
    const f = data.fields;
    document.getElementById("edit_claim_amount").value = f.claim_amount || 100000;
    document.getElementById("edit_delay_days").value = f.delay_days || 100;
    setSelectValue("edit_document_count", String(f.document_count || 1));
    setSelectValue("edit_dispute_type", f.dispute_type || "");
    setSelectValue("edit_jurisdiction", f.jurisdiction || "");

    // Show raw text
    document.getElementById("rawTextPreview").textContent = extractedTextContent.substring(0, 5000);

    showStepStatus(1, "success", "✅ Extraction complete! Proceeding to review…");
    document.getElementById("chatDocBtn").style.display = "";
    setTimeout(() => goToStep(2), 600);
  } catch (err) {
    showStepStatus(1, "error", "❌ Error: " + err.message);
  }
  extractBtn.disabled = false;
});

function setSelectValue(id, value) {
  const sel = document.getElementById(id);
  for (let i = 0; i < sel.options.length; i++) {
    if (sel.options[i].value === value) { sel.selectedIndex = i; return; }
  }
}

// ══════════════════════════════════════════════════════════════
// STEP 2 → 3: PREDICT
// ══════════════════════════════════════════════════════════════
document.getElementById("predictBtn").addEventListener("click", async () => {
  const btn = document.getElementById("predictBtn");
  btn.disabled = true;
  showStepStatus(2, "loading", '<span class="spinner"></span> Running XGBoost prediction…');

  currentCaseData = {
    claim_amount: document.getElementById("edit_claim_amount").value,
    delay_days: document.getElementById("edit_delay_days").value,
    document_count: document.getElementById("edit_document_count").value,
    dispute_type: document.getElementById("edit_dispute_type").value,
    jurisdiction: document.getElementById("edit_jurisdiction").value,
  };

  try {
    const resp = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentCaseData),
    });
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || "Prediction failed");

    currentPrediction = data;
    renderPredictionResults(data);
    showStepStatus(2, "success", "✅ Analysis complete!");
    setTimeout(() => goToStep(3), 500);
  } catch (err) {
    showStepStatus(2, "error", "❌ Error: " + err.message);
  }
  btn.disabled = false;
});

function renderPredictionResults(data) {
  // Probability circle
  document.getElementById("probNumber").textContent = data.probability;
  const circle = document.getElementById("circlePath");
  circle.setAttribute("stroke-dasharray", `${data.probability}, 100`);
  circle.classList.remove("high", "medium", "low");
  circle.classList.add(data.priority_class);

  // Settlement range
  document.getElementById("settleMin").textContent = "₹" + data.settle_min;
  document.getElementById("settleMax").textContent = "₹" + data.settle_max;

  // Priority
  document.getElementById("priorityText").textContent = data.priority;
  const pill = document.getElementById("priorityPill");
  pill.textContent = data.priority_class.toUpperCase();
  pill.className = "inline-block px-3 py-1 rounded-full text-xs font-semibold " +
    (data.priority_class === "high" ? "bg-green-100 text-green-800" :
      data.priority_class === "medium" ? "bg-amber-100 text-amber-800" :
        "bg-red-100 text-red-800");

  // Deep analysis
  const container = document.getElementById("deepAnalysisContent");
  container.innerHTML = "";
  (data.deep_analysis || []).forEach(item => {
    container.innerHTML += `<div class="analysis-item impact-${item.impact}">
      <div class="flex items-center gap-3 mb-1">
        <i class="fa-solid ${item.icon} text-sm"></i>
        <span class="font-semibold text-sm flex-1">${item.factor}</span>
        <span class="impact-badge ${item.impact}">${item.impact}</span>
      </div>
      <p class="text-xs text-gray-600 ml-7">${item.description}</p>
    </div>`;
  });

  // Render Advance Tab Data
  if (data.legal_argumentation) {
    const la = data.legal_argumentation;
    const statutesList = document.getElementById("adv_statutes");
    if (statutesList) {
      statutesList.innerHTML = (la.applicable_statutes || []).map(s =>
        `<li class="flex items-start gap-2"><i class="fa-solid fa-book text-indigo-400 mt-1"></i><span><strong>Section ${s.section}:</strong> ${s.title}</span></li>`
      ).join('');
    }

    if (document.getElementById("adv_legal_arg")) document.getElementById("adv_legal_arg").textContent = `"${la.legal_argument}"`;

    const sb = la.statutory_breakdown || {};
    if (document.getElementById("adv_principal")) document.getElementById("adv_principal").textContent = "₹" + (sb.principal || 0).toLocaleString();
    if (document.getElementById("adv_interest")) document.getElementById("adv_interest").textContent = "₹" + (sb.interest || 0).toLocaleString();
    if (document.getElementById("adv_total")) document.getElementById("adv_total").textContent = "₹" + (sb.total || 0).toLocaleString();
  }

  if (data.legal_argumentation && data.legal_argumentation.escalation_risk_assessment) {
    const risk = data.legal_argumentation.escalation_risk_assessment;
    if (document.getElementById("adv_risk_recommendation")) document.getElementById("adv_risk_recommendation").textContent = risk.recommendation;
    if (document.getElementById("adv_award_prob")) document.getElementById("adv_award_prob").textContent = (risk.estimated_award_probability * 100).toFixed(0) + "%";
    if (document.getElementById("adv_recovery")) document.getElementById("adv_recovery").textContent = risk.estimated_recovery;
    if (document.getElementById("adv_timeline")) document.getElementById("adv_timeline").textContent = risk.timeline_if_escalated;
    if (document.getElementById("adv_escalation_path")) document.getElementById("adv_escalation_path").textContent = risk.escalation_path;
  }

  if (data.negotiation_strategy) {
    const ns = data.negotiation_strategy;
    if (document.getElementById("adv_opening_offer")) document.getElementById("adv_opening_offer").textContent = "₹" + ns.opening_offer;
    if (document.getElementById("adv_neg_zone")) document.getElementById("adv_neg_zone").textContent = ns.negotiation_zone;

    if (data.legal_argumentation && data.legal_argumentation.rebuttal_strategy && document.getElementById("adv_rebuttals")) {
      const rebuttals = data.legal_argumentation.rebuttal_strategy.split('|');
      document.getElementById("adv_rebuttals").innerHTML = rebuttals.map(r =>
        `<div class="text-xs bg-white p-2 border rounded text-gray-700 border-l-4 border-l-green-500">${r.trim()}</div>`
      ).join('');
    }

    if (data.legal_argumentation && data.legal_argumentation.negotiation_script && document.getElementById("adv_negotiation_script")) {
      document.getElementById("adv_negotiation_script").textContent = `"${data.legal_argumentation.negotiation_script}"`;
    }
  }
}

// Analysis Tab Switching
window.switchAnalysisTab = function (tab) {
  const summaryBtn = document.getElementById("tabSummaryBtn");
  const advanceBtn = document.getElementById("tabAdvanceBtn");
  const summaryView = document.getElementById("analysisSummary");
  const advanceView = document.getElementById("analysisAdvance");

  if (tab === 'summary') {
    summaryBtn.classList.add("text-indigo-700", "border-b-2", "border-indigo-600");
    summaryBtn.classList.remove("text-gray-500");
    advanceBtn.classList.remove("text-indigo-700", "border-b-2", "border-indigo-600");
    advanceBtn.classList.add("text-gray-500");

    summaryView.classList.remove("hidden");
    advanceView.classList.add("hidden");
  } else {
    advanceBtn.classList.add("text-indigo-700", "border-b-2", "border-indigo-600");
    advanceBtn.classList.remove("text-gray-500");
    summaryBtn.classList.remove("text-indigo-700", "border-b-2", "border-indigo-600");
    summaryBtn.classList.add("text-gray-500");

    advanceView.classList.remove("hidden");
    summaryView.classList.add("hidden");
  }
};

// ══════════════════════════════════════════════════════════════
// STEP 3 → 4: GENERATE DRAFT
// ══════════════════════════════════════════════════════════════
document.getElementById("draftBtn").addEventListener("click", async () => {
  const btn = document.getElementById("draftBtn");
  btn.disabled = true;
  showStepStatus(3, "loading", '<span class="spinner"></span> Generating settlement draft via AI…');

  try {
    const resp = await fetch("/api/generate-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text_content: extractedTextContent,
        case_data: currentCaseData,
        prediction: currentPrediction,
      }),
    });
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || "Draft generation failed");

    document.getElementById("llmDraftContent").innerHTML = marked.parse(data.rule_draft || data.llm_draft || "");
    document.getElementById("ruleDraftContent").textContent = JSON.stringify(data.structured_draft, null, 2);
    document.getElementById("draftEditor").value = data.rule_draft || "";

    showStepStatus(3, "success", "✅ Draft generated!");
    setTimeout(() => goToStep(4), 500);
  } catch (err) {
    showStepStatus(3, "error", "❌ Error: " + err.message);
  }
  btn.disabled = false;
});

// Draft tab switching
function showDraftTab(tab) {
  document.getElementById("draftLlm").classList.toggle("hidden", tab !== "llm");
  document.getElementById("draftRule").classList.toggle("hidden", tab !== "rule");
  document.getElementById("tabLlm").classList.toggle("bg-indigo-100", tab === "llm");
  document.getElementById("tabLlm").classList.toggle("text-indigo-700", tab === "llm");
  document.getElementById("tabLlm").classList.toggle("border-indigo-200", tab === "llm");
  document.getElementById("tabLlm").classList.toggle("bg-gray-100", tab !== "llm");
  document.getElementById("tabLlm").classList.toggle("text-gray-600", tab !== "llm");
  document.getElementById("tabLlm").classList.toggle("border-gray-200", tab !== "llm");
  document.getElementById("tabRule").classList.toggle("bg-indigo-100", tab === "rule");
  document.getElementById("tabRule").classList.toggle("text-indigo-700", tab === "rule");
  document.getElementById("tabRule").classList.toggle("border-indigo-200", tab === "rule");
  document.getElementById("tabRule").classList.toggle("bg-gray-100", tab !== "rule");
  document.getElementById("tabRule").classList.toggle("text-gray-600", tab !== "rule");
  document.getElementById("tabRule").classList.toggle("border-gray-200", tab !== "rule");
}

// ══════════════════════════════════════════════════════════════
// PDF EXPORT (Step 4)
// ══════════════════════════════════════════════════════════════

// Template Draft PDF (rule-based)
document.getElementById("exportDraftPdfBtn").addEventListener("click", async () => {
  const payload = { ...currentCaseData, ...currentPrediction };
  try {
    const resp = await fetch("/api/export-settlement-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error("PDF generation failed");
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Template_Draft_${Date.now()}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("❌ PDF Error: " + err.message);
  }
});

// AI-Generated Draft PDF
document.getElementById("exportAiDraftPdfBtn").addEventListener("click", async () => {
  const draftText = document.getElementById("llmDraftContent").textContent || "";
  if (!draftText.trim()) {
    alert("No AI draft available yet. Please generate it first.");
    return;
  }
  try {
    const resp = await fetch("/api/export-ai-draft-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_text: draftText, ...currentCaseData }),
    });
    if (!resp.ok) throw new Error("AI Draft PDF generation failed");
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `AI_Settlement_Draft_${Date.now()}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("❌ AI Draft PDF Error: " + err.message);
  }
});

// ══════════════════════════════════════════════════════════════
// SUMMARIZE MODAL
// ══════════════════════════════════════════════════════════════
const summarizeModal = document.getElementById("summarizeModal");
const closeModal = document.getElementById("closeModal");
const cancelBtn = document.getElementById("cancelBtn");
const submitSummary = document.getElementById("submitSummary");
const textInput = document.getElementById("textInput");
const summaryResult = document.getElementById("summaryResult");
const summaryContent = document.getElementById("summaryContent");
const summaryStatus = document.getElementById("summaryStatus");

function closeModalFunc() { summarizeModal.classList.add("hidden"); }
closeModal.addEventListener("click", closeModalFunc);
cancelBtn.addEventListener("click", closeModalFunc);
summarizeModal.addEventListener("click", e => { if (e.target === summarizeModal) closeModalFunc(); });

submitSummary.addEventListener("click", async () => {
  const text = textInput.value.trim();
  if (!text) { showSummaryStatus("error", "⚠️ Please enter some text to summarize."); return; }
  submitSummary.disabled = true;
  summaryResult.classList.add("hidden");
  showSummaryStatus("loading", '<span class="spinner"></span> Generating summary...');

  try {
    const resp = await fetch("/api/summarize-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!resp.ok) { const err = await resp.json(); throw new Error(err.error || "Summarization failed"); }
    const data = await resp.json();
    summaryContent.textContent = data.summary;
    summaryResult.classList.remove("hidden");
    showSummaryStatus("success", "✅ Summary generated successfully!");
  } catch (err) {
    showSummaryStatus("error", "❌ Error: " + err.message);
  }
  submitSummary.disabled = false;
});

function showSummaryStatus(type, msg) {
  summaryStatus.className = "block rounded-lg px-4 py-3 text-sm font-medium" +
    (type === "loading" ? " bg-indigo-50 text-indigo-700" :
      type === "success" ? " bg-green-50 text-green-700" :
        type === "error" ? " bg-red-50 text-red-700" : "");
  summaryStatus.innerHTML = msg;
  summaryStatus.classList.remove("hidden");
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}