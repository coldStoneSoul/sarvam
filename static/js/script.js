const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const fileListEl = document.getElementById("fileList");
const convertBtn = document.getElementById("convertBtn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("resultsContainer");
const sendChatBtn = document.getElementById("sendChat");
let selectedFiles = []; // Array of File objects
let conversionResults = []; // Store conversion results for summarization

marked.setOptions({
  breaks: true,
  gfm: true,
});
/* ---- Drop zone ---- */
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () =>
  dropzone.classList.remove("dragover"),
);
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) addFiles(fileInput.files);
  fileInput.value = ""; // allow re-selecting same files
});
sendChatBtn.addEventListener("click", () => {
  const chatInput = document.getElementById("chatInput");
  if (chatInput.value.trim() !== "") {
    sendMessage();
  }
});
function addFiles(fileListObj) {
  for (const f of fileListObj) {
    // avoid duplicates by name+size
    if (!selectedFiles.some((s) => s.name === f.name && s.size === f.size)) {
      selectedFiles.push(f);
    }
  }
  renderFileList();
}
function renderMarkdown(content) {
  try {
    return marked.parse(content);
  } catch (error) {
    return `<p style="color:red;">Error rendering Markdown</p>`;
    console.error(error);
  }
}
function removeFile(idx) {
  selectedFiles.splice(idx, 1);
  renderFileList();
}

function clearAllFiles() {
  selectedFiles = [];
  renderFileList();
}

function renderFileList() {
  if (selectedFiles.length === 0) {
    fileListEl.style.display = "none";
    dropzone.style.display = "block";
    convertBtn.disabled = true;
    return;
  }
  dropzone.style.display = "block";
  fileListEl.style.display = "block";
  convertBtn.disabled = false;

  const totalSize = selectedFiles.reduce((a, f) => a + f.size, 0);
  let html = `<div class="flex justify-between items-center mb-2 text-sm">
        <span><span class="font-semibold">${selectedFiles.length}</span> file${selectedFiles.length > 1 ? "s" : ""} selected
        <span class="text-slate-400">(${(totalSize / 1024 / 1024).toFixed(2)} MB total)</span></span>
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

function hideResults() {
  statusEl.className = "status";
  resultsEl.innerHTML = "";
}

function showStatus(type, msg) {
  statusEl.className =
    `block rounded-lg px-4 py-3 mt-2 text-base font-medium` +
    (type === "loading"
      ? " bg-indigo-50 text-indigo-700"
      : type === "success"
        ? " bg-green-50 text-green-700"
        : type === "error"
          ? " bg-red-50 text-red-700"
          : "");
  statusEl.innerHTML = msg;
}

/* ---- Convert ---- */
convertBtn.addEventListener("click", async () => {
  if (selectedFiles.length === 0) return;

  const format = "markdown"; // For simplicity, we convert to markdown. This can be made dynamic.
  // const useOcr = document.getElementById("useOcr").checked;
  const useOcr = true; // Always use OCR for legal documents to maximize text extraction

  convertBtn.disabled = true;
  hideResults();

  const count = selectedFiles.length;
  const isBatch = count > 1;

  if (isBatch) {
    /* ---------- Batch conversion ---------- */
    showStatus(
      "loading",
      `<span class="spinner"></span> Analyzing ${count} documents… this may take a while.`,
    );

    const formData = new FormData();
    selectedFiles.forEach((f) => formData.append("files[]", f));
    formData.append("output_format", format);
    formData.append("use_ocr", useOcr ? "true" : "false");

    try {
      const resp = await fetch("/api/convert/batch", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.error || "Batch conversion failed");
      }
      const data = await resp.json();
      const ok = data.results.filter((r) => r.success).length;
      const fail = data.results.filter((r) => !r.success).length;

      showStatus(
        "success",
        `✅ Done! ${ok} succeeded${fail ? `, ${fail} failed` : ""} out of ${data.total} files.`,
      );

      renderBatchResults(data.results);
    } catch (err) {
      showStatus("error", `❌ Error: ${err.message}`);
    }
  } else {
    /* ---------- Single file ---------- */
    showStatus(
      "loading",
      '<span class="spinner"></span> Analyzing document… this may take a moment.',
    );

    const formData = new FormData();
    formData.append("file", selectedFiles[0]);
    formData.append("output_format", format);
    formData.append("use_ocr", useOcr ? "true" : "false");

    try {
      const resp = await fetch("/api/convert?inline=true", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.error || "Conversion failed");
      }
      const data = await resp.json();
      showStatus("success", "Analysis completed successfully!");
      renderBatchResults([
        {
          success: true,
          original_filename: selectedFiles[0].name,
          filename: data.filename,
          format: data.format,
          content: data.content,
        },
      ]);
    } catch (err) {
      showStatus("error", `❌ Error: ${err.message}`);
    }
  }

  convertBtn.disabled = false;
});

/* ---- Render results ---- */
function activateTwoColumnLayout() {
  const layoutContainer = document.getElementById("layoutContainer");
  const resultsSection = document.getElementById("resultsSection");

  // Make layout two-column on desktop, stacked on mobile
  layoutContainer.classList.remove("max-w-3xl", "mx-auto");
  layoutContainer.classList.add("lg:flex-row", "lg:gap-6", "max-w-full");

  // Show results section
  resultsSection.classList.remove("hidden");
}

function renderBatchResults(results) {
  activateTwoColumnLayout(); // Activate two-column layout
  conversionResults = results; // Store results for summarization
  let html = "";
  results.forEach((r, i) => {
    if (r.success) {
      const preview =
        typeof r.content === "string"
          ? r.content
          : JSON.stringify(r.content, null, 2);
      const blob = new Blob([preview], {
        type: "text/plain;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);

      html += `<div class="shadow rounded-lg p-6 mb-4">
                <div class="flex flex-wrap justify-between items-center mb-2 gap-2">
                    <h3 class="font-semibold text-green-700 text-base">${r.original_filename}</h3>
                    <div class="flex gap-2">
                        <button class="px-3 py-1 rounded bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold" onclick="togglePreview(${i})">👁️ Preview</button>
                        <button class="px-3 py-1 rounded bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold" onclick="summarizeExtractedText(${i})">📝 Summarize</button>
                        <a class="px-3 py-1 rounded bg-green-600 hover:bg-green-700 text-white text-xs font-semibold" href="${url}" download="${r.filename}">⬇️ Download</a>
                    </div>
                    <button class="px-3 py-1 rounded bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold" 
        onclick="analyzeCase(${i})">⚖️ Analyze Case</button>
<button class="px-3 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold" 
        onclick="openChat(${i})">💬 Chat</button>
                </div>
                <div class="bg-slate-50 border border-slate-200 rounded p-3 mt-2 text-xs font-mono max-h-100 overflow-auto hidden" id="preview-${i}">${renderMarkdown(preview)}</div>
                <div class="hidden mt-3" id="summary-container-${i}"></div>
            </div>`;
    } else {
      html += `<div class="bg-white border-l-4 border-red-500 shadow rounded-lg p-6 mb-4">
                <div class="flex justify-between items-center mb-2">
                    <h3 class="font-semibold text-red-700 text-base">❌ ${r.original_filename}</h3>
                </div>
                <p class="text-red-600 text-xs">${escapeHtml(r.error)}</p>
            </div>`;
    }
  });
  resultsEl.innerHTML = html;
}

function togglePreview(idx) {
  const el = document.getElementById(`preview-${idx}`);
  if (el) el.classList.toggle("hidden");
}
let currentChatContext = "";

function openChat(idx) {
  const result = conversionResults[idx];
  currentChatContext =
    typeof result.content === "string"
      ? result.content
      : JSON.stringify(result.content);
  document.getElementById("chatSidebar").classList.remove("translate-x-full");
}

function toggleChat() {
  document.getElementById("chatSidebar").classList.add("translate-x-full");
}
// Handle sending messages
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

chatInput.addEventListener("keypress", async (e) => {
  if (e.key === "Enter" && chatInput.value.trim() !== "") {
    sendMessage();
  }
});

async function sendMessage() {
  const userMsg = chatInput.value.trim();
  chatInput.value = "";

  // 1. Add User message to UI
  appendMessage("user", userMsg);

  // 2. Show loading bubble
  const loadingId = "loading-" + Date.now();
  appendMessage(
    "ai",
    '<span class="spinner"></span> AI is thinking...',
    loadingId,
  );

  try {
    // 3. Call the API
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userMsg,
        context: currentChatContext,
      }),
    });

    const data = await resp.json();

    // 4. Replace loading with actual response
    document.getElementById(loadingId).innerHTML = data.response;
  } catch (err) {
    document.getElementById(loadingId).innerHTML = "❌ Error: " + err.message;
  }
}
// Helper to add bubbles to the UI
function appendMessage(sender, text, id = null) {
  const msgDiv = document.createElement("div");
  msgDiv.className =
    sender === "user"
      ? "bg-indigo-100 text-indigo-900 p-2 rounded-lg self-end ml-8"
      : "bg-gray-200 text-gray-900 p-2 rounded-lg mr-8";

  if (id) msgDiv.id = id;
  msgDiv.innerHTML = text;
  chatMessages.appendChild(msgDiv);

  // Scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Case Analysis Execution
async function analyzeCase(idx) {
  const file = selectedFiles[idx];
  const formData = new FormData();
  formData.append("file", file);

  showStatus("loading", "⚖️ Extracting case data and predicting outcome...");

  const resp = await fetch("/api/analyze-case", {
    method: "POST",
    body: formData,
  });
  const data = await resp.json();

  // Display result in the results container
  const container = document.getElementById(`summary-container-${idx}`);
  container.classList.remove("hidden");
  container.innerHTML = `
        <div class="bg-orange-50 border border-orange-200 rounded-lg p-4 mt-2">
            <h4 class="font-bold text-orange-800">Legal Intelligence Report</h4>
            <div class="grid grid-cols-2 gap-2 text-xs mt-2">
                <div><b>Case ID:</b> ${data.case_data.case_id}</div>
                <div><b>Jurisdiction:</b> ${data.case_data.jurisdiction}</div>
                <div><b>Win Probability:</b> ${data.prediction.predicted_win_rate}</div>
            </div>
            <div class="mt-4">
                <p class="font-semibold text-xs">Suggested Settlement Draft:</p>
                <div class="bg-white p-2 border rounded mt-1 text-xs h-32 overflow-y-auto italic">
                    ${data.settlement_draft}
                </div>
            </div>
        </div>
    `;
}

async function summarizeExtractedText(idx) {
  const result = conversionResults[idx];
  if (!result || !result.success) return;

  const text =
    typeof result.content === "string"
      ? result.content
      : JSON.stringify(result.content, null, 2);
  const container = document.getElementById(`summary-container-${idx}`);

  if (!container) return;

  // Show loading state
  container.classList.remove("hidden");
  container.innerHTML = `<div class="bg-indigo-50 text-indigo-700 rounded-lg px-4 py-3 text-sm font-medium">
        <span class="spinner"></span> Generating summary from extracted text...
    </div>`;

  try {
    const resp = await fetch("/api/summarize-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, max_tokens: 500, temperature: 0.7 }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || "Summarization failed");
    }

    const data = await resp.json();
    container.innerHTML = `<div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <div class="flex items-center gap-2 font-semibold text-purple-800 mb-2">
                <span>📝</span>
                <span>AI Summary</span>
            </div>
            <div class="text-sm text-gray-800 leading-relaxed">${escapeHtml(data.summary)}</div>
            <div class="text-xs text-gray-500 mt-2">Model: ${data.metadata.model} • Tokens: ${data.metadata.tokens_used.total}</div>
        </div>`;
  } catch (err) {
    container.innerHTML = `<div class="bg-red-50 text-red-700 rounded-lg px-4 py-3 text-sm font-medium">
            ❌ Error: ${escapeHtml(err.message)}
        </div>`;
  }
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

/* ---- Summarize Modal ---- */
const summarizeBtn = document.getElementById("summarizeBtn");
const summarizeModal = document.getElementById("summarizeModal");
const closeModal = document.getElementById("closeModal");
const cancelBtn = document.getElementById("cancelBtn");
const submitSummary = document.getElementById("submitSummary");
const textInput = document.getElementById("textInput");
const summaryResult = document.getElementById("summaryResult");
const summaryContent = document.getElementById("summaryContent");
const summaryStatus = document.getElementById("summaryStatus");

// Open modal
summarizeBtn.addEventListener("click", () => {
  summarizeModal.classList.remove("hidden");
  textInput.value = "";
  summaryResult.classList.add("hidden");
  summaryStatus.classList.add("hidden");
});

// Close modal functions
function closeModalFunc() {
  summarizeModal.classList.add("hidden");
}
closeModal.addEventListener("click", closeModalFunc);
cancelBtn.addEventListener("click", closeModalFunc);

// Close on backdrop click
summarizeModal.addEventListener("click", (e) => {
  if (e.target === summarizeModal) closeModalFunc();
});

// Submit for summary
submitSummary.addEventListener("click", async () => {
  const text = textInput.value.trim();
  if (!text) {
    showSummaryStatus("error", "⚠️ Please enter some text to summarize.");
    return;
  }

  submitSummary.disabled = true;
  summaryResult.classList.add("hidden");
  showSummaryStatus(
    "loading",
    '<span class="spinner"></span> Generating summary...',
  );

  try {
    const resp = await fetch("/api/summarize-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || "Summarization failed");
    }

    const data = await resp.json();
    summaryContent.textContent = data.summary;
    summaryResult.classList.remove("hidden");
    showSummaryStatus("success", "✅ Summary generated successfully!");
  } catch (err) {
    showSummaryStatus("error", `❌ Error: ${err.message}`);
  }

  submitSummary.disabled = false;
});

function showSummaryStatus(type, msg) {
  summaryStatus.className =
    `block rounded-lg px-4 py-3 text-sm font-medium` +
    (type === "loading"
      ? " bg-indigo-50 text-indigo-700"
      : type === "success"
        ? " bg-green-50 text-green-700"
        : type === "error"
          ? " bg-red-50 text-red-700"
          : "");
  summaryStatus.innerHTML = msg;
  summaryStatus.classList.remove("hidden");
}
