# 🪟 Windows Setup Guide — MSME Negotiation AI

> This guide walks you through running the MSME Negotiation AI project on a Windows machine from scratch.
> The project uses **two AI systems**: IBM Granite (via Docker Model Runner) for reasoning, and **Docling** for document OCR/parsing.

---

## Prerequisites

| Tool | Minimum Version | Download |
|---|---|---|
| Python | 3.10+ | https://www.python.org/downloads/ |
| Git | Any | https://git-scm.com/download/win |
| Docker Desktop | 4.30+ | https://www.docker.com/products/docker-desktop |
| WSL2 (Windows Subsystem for Linux) | Required for Docker | Enabled via PowerShell (see below) |

> **GPU Note:** An NVIDIA GPU is strongly recommended for running the Granite models at usable speed. CPU-only inference on the `h-micro` model will be very slow.

---

## Step 1 — Install Python

1. Download Python 3.10+ from https://www.python.org/downloads/
2. During installation, **check the box**: ✅ `Add Python to PATH`
3. Verify installation by opening **Command Prompt** and running:
   ```cmd
   python --version
   pip --version
   ```

---

## Step 2 — Enable WSL2 (Required for Docker)

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

Restart your machine when prompted. After reboot, WSL2 will be ready.

---

## Step 3 — Install Docker Desktop

1. Download from https://www.docker.com/products/docker-desktop
2. During installation, make sure **"Use WSL2 instead of Hyper-V"** is selected
3. Launch Docker Desktop and wait for it to fully start (whale icon in taskbar turns steady)
4. Go to **Settings → Resources → WSL Integration** and enable it for your distro

---

## Step 4 — Set Up IBM Granite Models (Docker Model Runner)

The project uses IBM Granite models served via Docker's built-in Model Runner on port `12434`.

### 4a. Enable Model Runner in Docker Desktop

Open Docker Desktop → **Settings → Features in development** → enable **"Docker Model Runner"** → Apply & Restart.

### 4b. Pull the Granite Models

Open **Command Prompt** or **PowerShell** and run:

```cmd
docker model pull ai/granite-4.0-h-micro
docker model pull ai/granite-4.0-h-nano:350M-Q8_0
```

> Downloading may take a few minutes depending on your internet speed.

### 4c. Verify the Models are Running

```cmd
docker model ls
```

You should see both `granite-4.0-h-micro` and `granite-4.0-h-nano` listed.

The model runner API will be available at:
```
http://localhost:12434/v1
```
This matches the `BASE_URL` in your `.env` file — no changes needed.

---

## Step 5 — Clone & Set Up the Project

### 5a. Clone the repository

```cmd
git clone <your-repo-url>
cd sarvam
```

### 5b. Create a virtual environment

```cmd
python -m venv venv
```

### 5c. Activate the virtual environment

```cmd
venv\Scripts\activate
```

> You should see `(venv)` appear at the start of your command prompt line.

### 5d. Install dependencies

```cmd
pip install -r requirements.txt
```

> **Note:** `docling` will automatically install its OCR dependencies on Windows. This may take several minutes on first install.

---

## Step 6 — Configure the `.env` File

Create a `.env` file in the project root (copy from the example if provided, or create it fresh):

```env
OPENAI_API_KEY="not-needed"

# Chat: conversational assistant
MODEL_FOR_CHAT=ai/granite-4.0-h-micro

# Analysis: legal extraction + reasoning (needs stronger model)
MODEL_FOR_ANALYSIS=ai/granite-4.0-h-micro

# Summarize: fast bulk text tasks (nano is enough)
MODEL_FOR_SUMMARIZE=ai/granite-4.0-h-nano:350M-Q8_0

BASE_URL=http://localhost:12434/v1
```

> The `OPENAI_API_KEY` can be set to any non-empty string since the project uses Docker Model Runner locally (not OpenAI's servers).

---

## Step 7 — Run the Application

Make sure your virtual environment is activated (`venv\Scripts\activate`), then:

```cmd
python flask_app.py
```

Open your browser and go to:
```
http://localhost:5000
```

---

## AI Architecture Summary

```
┌─────────────────────────────────────────────────┐
│              MSME Negotiation AI                │
├──────────────────┬──────────────────────────────┤
│   DOCLING (OCR)  │   IBM GRANITE (Reasoning)    │
│                  │                              │
│  Reads uploaded  │  granite-4.0-h-micro:        │
│  PDFs, DOCX,     │  → Legal field extraction    │
│  images, PPTX    │  → Case validation           │
│                  │  → Chat assistant            │
│  Pure Python lib │  → Settlement drafting       │
│  No extra setup  │                              │
│  needed          │  granite-4.0-h-nano:         │
│                  │  → Fast summarization        │
│                  │  → Key point extraction      │
│                  │                              │
│                  │  Served via Docker Model     │
│                  │  Runner at localhost:12434   │
└──────────────────┴──────────────────────────────┘
```

---

## Troubleshooting

### ❌ `python` not found
Make sure you checked **"Add Python to PATH"** during installation. If not, reinstall Python or add it manually to your system PATH.

### ❌ `venv\Scripts\activate` fails in PowerShell
Run this first to allow script execution:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ❌ Docker Model Runner not available
Ensure Docker Desktop is at version **4.30+** and the **"Docker Model Runner"** feature is enabled in Settings → Features in development.

### ❌ Models not loading / API returns 404
Check that Docker Desktop is running and models are pulled:
```cmd
docker model ls
```
If empty, re-run the `docker model pull` commands from Step 4b.

### ❌ Docling OCR fails on certain PDFs
Docling uses `pypdfium2` on Windows which is fully supported. If you encounter issues with scanned PDFs, ensure the file is not password-protected.

### ❌ Very slow inference
Running `granite-4.0-h-micro` on CPU only will be slow. For best performance, ensure Docker Desktop has access to your NVIDIA GPU (Settings → Resources → GPU).

---

## Quick Reference Commands

```cmd
# Activate virtual environment
venv\Scripts\activate

# Run the app
python flask_app.py

# Check Granite models
docker model ls

# Pull models (if missing)
docker model pull ai/granite-4.0-h-micro
docker model pull ai/granite-4.0-h-nano:350M-Q8_0

# Deactivate virtual environment
deactivate
```

---

*Generated for MSME Negotiation AI — Team Lotus*
