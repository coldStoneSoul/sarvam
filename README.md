# MSME Negotiation AI

An AI-powered decision support system designed to assist Micro, Small, and Medium Enterprises (MSMEs) in resolving payment disputes. It leverages machine learning (XGBoost) for settlement prediction, IBM Granite LLMs for document extraction and legal argumentation, and deterministic rule engines for statutory compliance and negotiation.

## Key Features

1.  **AI Document Extraction (Docling + IBM Granite)**: Upload legal notices, invoices, or POs. The system uses Docling (by IBM) for OCR-based document parsing and IBM Granite (via Docker Model Runner) for two-pass extraction and validation of case fields.
2.  **Predictive Settlement Modeling (XGBoost)**: A model trained on synthetic MSME cases predicts the likelihood of settlement based on case features and outputs SHAP-style feature contributions.
3.  **Statutory Compliance Engine**: Deterministically calculates entitlements under Sections 15 & 16 of the MSME Act, 2006 (including monthly compound interest at 3x the RBI bank rate).
4.  **Multi-Round Negotiation Assistant**: A rule-based 5-round negotiation engine with tactic suggestions, gap analysis, and fallback to MSEFC escalation threats.
5.  **Legal Argumentation & Rebuttal**: Automatically generates counter-arguments based on the dispute type and scores evidence strength.
6.  **Automated PDF Drafting**: Generates professional, compliant settlement drafts and analysis reports ready for download.
7.  **Audit Logging**: Every prediction is logged to `logs/prediction_audit.jsonl` with a unique Case ID for traceability.
8.  **Fully Local Execution**: Uses Docker Desktop's built-in Model Runner with IBM Granite models for complete data privacy — no data leaves your machine.

## User Flows

### 1. Document Wizard Flow (`/`)
Ideal for users with physical documents (PDFs, DOCX).
- **Upload**: User uploads a document.
- **Extract**: System extracts case fields via Docling OCR and IBM Granite LLM (two-pass: extract → validate).
- **Review/Predict**: User verifies fields, system runs XGBoost prediction.
- **Draft**: System generates settlement draft and analysis reports.

### 2. Direct Input Flow (`/schema`)
Ideal for quick, manual entry.
- **Input**: User fills out the form manually.
- **Predict**: System runs XGBoost prediction.
- **Export**: User downloads the analysis report or settlement draft.

## Architecture

*   **Frontend**: HTML, CSS, Vanilla JS (`templates/`, `static/`)
*   **Backend**: Flask (`flask_app.py`)
*   **Machine Learning**: XGBoost (`services/prediction.py`, `model/`)
*   **Foundation Model**: IBM Granite — via Docker Model Runner (OpenAI-compatible API, fully local)
*   **Document Intelligence**: Docling by IBM with RapidOCR GPU backend (`services/document.py`)
*   **Statutory Engine**: `services/settlement_drafter.py`, `services/legal_knowledge.py`
*   **Negotiation Engine**: `services/negotiation_engine.py`

## Setup and Installation

### Prerequisites
*   Python 3.8+
*   Docker Desktop (with Model Runner enabled under Settings → AI)

### 1. Start the Local LLM (Docker Desktop Model Runner)
Docker Desktop's built-in Model Runner runs IBM Granite locally on port `12434`.
Enable it under **Docker Desktop → Settings → AI → Enable Model Runner**, then models are managed via the Docker Desktop GUI or the API:
```bash
# Verify models are available
curl http://localhost:12434/v1/models
```

### 2. Install Python Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY="not-needed-for-local"

# IBM Granite model for chat and analysis (reasoning tasks)
MODEL_FOR_CHAT=ai/granite-4.0-h-micro
MODEL_FOR_ANALYSIS=ai/granite-4.0-h-micro

# Smaller Granite model for fast summarization
MODEL_FOR_SUMMARIZE=ai/granite-4.0-h-nano:350M-Q8_0

BASE_URL=http://localhost:12434/v1
```

### 4. Run the Application
```bash
python flask_app.py
```
Access the application at `http://localhost:5000`.

## API Endpoints

*   `POST /api/extract-fields`: Extracts case data from uploaded documents.
*   `POST /api/predict`: Runs XGBoost prediction on case fields.
*   `POST /api/generate-draft`: Generates the statutory settlement draft.
*   `POST /api/negotiation/start`: Initializes a new multi-round negotiation session.
*   `POST /api/negotiation/continue`: Processes a counter-offer in an active session.
*   `POST /api/export-pdf`: Exports the analysis report.
*   `POST /api/export-settlement-pdf`: Exports the settlement draft.
*   `POST /api/chat`: Chat specifically about the provided document context.

## Logs
Prediction audit logs are stored in `logs/prediction_audit.jsonl`.

