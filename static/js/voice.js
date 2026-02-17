/* ═══════════════════════════════════════════════════════════════
   VOICE INPUT MANAGER – ASR/TTS for automated form population
   Uses Web Speech API with fallback to MediaRecorder + server
   ═══════════════════════════════════════════════════════════════ */

class VoiceInputManager {
    constructor() {
        this.recognition = null;
        this.isRecording = false;
        this.targetField = null;
        this.fallbackMode = false;
        this.mediaRecorder = null;
        this.audioChunks = [];

        // Check browser support
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-IN';  // Default: Indian English
        } else {
            this.fallbackMode = true;
        }
    }

    // Start recording for specific field
    startRecording(fieldId, fieldType) {
        // If already recording, stop first
        if (this.isRecording) {
            this.stopRecording();
            return;
        }

        if (this.fallbackMode) {
            this.startFallbackRecording(fieldId, fieldType);
            return;
        }

        if (!this.recognition) {
            this._showVoiceToast('Voice input not supported. Use text entry.', 'error');
            return;
        }

        this.targetField = document.getElementById(fieldId);
        this.isRecording = true;

        // Update mic button UI
        const micBtn = document.getElementById(`${fieldId}-mic`);
        if (micBtn) {
            micBtn.classList.add('recording');
            micBtn.title = 'Click to stop recording';
        }

        // Show listening indicator
        this._showVoiceToast('🎤 Listening…', 'info');

        // Configure language
        this.recognition.lang = this._detectLanguage();

        this.recognition.onresult = (event) => {
            const result = event.results[0];
            const transcript = result[0].transcript;

            // Show interim results in real-time
            if (this.targetField) {
                const processed = this._processTranscript(transcript, fieldType, fieldId);
                this.targetField.value = processed;
            }

            // Final result
            if (result.isFinal) {
                const processed = this._processTranscript(transcript, fieldType, fieldId);
                if (this.targetField) {
                    this.targetField.value = processed;
                    this.targetField.dispatchEvent(new Event('input', { bubbles: true }));
                    this.targetField.dispatchEvent(new Event('change', { bubbles: true }));
                }
                this._showVoiceToast(`✅ Captured: "${transcript}"`, 'success');
            }
        };

        this.recognition.onerror = (event) => {
            console.error('Speech error:', event.error);
            let msg = 'Voice input error.';
            if (event.error === 'not-allowed') msg = '🔇 Microphone access denied. Please allow in browser settings.';
            else if (event.error === 'no-speech') msg = '🔇 No speech detected. Try again.';
            else if (event.error === 'network') msg = '🌐 Network error. Check connection.';
            this._showVoiceToast(msg, 'error');
            this.stopRecording();
        };

        this.recognition.onend = () => {
            this.stopRecording();
        };

        try {
            this.recognition.start();
        } catch (e) {
            console.error('Recognition start failed:', e);
            this.stopRecording();
        }
    }

    stopRecording() {
        this.isRecording = false;
        if (this.recognition) {
            try { this.recognition.stop(); } catch (e) { /* already stopped */ }
        }
        // Remove recording UI state from all mic buttons
        document.querySelectorAll('.voice-mic-btn').forEach(btn => {
            btn.classList.remove('recording');
            btn.title = 'Click to record voice input';
        });
    }

    _detectLanguage() {
        const langSelector = document.getElementById('voiceLanguageSelect');
        return langSelector ? langSelector.value : 'en-IN';
    }

    _processTranscript(text, fieldType, fieldId) {
        switch (fieldType) {
            case 'amount':
                return this._extractAmount(text);

            case 'days':
                return this._textToNumber(text);

            case 'dispute_type':
                const mapped = this._mapDisputeType(text.toLowerCase());
                // For select fields, set selectedIndex
                const selectEl = document.getElementById(fieldId);
                if (selectEl && selectEl.tagName === 'SELECT') {
                    for (let i = 0; i < selectEl.options.length; i++) {
                        if (selectEl.options[i].value === mapped) {
                            selectEl.selectedIndex = i;
                            selectEl.dispatchEvent(new Event('change', { bubbles: true }));
                            break;
                        }
                    }
                }
                return mapped;

            case 'jurisdiction':
                const state = this._extractState(text);
                const jSelectEl = document.getElementById(fieldId);
                if (jSelectEl && jSelectEl.tagName === 'SELECT') {
                    for (let i = 0; i < jSelectEl.options.length; i++) {
                        if (jSelectEl.options[i].value.toLowerCase().includes(state.toLowerCase())) {
                            jSelectEl.selectedIndex = i;
                            jSelectEl.dispatchEvent(new Event('change', { bubbles: true }));
                            break;
                        }
                    }
                }
                return state;

            case 'select':
                // Generic select — find best match
                const sel = document.getElementById(fieldId);
                if (sel && sel.tagName === 'SELECT') {
                    const lower = text.toLowerCase();
                    for (let i = 0; i < sel.options.length; i++) {
                        if (sel.options[i].text.toLowerCase().includes(lower) ||
                            sel.options[i].value.toLowerCase().includes(lower)) {
                            sel.selectedIndex = i;
                            sel.dispatchEvent(new Event('change', { bubbles: true }));
                            return sel.options[i].value;
                        }
                    }
                }
                return text;

            case 'full_case':
            default:
                return text;
        }
    }

    _extractAmount(text) {
        // Handle "five lakh" "5 lakh" "500000" etc.
        const lakhMatch = text.match(/(\d+)\s*(lakh|lac)/i);
        if (lakhMatch) return String(parseInt(lakhMatch[1]) * 100000);

        const croreMatch = text.match(/(\d+)\s*crore/i);
        if (croreMatch) return String(parseInt(croreMatch[1]) * 10000000);

        const thousandMatch = text.match(/(\d+)\s*thousand/i);
        if (thousandMatch) return String(parseInt(thousandMatch[1]) * 1000);

        // Just extract digits
        const digits = text.replace(/[^0-9]/g, '');
        return digits || text;
    }

    _textToNumber(text) {
        const numberWords = {
            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
            'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
            'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
            'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90, 'hundred': 100,
            'thousand': 1000
        };

        let total = 0;
        let current = 0;
        const words = text.toLowerCase().split(/\s+/);

        words.forEach(word => {
            // Try direct digit extraction
            const digits = word.replace(/\D/g, '');
            if (digits) {
                current += parseInt(digits);
                return;
            }
            // Word-to-number
            if (numberWords[word] !== undefined) {
                if (word === 'hundred') {
                    current = (current || 1) * 100;
                } else if (word === 'thousand') {
                    current = (current || 1) * 1000;
                } else {
                    current += numberWords[word];
                }
            }
        });

        total += current;
        return total > 0 ? String(total) : text;
    }

    _mapDisputeType(text) {
        const mappings = {
            'goods': 'goods_rejection',
            'quality': 'goods_rejection',
            'reject': 'goods_rejection',
            'defective': 'goods_rejection',
            'service': 'service_non_payment',
            'work': 'service_non_payment',
            'labor': 'service_non_payment',
            'invoice': 'invoice_non_payment',
            'bill': 'invoice_non_payment',
            'payment': 'invoice_non_payment',
            'short': 'short_payment',
            'partial': 'short_payment',
            'less': 'short_payment',
            'interest': 'interest_on_delay',
            'delay': 'interest_on_delay',
            'late': 'interest_on_delay',
            'penalty': 'interest_on_delay'
        };

        for (const [keyword, type] of Object.entries(mappings)) {
            if (text.includes(keyword)) return type;
        }
        return 'others';
    }

    _extractState(text) {
        const states = [
            'andhra pradesh', 'arunachal pradesh', 'assam', 'bihar', 'chhattisgarh',
            'goa', 'gujarat', 'haryana', 'himachal pradesh', 'jharkhand',
            'karnataka', 'kerala', 'madhya pradesh', 'maharashtra', 'manipur',
            'meghalaya', 'mizoram', 'nagaland', 'odisha', 'punjab',
            'rajasthan', 'sikkim', 'tamil nadu', 'telangana', 'tripura',
            'uttar pradesh', 'uttarakhand', 'west bengal',
            'delhi', 'chandigarh', 'puducherry', 'jammu and kashmir', 'ladakh'
        ];

        const lowerText = text.toLowerCase();
        for (const state of states) {
            if (lowerText.includes(state)) {
                return state.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            }
        }
        return text;
    }

    // ── Fallback: MediaRecorder + server transcription ──
    async startFallbackRecording(fieldId, fieldType) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];
            this.isRecording = true;

            const micBtn = document.getElementById(`${fieldId}-mic`);
            if (micBtn) micBtn.classList.add('recording');
            this._showVoiceToast('🎤 Recording… (max 10s)', 'info');

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = async () => {
                stream.getTracks().forEach(t => t.stop());
                this.stopRecording();

                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                await this._sendToServer(audioBlob, fieldId, fieldType);
            };

            this.mediaRecorder.start();

            // Auto-stop after 10 seconds
            setTimeout(() => {
                if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
                    this.mediaRecorder.stop();
                }
            }, 10000);

        } catch (err) {
            console.error('Microphone access denied:', err);
            this._showVoiceToast('🔇 Microphone access denied. Please allow or type manually.', 'error');
            this.stopRecording();
        }
    }

    async _sendToServer(audioBlob, fieldId, fieldType) {
        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');

            const response = await fetch('/api/transcribe-voice', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            if (result.text) {
                const processed = this._processTranscript(result.text, fieldType, fieldId);
                const field = document.getElementById(fieldId);
                if (field) {
                    field.value = processed;
                    field.dispatchEvent(new Event('input', { bubbles: true }));
                }
                this._showVoiceToast(`✅ Transcribed: "${result.text}"`, 'success');
            } else if (result.fallback) {
                this._showVoiceToast('⚠️ Server transcription not available. Web Speech API recommended.', 'error');
            }
        } catch (err) {
            this._showVoiceToast('❌ Transcription failed: ' + err.message, 'error');
        }
    }

    _showVoiceToast(message, type) {
        // Remove existing toast
        const existing = document.getElementById('voiceToast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.id = 'voiceToast';
        toast.className = `voice-toast voice-toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => toast.classList.add('show'));

        // Auto-remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }
}

// ── Initialize ──
const voiceManager = new VoiceInputManager();

// ── Add mic buttons to form fields ──
function addVoiceButtons() {
    const fields = [
        { id: 'edit_claim_amount', type: 'amount', label: 'Claim Amount' },
        { id: 'edit_delay_days', type: 'days', label: 'Delay Days' },
        { id: 'edit_document_count', type: 'select', label: 'Document Count' },
        { id: 'edit_dispute_type', type: 'dispute_type', label: 'Dispute Type' },
        { id: 'edit_jurisdiction', type: 'jurisdiction', label: 'Jurisdiction' }
    ];

    fields.forEach(field => {
        const inputEl = document.getElementById(field.id);
        if (!inputEl) return;

        // Skip if mic button already exists
        if (document.getElementById(`${field.id}-mic`)) return;

        // Create mic button
        const micBtn = document.createElement('button');
        micBtn.type = 'button';
        micBtn.className = 'voice-mic-btn';
        micBtn.id = `${field.id}-mic`;
        micBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
        micBtn.title = `Voice input for ${field.label}`;
        micBtn.onclick = (e) => {
            e.preventDefault();
            voiceManager.startRecording(field.id, field.type);
        };

        // Wrap input + mic in a flex container
        const wrapper = document.createElement('div');
        wrapper.className = 'voice-input-wrapper';
        inputEl.parentNode.insertBefore(wrapper, inputEl);
        wrapper.appendChild(inputEl);
        wrapper.appendChild(micBtn);
    });

    // Add language selector to the Step 2 header area
    const step2 = document.getElementById('step2');
    if (step2 && !document.getElementById('voiceLanguageSelect')) {
        const headerDiv = step2.querySelector('.flex.items-center.justify-between');
        if (headerDiv) {
            const langContainer = document.createElement('div');
            langContainer.className = 'flex items-center gap-2';
            langContainer.innerHTML = `
        <label class="text-xs text-gray-500 flex items-center gap-1">
          <i class="fa-solid fa-language text-indigo-500"></i> Voice:
        </label>
        <select id="voiceLanguageSelect"
          class="text-xs px-2 py-1 border border-gray-200 rounded-md focus:ring-1 focus:ring-indigo-500 bg-white">
          <option value="en-IN">English (India)</option>
          <option value="hi-IN">हिन्दी (Hindi)</option>
          <option value="mr-IN">मराठी (Marathi)</option>
          <option value="ta-IN">தமிழ் (Tamil)</option>
          <option value="te-IN">తెలుగు (Telugu)</option>
          <option value="kn-IN">ಕನ್ನಡ (Kannada)</option>
          <option value="gu-IN">ગુજરાતી (Gujarati)</option>
          <option value="bn-IN">বাংলা (Bengali)</option>
          <option value="ml-IN">മലയാളം (Malayalam)</option>
          <option value="pa-IN">ਪੰਜਾਬੀ (Punjabi)</option>
        </select>
      `;

            // Insert the back button separately and add lang before it
            const backBtn = headerDiv.querySelector('button');
            if (backBtn) {
                const rightGroup = document.createElement('div');
                rightGroup.className = 'flex items-center gap-3';
                rightGroup.appendChild(langContainer);
                rightGroup.appendChild(backBtn.cloneNode(true));
                // Copy onclick
                rightGroup.querySelector('button').onclick = backBtn.onclick;
                headerDiv.replaceChild(rightGroup, backBtn);
            } else {
                headerDiv.appendChild(langContainer);
            }
        }
    }
}

// Initialize voice buttons when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addVoiceButtons);
} else {
    // DOM already loaded (script loaded with defer or at bottom)
    addVoiceButtons();
}

// Re-add buttons when navigating to Step 2 (in case DOM was updated)
// Hook into goToStep
const _originalGoToStep = typeof goToStep === 'function' ? goToStep : null;
if (_originalGoToStep) {
    goToStep = function (n) {
        _originalGoToStep(n);
        if (n === 2) {
            setTimeout(addVoiceButtons, 100);
        }
    };
}
