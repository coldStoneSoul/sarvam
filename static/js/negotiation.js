/* ═══════════════════════════════════════════════════════════════
   MULTI-ROUND NEGOTIATION ENGINE (Frontend)
   Relies on globals: currentCaseData, currentPrediction
   ═══════════════════════════════════════════════════════════════ */

let currentNegSessionId = null;
let negRoundHistory = [];

async function startNegotiation() {
    const btn = document.getElementById("startNegotiationBtn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Starting…';

    try {
        const resp = await fetch('/api/negotiation/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                claim_amount: parseInt(String(currentCaseData.claim_amount).replace(/,/g, '')) || 100000,
                delay_days: parseInt(String(currentCaseData.delay_days).replace(/,/g, '')) || 90,
                document_count: parseInt(currentCaseData.document_count) || 1,
                dispute_type: currentCaseData.dispute_type || 'others',
                probability: currentPrediction ? currentPrediction.probability : 70
            })
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
            throw new Error(errData.error || `Server error ${resp.status}`);
        }

        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        currentNegSessionId = data.session_id;
        negRoundHistory = [data];

        document.getElementById("negotiationPanel").classList.remove("hidden");
        document.getElementById("negSessionBadge").textContent = "Session: " + data.session_id;
        renderNegotiationHistory();

        if (!data.is_final_round) {
            document.getElementById("negotiationActions").classList.remove("hidden");
        }

        btn.innerHTML = '<i class="fa-solid fa-handshake-angle"></i> Restart Negotiation';
    } catch (err) {
        showNegError("❌ Negotiation Error: " + err.message);
        btn.innerHTML = '<i class="fa-solid fa-handshake-angle"></i> Start Negotiation';
    }
    btn.disabled = false;
}

async function submitCounterOffer() {
    const input = document.getElementById("opponentCounterInput");
    const amount = parseInt(String(input.value).replace(/,/g, ''));
    if (!amount || amount <= 0) {
        showNegError("Please enter a valid counter-offer amount.");
        return;
    }

    const btn = document.getElementById("submitCounterBtn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';

    try {
        const resp = await fetch('/api/negotiation/continue', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentNegSessionId,
                opponent_offer: amount,
                message: ''
            })
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
            throw new Error(errData.error || `Server error ${resp.status}`);
        }

        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        negRoundHistory.push(data);
        input.value = '';
        renderNegotiationHistory();

        if (data.is_final_round || data.ultimatum) {
            document.getElementById("negotiationActions").classList.add("hidden");
        }
    } catch (err) {
        showNegError("❌ Error: " + err.message);
    }
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Submit';
}

function showNegError(msg) {
    const el = document.getElementById("step3Status");
    if (el) {
        el.className = "block rounded-lg px-4 py-3 mt-3 text-sm font-medium bg-red-50 text-red-700";
        el.textContent = msg;
        setTimeout(() => { el.className = "hidden"; }, 6000);
    }
}

function renderNegotiationHistory() {
    const container = document.getElementById("negotiationHistory");
    container.innerHTML = '';

    negRoundHistory.forEach((data, idx) => {
        const isLast = idx === negRoundHistory.length - 1;
        const roundLabel = data.round === "FINAL" ? "FINAL" : "Round " + data.round;
        const tacticName = data.tactic ? data.tactic.name : "N/A";
        const tacticDesc = data.tactic ? data.tactic.desc : "";

        let cardClass = isLast ? "border-amber-400 bg-white" : "border-gray-200 bg-gray-50";
        if (data.ultimatum) cardClass = "border-red-400 bg-red-50";

        let html = `<div class="neg-round-card border-2 ${cardClass} rounded-lg p-4 transition-all">`;

        // Header
        html += `<div class="flex items-center justify-between mb-2">`;
        html += `<span class="text-xs font-bold px-2 py-0.5 rounded-full ${data.ultimatum ? 'bg-red-200 text-red-800' : 'bg-amber-200 text-amber-800'}">${roundLabel}</span>`;
        html += `<span class="text-xs font-semibold text-gray-600">${tacticName}</span>`;
        html += `</div>`;

        // Offer
        html += `<div class="flex items-center gap-3 mb-2">`;
        html += `<div class="flex-1">`;
        html += `<p class="text-[10px] uppercase tracking-wider text-gray-500 font-bold">Our Offer</p>`;
        html += `<p class="text-lg font-bold text-green-700">₹${data.our_offer ? data.our_offer.toLocaleString() : '0'}</p>`;
        html += `</div>`;
        if (data.offer_percentage) {
            html += `<span class="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full font-semibold">${data.offer_percentage}% of claim</span>`;
        }
        html += `</div>`;

        // Tactic description
        if (tacticDesc) {
            html += `<p class="text-xs text-gray-500 italic mb-2">${tacticDesc}</p>`;
        }

        // Rationale 
        const message = data.polished_message || data.rationale || '';
        if (message) {
            html += `<div class="bg-slate-50 border-l-4 border-l-amber-400 rounded p-3 text-xs text-gray-700 mb-2">${message}</div>`;
        }

        // Gap analysis
        if (data.gap_analysis) {
            html += `<div class="flex items-center gap-2 text-xs">`;
            html += `<span class="px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full font-semibold">Gap: ${data.gap_analysis.assessment}</span>`;
            if (data.gap_analysis.percentage) {
                html += `<span class="text-gray-400">(${data.gap_analysis.percentage}%)</span>`;
            }
            html += `</div>`;
        }

        // Ultimatum warning
        if (data.ultimatum || data.is_final_round) {
            html += `<div class="mt-2 bg-red-100 border border-red-300 rounded-lg p-2 text-xs text-red-700 font-semibold text-center">`;
            html += `⚠️ FINAL OFFER — Escalation to ${data.escalation_path || 'MSEFC'} imminent`;
            html += `</div>`;
        }

        // Escalation warning
        if (data.escalation_warning && !data.is_final_round) {
            html += `<div class="mt-2 text-xs text-amber-600 font-semibold">⚠ Approaching final round — escalation likely</div>`;
        }

        html += `</div>`;
        container.innerHTML += html;

        // Show suggested moves for the last round
        if (isLast && data.next_moves && data.next_moves.length && !data.is_final_round) {
            const movesContainer = document.getElementById("suggestedMovesContainer");
            const movesDiv = document.getElementById("suggestedMoves");
            movesContainer.classList.remove("hidden");
            movesDiv.innerHTML = data.next_moves.map(m =>
                `<span class="text-xs px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-full text-blue-700 font-medium cursor-default" title="${m.action || ''}">${m.description || m.action}</span>`
            ).join('');
        }
    });

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;

    // Auto-scroll panel into view
    document.getElementById("negotiationPanel").scrollIntoView({ behavior: "smooth", block: "end" });
}
