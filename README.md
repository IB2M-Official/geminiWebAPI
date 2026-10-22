# Gemini Web-UI Automation Wrapper (Extended Edition)

> **Base Repository & Credits**: This project is built upon the open-source repository [`czarflix/GeminiCustomAPI`](https://github.com/czarflix/GeminiCustomAPI) (MIT License, Copyright (c) 2025 Gemini Custom API Contributors).  
> All credits for the original Playwright browser lifecycle architecture go to the original author.

This extension provides an **ultra-lightweight, universal, and fast** automation wrapper for Google Gemini Web, supporting image generation, vision analysis, and multimodal image editing (Image-to-Image / Prompt-to-Image) without requiring heavy dependencies.

---

## 🚀 Key Features Added

### 1. Universal Multimodal Support (3 Seamless Modes)
* **Case 1 (Prompt only):** Input prompt into Gemini -> Automatic generation of the image (or text response) saved directly to disk.
* **Case 2 (Image only):** Upload image to Gemini UI -> Send without text prompt -> Retrieve image response or analysis.
* **Case 3 (Image + Prompt):** Upload input image **AND** enter instruction prompt (e.g. *"transform this photo into anime manga style"*) -> Send -> Automatically extract and save the edited image.

### 2. Minimalist Interfaces (Node.js & Python)
* **Ultra-Fast Node.js CLI:**
  ```bash
  node index.js --prompt "a cute cat in 3D render style" --image "./input.png" --out "./output.png"
  ```
* **Minimalist Express Web Server:**
  A single file offering a `POST /` endpoint accepting prompt and/or image file, directly returning the binary image stream:
  ```bash
  node index.js --server --port 3000
  ```
* **Python CLI & API (Full Parity):**
  ```bash
  python cli.py --prompt "a cute cat" --image "./input.png" --out "./output.png"
  ```
  The original FastAPI server (`python main.py`) also includes the `POST /` binary image endpoint.

### 3. Persistent Chromium Session (`user_data` / `storage`)
The browser profile is stored locally. You only log in to your Google account **once**. All subsequent CLI commands and API calls reuse this authenticated session without needing to log in again.

---

## 📦 Installation

### Option A: Node.js Environment (Recommended for `node index.js`)

1. Install dependencies:
```bash
npm install
```
2. Install Chromium for Playwright (if not already installed):
```bash
npx playwright install chromium
```

### Option B: Python Environment

1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```
2. Copy configuration file:
```bash
cp .env.example .env
```

---

## 🔑 Initial Setup (One-Time Login)

Launch the login helper to open a visible browser window:

* **Using Node.js:**
  ```bash
  npm run login
  # or
  node index.js --login
  ```
* **Using Python:**
  ```bash
  python login_helper.py
  ```

Log in to your Google account and verify that the Gemini chat interface loads, then close the browser. Your session is safely stored in `./storage/playwright_profile` or `./user_data`.

---

## 💻 CLI Usage

### Case 1: Prompt Only (Image or Text Generation)
```bash
node index.js --prompt "An astronaut exploring a fluorescent alien jungle" --out "./mars.png"
```
*(or with Python: `python cli.py --prompt "..." --out "./mars.png"`)*

### Case 2: Image Only (Direct Upload Without Prompt)
```bash
node index.js --image "./photo.png" --out "./result.png"
```
*(or with Python: `python cli.py --image "./photo.png" --out "./result.png"`)*

### Case 3: Image + Prompt (Image Edition / Modification)
```bash
node index.js --image "./portrait.png" --prompt "transform this photo into anime cyberpunk style" --out "./cyberpunk.png"
```
*(or with Python: `python cli.py --image "./portrait.png" --prompt "..." --out "./cyberpunk.png"`)*

### CLI Options
| Option | Shorthand | Description | Default |
|---|---|---|---|
| `--prompt` | `-p` | Text prompt or instruction | `null` |
| `--image` | `-i` | Local input image path | `null` |
| `--out` | `-o` | Output file path | `./output.png` |
| `--server` | `-s` | Start the lightweight Express server | `false` |
| `--port` | | Server port | `3000` |
| `--no-headless` | `--headful` | Run browser in visible mode (for debugging) | `headless` |
| `--login` | | Open browser to authenticate with Google | |

---

## 🌐 Web Server Usage (Minimalist `POST /` Endpoint)

### Start the Express Server (Node.js):
```bash
node index.js --server --port 3000
```

### Start the FastAPI Server (Python):
```bash
python main.py
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Making Requests with cURL (Direct Binary Image Response):
```bash
# Case 3: Image + Prompt
curl -X POST http://localhost:3000/ \
  -F "prompt=transform this photo into watercolor painting style" \
  -F "image=@./portrait.png" \
  --output ./watercolor.png

# Case 1: Prompt only
curl -X POST http://localhost:3000/ \
  -F "prompt=futuristic cityscape under neon rain" \
  --output ./city.png

# Case 2: Image only
curl -X POST http://localhost:3000/ \
  -F "image=@./source.png" \
  --output ./result.png
```

---

## 📁 Project Structure

```
.
├── index.js                 # Universal Node.js entry point (CLI + Optional Express server)
├── login.js                 # Node.js login shortcut
├── cli.py                   # Python CLI entry point
├── package.json             # Node.js dependencies (Playwright, Express, Multer)
├── app/
│   ├── main.py              # FastAPI app (includes POST / binary route)
│   ├── gemini_automation.py # Core Playwright automation (3 cases & image extraction)
│   ├── browser_manager.py   # Persistent browser lifecycle manager
│   ├── models.py            # Pydantic models for FastAPI
│   └── config.py            # Environment configuration
├── login_helper.py          # Python one-time login script
├── test_api.py              # API test script
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── LICENSE                  # Original MIT License
└── README.md                # Comprehensive documentation
```

---

## ⚖️ License & Attribution

This project retains the original **MIT License**:
* Original project: [`czarflix/GeminiCustomAPI`](https://github.com/czarflix/GeminiCustomAPI)
* Authors: Czarflix & Gemini Custom API contributors
* Copyright (c) 2025 Gemini Custom API Contributors

*Disclaimer: This tool automates the Google Gemini web interface for personal and experimental use. It is not affiliated with or endorsed by Google.*
