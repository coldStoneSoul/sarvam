/* ═══════════════════════════════════════════════════════════════
   CHAT SIDEBAR – Two modes: document & prediction context
   Relies on globals: extractedTextContent, currentPrediction, sendChatBtn
   ═══════════════════════════════════════════════════════════════ */

let currentChatContext = "";
let chatMode = "document";

const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

sendChatBtn.addEventListener("click", () => {
    if (chatInput.value.trim() !== "") sendMessage();
});

chatInput.addEventListener("keypress", async e => {
    if (e.key === "Enter" && chatInput.value.trim() !== "") sendMessage();
});

// ── Open with extracted document context ──
function openChatWithDoc() {
    chatMode = "document";
    currentChatContext = extractedTextContent;
    document.getElementById("chatModeLabel").textContent = "Context: Extracted Document";
    chatInput.placeholder = "Ask about this document...";
    chatMessages.innerHTML = '';
    appendMessage("ai", '👋 I have the extracted document loaded. Ask me anything about it!');
    document.getElementById("chatSidebar").classList.remove("translate-x-full");
}

// ── Open with prediction + document context ──
function openChatWithPrediction() {
    chatMode = "prediction";
    let ctx = "EXTRACTED DOCUMENT:\n" + extractedTextContent + "\n\n";
    if (currentPrediction) {
        ctx += "AI PREDICTION RESULTS:\n";
        ctx += "Settlement Probability: " + currentPrediction.probability + "%\n";
        ctx += "Priority: " + currentPrediction.priority + "\n";
        ctx += "Settlement Range: ₹" + currentPrediction.settle_min + " – ₹" + currentPrediction.settle_max + "\n";
        if (currentPrediction.deep_analysis) {
            ctx += "\nDEEP ANALYSIS:\n";
            currentPrediction.deep_analysis.forEach(item => {
                ctx += "- " + item.factor + " (" + item.impact + "): " + item.description + "\n";
            });
        }
        if (currentPrediction.legal_argumentation) {
            ctx += "\nLEGAL ARGUMENTATION:\n" + currentPrediction.legal_argumentation.legal_argument + "\n";
        }
        if (currentPrediction.negotiation_strategy) {
            const ns = currentPrediction.negotiation_strategy;
            ctx += "\nNEGOTIATION STRATEGY:\n";
            ctx += "Opening Offer: ₹" + ns.opening_offer + "\n";
            ctx += "Zone: " + ns.negotiation_zone + "\n";
        }
    }
    currentChatContext = ctx;
    document.getElementById("chatModeLabel").textContent = "Context: AI Analysis Results";
    chatInput.placeholder = "Ask about the analysis, strategy, or legal aspects...";
    chatMessages.innerHTML = '';
    appendMessage("ai", '📊 I have both the document and AI analysis loaded. Ask about the settlement probability, legal strategy, negotiation approach, or anything else!');
    document.getElementById("chatSidebar").classList.remove("translate-x-full");
}

// Legacy compat
function openChat() { openChatWithDoc(); }

function toggleChat() {
    document.getElementById("chatSidebar").classList.add("translate-x-full");
}

// ── Send message via /api/chat ──
async function sendMessage() {
    const userMsg = chatInput.value.trim();
    chatInput.value = "";
    appendMessage("user", userMsg);
    const loadingId = "loading-" + Date.now();
    appendMessage("ai", '<span class="spinner"></span> AI is thinking...', loadingId);

    try {
        const resp = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userMsg, context: currentChatContext }),
        });
        const data = await resp.json();
        document.getElementById(loadingId).innerHTML = marked.parse(data.response || data.error || "No response");
    } catch (err) {
        document.getElementById(loadingId).innerHTML = "❌ Error: " + err.message;
    }
}

function appendMessage(sender, text, id = null) {
    const msgDiv = document.createElement("div");
    msgDiv.className = sender === "user"
        ? "bg-indigo-100 text-indigo-900 p-3 rounded-lg self-end ml-8"
        : "bg-gray-100 text-gray-900 p-3 rounded-lg mr-8";
    if (id) msgDiv.id = id;
    msgDiv.innerHTML = text;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}
