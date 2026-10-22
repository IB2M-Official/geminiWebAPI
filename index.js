#!/usr/bin/env node
/**
 * Gemini Web Automation - Lightweight Node.js / Playwright Wrapper
 * 
 * Based on czarflix/GeminiCustomAPI (Playwright Persistent Context Architecture)
 * Supports:
 *   - Case 1: Text prompt only -> Image or Text generation
 *   - Case 2: Image only -> Upload & Gemini processing without text
 *   - Case 3: Image + Prompt -> Image edition / multimodal transformation (e.g. "convert to manga")
 * 
 * Usage:
 *   CLI:
 *     node index.js --prompt "un chat mignon style 3d" --out "./output.png"
 *     node index.js --image "./input.png" --out "./output.png"
 *     node index.js --prompt "transforme en style manga" --image "./input.png" --out "./output.png"
 *     node index.js --login
 * 
 *   Server (Express option):
 *     node index.js --server --port 3000
 *     curl -X POST http://localhost:3000/ -F "prompt=un chat" -F "image=@./input.png" --output ./result.png
 */

const fs = require('fs');
const path = require('path');

// Lazy-loaded dependencies
let playwright = null;
function getPlaywright() {
  if (!playwright) {
    try {
      playwright = require('playwright');
    } catch (e) {
      console.error('Playwright not found. Please install dependencies by running: npm install');
      process.exit(1);
    }
  }
  return playwright;
}

// --- Configuration & Paths ---
const DEFAULT_GEMINI_URL = 'https://gemini.google.com/app';
const STORAGE_DIR = fs.existsSync(path.resolve('./storage/playwright_profile'))
  ? path.resolve('./storage/playwright_profile')
  : path.resolve('./user_data');

// --- Helper: Parse CLI Arguments ---
function parseArgs() {
  const args = process.argv.slice(2);
  const params = {
    prompt: null,
    image: null,
    out: './output.png',
    headless: true,
    login: false,
    server: false,
    port: 3000,
    model: 'gemini-2.5-flash', // fast default
    timeout: 120000 // 2 minutes max
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--prompt' || arg === '-p') params.prompt = args[++i];
    else if (arg === '--image' || arg === '-i') params.image = args[++i];
    else if (arg === '--out' || arg === '-o') params.out = args[++i];
    else if (arg === '--port') params.port = parseInt(args[++i], 10);
    else if (arg === '--model' || arg === '-m') params.model = args[++i];
    else if (arg === '--timeout') params.timeout = parseInt(args[++i], 10);
    else if (arg === '--headless') params.headless = true;
    else if (arg === '--headful' || arg === '--no-headless') params.headless = false;
    else if (arg === '--login') params.login = true;
    else if (arg === '--server' || arg === '-s') params.server = true;
    else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    }
  }

  return params;
}

function printHelp() {
  console.log(`
Gemini Web Automation (Playwright Lightweight Wrapper)
------------------------------------------------------
Options:
  --prompt, -p <text>     Text prompt (Prompt seul ou instruction avec image)
  --image, -i  <path>     Input image path (Image seule ou image source à modifier)
  --out, -o    <path>     Output file path (default: ./output.png)
  --login                 Open browser to authenticate your Google session
  --server, -s            Launch lightweight Express HTTP server
  --port <num>            Server port (default: 3000)
  --no-headless           Run browser in visible mode (default: headless)
  --help, -h              Show this help message

Examples:
  1. Prompt text alone:
     node index.js --prompt "Dessine un astronaute sur Mars" --out "./mars.png"

  2. Image alone:
     node index.js --image "./photo.png" --out "./output.png"

  3. Image + Prompt (Edit / Transform):
     node index.js --image "./portrait.png" --prompt "transforme cette photo en style anime manga" --out "./manga.png"

  4. Login helper:
     node index.js --login

  5. Express server:
     node index.js --server --port 3000
`);
}

// --- Browser Session Initialization ---
async function getBrowserContext(headless = true) {
  if (!fs.existsSync(STORAGE_DIR)) {
    fs.mkdirSync(STORAGE_DIR, { recursive: true });
  }

  const { chromium } = getPlaywright();
  const context = await chromium.launchPersistentContext(STORAGE_DIR, {
    headless: headless,
    viewport: { width: 1920, height: 1080 },
    args: [
      '--disable-blink-features=AutomationControlled',
      '--disable-dev-shm-usage',
      '--no-sandbox'
    ]
  });

  return context;
}

// --- Login Helper ---
async function runLogin() {
  console.log('='.repeat(60));
  console.log('Gemini Web Automation - One-Time Login Helper');
  console.log('='.repeat(60));
  console.log(`Browser profile directory: ${STORAGE_DIR}`);
  console.log('Opening visible browser for Google authentication...');
  console.log('Please log into your Google account and verify Gemini is accessible.');
  console.log('When you are done, close the browser window or press Ctrl+C in this terminal.');

  const context = await getBrowserContext(false);
  const page = context.pages().length > 0 ? context.pages()[0] : await context.newPage();

  await page.goto(DEFAULT_GEMINI_URL);

  // Keep open until closed by user
  await new Promise((resolve) => {
    page.on('close', resolve);
    context.on('close', resolve);
  });

  console.log('Browser session saved successfully in:', STORAGE_DIR);
  process.exit(0);
}

// --- Core Automation: Upload Image ---
async function uploadImageToGemini(page, imagePath) {
  const resolvedPath = path.resolve(imagePath);
  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Image file not found: ${resolvedPath}`);
  }

  console.log(`[+] Uploading image: ${path.basename(resolvedPath)}...`);

  // Try method 1: Input[type=file] directly
  let fileInput = await page.$('input[type="file"]');
  if (fileInput) {
    await fileInput.setInputFiles(resolvedPath);
  } else {
    // Try method 2: Click upload button to reveal file chooser
    const uploadBtnSelectors = [
      'button[aria-label*="Upload"]',
      'button[aria-label*="upload"]',
      'button[aria-label*="Importer"]',
      'button[aria-label*="Ajouter"]',
      '[data-test-id="upload-file-card-container"]',
      'button[mattooltip*="Upload"]'
    ];

    let clicked = false;
    for (const selector of uploadBtnSelectors) {
      const btn = await page.$(selector);
      if (btn && await btn.isVisible()) {
        try {
          const [fileChooser] = await Promise.all([
            page.waitForEvent('filechooser', { timeout: 4000 }).catch(() => null),
            btn.click()
          ]);
          if (fileChooser) {
            await fileChooser.setFiles(resolvedPath);
            clicked = true;
            break;
          }
        } catch (_) {}
      }
    }

    // Try method 3: Synthetic paste event (AIkaptan clipboard technique)
    if (!clicked) {
      console.log('[-] Standard file chooser not triggered, injecting image via paste...');
      const imageBuffer = fs.readFileSync(resolvedPath);
      const ext = path.extname(resolvedPath).toLowerCase();
      const mimeMap = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif'
      };
      const mimeType = mimeMap[ext] || 'image/png';
      const base64Data = imageBuffer.toString('base64');
      const fileName = path.basename(resolvedPath);

      await page.evaluate(async ({ base64Data, mimeType, fileName }) => {
        const inputArea = document.querySelector('div.ql-editor, textarea, [contenteditable="true"]');
        if (!inputArea) return;
        inputArea.focus();

        const binary = atob(base64Data);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const blob = new Blob([bytes], { type: mimeType });
        const file = new File([blob], fileName, { type: mimeType });

        const dt = new DataTransfer();
        dt.items.add(file);
        const pasteEvent = new ClipboardEvent('paste', {
          clipboardData: dt,
          bubbles: true,
          cancelable: true
        });
        inputArea.dispatchEvent(pasteEvent);
      }, { base64Data, mimeType, fileName });
    }
  }

  // Wait for the upload thumbnail/card to appear or stabilize
  console.log('[+] Waiting for image attachment to be processed...');
  await page.waitForTimeout(2500);

  const previewSelectors = [
    'img[data-test-id="image-preview"]',
    'img[aria-label*="preview" i]',
    'img[aria-label*="aperçu" i]',
    '.file-preview-wrapper',
    '.uploader-file-preview-container',
    'button[aria-label*="Remove" i]'
  ];

  for (const sel of previewSelectors) {
    const el = await page.$(sel);
    if (el && await el.isVisible()) {
      console.log('[✓] Image successfully attached to prompt area.');
      return;
    }
  }
  console.log('[✓] Upload step completed.');
}

// --- Core Automation: Send Prompt & Submit ---
async function enterPromptAndSend(page, prompt) {
  // Select text input editor
  const editorSelectors = [
    'div.ql-editor.textarea.new-input-ui',
    'div.ql-editor[contenteditable="true"]',
    'textarea[aria-label*="prompt" i]',
    'textarea[placeholder*="prompt" i]',
    'div[contenteditable="true"]'
  ];

  let editor = null;
  for (const sel of editorSelectors) {
    const el = await page.$(sel);
    if (el && await el.isVisible()) {
      editor = el;
      break;
    }
  }

  if (prompt && prompt.trim().length > 0) {
    console.log(`[+] Entering prompt: "${prompt}"`);
    if (editor) {
      await editor.click();
      await page.keyboard.press('Control+A');
      await page.keyboard.press('Backspace');
      await editor.fill(prompt);
      await page.waitForTimeout(300);
    } else {
      throw new Error('Could not find Gemini prompt text input area.');
    }
  } else {
    console.log('[+] No prompt text provided (Image-only mode).');
  }

  // Click Send button
  console.log('[+] Sending request...');
  const sendBtnSelectors = [
    'button[aria-label*="Send message" i]',
    'button[aria-label*="Envoyer" i]',
    'button[aria-label*="Submit" i]',
    'button[data-test-id="send-button"]'
  ];

  let sent = false;
  for (const sel of sendBtnSelectors) {
    const btn = await page.$(sel);
    if (btn && await btn.isVisible() && await btn.isEnabled()) {
      await btn.click();
      sent = true;
      break;
    }
  }

  // Fallback: Press Enter in the editor
  if (!sent) {
    if (editor) {
      await editor.focus();
      await page.keyboard.press('Enter');
      sent = true;
    }
  }

  if (!sent) {
    throw new Error('Could not click the send button or submit prompt.');
  }

  console.log('[✓] Request submitted to Gemini.');
}

// --- Core Automation: Wait for Response & Extract Image / Text ---
async function waitForGeminiResponse(page, outputPath, timeout = 120000) {
  console.log('[+] Waiting for Gemini response & generated media (up to ' + (timeout / 1000) + 's)...');

  const startTime = Date.now();
  let responseText = '';
  let imageBuffer = null;

  // Let Gemini begin generation
  await page.waitForTimeout(4000);

  while (Date.now() - startTime < timeout) {
    // 1. Check for generated image in the response
    const candidateImages = await page.$$('model-response-text img, message-content img, .model-response img, img.image-node');
    
    for (const img of candidateImages) {
      try {
        const isVisible = await img.isVisible();
        if (!isVisible) continue;

        const box = await img.boundingBox();
        // Ignore small icons or avatars (size > 150px)
        if (box && box.width > 150 && box.height > 150) {
          const testId = await img.getAttribute('data-test-id');
          const ariaLabel = await img.getAttribute('aria-label') || '';
          if (testId === 'image-preview' || ariaLabel.toLowerCase().includes('preview')) {
            continue; // Skip user upload preview
          }

          console.log(`[✓] Generated image found in response (${Math.round(box.width)}x${Math.round(box.height)})!`);
          
          // Try downloading via src or screenshot element
          const src = await img.getAttribute('src');
          if (src && src.startsWith('http')) {
            try {
              const resp = await page.request.get(src);
              imageBuffer = await resp.body();
            } catch (_) {}
          } else if (src && src.startsWith('data:image')) {
            const base64Data = src.split(',')[1];
            imageBuffer = Buffer.from(base64Data, 'base64');
          }

          // Guaranteed fallback: element screenshot
          if (!imageBuffer) {
            imageBuffer = await img.screenshot();
          }

          if (imageBuffer) break;
        }
      } catch (_) {}
    }

    if (imageBuffer) break;

    // 2. Check if text streaming has completed
    const responseElements = await page.$$('model-response-text, .model-response, message-content');
    if (responseElements.length > 0) {
      const lastResponse = responseElements[responseElements.length - 1];
      const text = (await lastResponse.innerText()).trim();

      // Check if send button reappeared (indicates generation finished)
      const isStillGenerating = await page.$('button[aria-label*="Stop" i], button[aria-label*="Arrêter" i]');
      if (!isStillGenerating && text.length > 0) {
        responseText = text;
        // Wait another 3s in case image is rendering lazily
        await page.waitForTimeout(3000);
        // Double check images once more
        const lastImages = await page.$$('model-response-text img, message-content img, .model-response img');
        for (const img of lastImages) {
          const box = await img.boundingBox();
          if (box && box.width > 150 && box.height > 150) {
            imageBuffer = await img.screenshot();
            break;
          }
        }
        break;
      }
    }

    await page.waitForTimeout(2000);
  }

  // Handle saving the result
  if (imageBuffer) {
    const finalOut = outputPath || './output.png';
    const outDir = path.dirname(path.resolve(finalOut));
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

    fs.writeFileSync(finalOut, imageBuffer);
    console.log(`[✓] SUCCESS: Image saved to -> ${path.resolve(finalOut)}`);
    return {
      type: 'image',
      outputPath: path.resolve(finalOut),
      buffer: imageBuffer,
      text: responseText
    };
  } else if (responseText) {
    console.log('[✓] Gemini returned text response:');
    console.log('-'.repeat(40));
    console.log(responseText);
    console.log('-'.repeat(40));
    return {
      type: 'text',
      text: responseText
    };
  } else {
    throw new Error('Gemini response timed out or no output was detected.');
  }
}

// --- Main Automation Runner ---
async function runGeminiTask({ prompt, image, out = './output.png', headless = true, timeout = 120000 }) {
  if (!prompt && !image) {
    throw new Error('Please provide either a --prompt, an --image, or both.');
  }

  console.log(`[+] Initializing browser context (${headless ? 'Headless' : 'Headful'})...`);
  const context = await getBrowserContext(headless);
  const page = context.pages().length > 0 ? context.pages()[0] : await context.newPage();

  try {
    console.log(`[+] Navigating to ${DEFAULT_GEMINI_URL}...`);
    await page.goto(DEFAULT_GEMINI_URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2000);

    // Verify session
    const currentUrl = page.url();
    if (currentUrl.includes('accounts.google.com') || currentUrl.includes('signin')) {
      throw new Error("Session expired or not logged in! Please run 'node index.js --login' once to authenticate.");
    }

    // Step A: Upload image if provided (Case 2 & Case 3)
    if (image) {
      await uploadImageToGemini(page, image);
    }

    // Step B: Enter prompt text and send (Case 1 & Case 3, or Case 2 without prompt)
    await enterPromptAndSend(page, prompt);

    // Step C: Wait for response and extract image / text
    const result = await waitForGeminiResponse(page, out, timeout);
    return result;

  } finally {
    await context.close();
  }
}

// --- Optional Lightweight Express Server ---
function startExpressServer(port = 3000) {
  let express, multer;
  try {
    express = require('express');
    multer = require('multer');
  } catch (e) {
    console.error('Express or multer not found. Please run: npm install express multer');
    process.exit(1);
  }

  const app = express();
  const upload = multer({ dest: './storage/uploads/' });

  app.use(express.json());
  app.use(express.urlencoded({ extended: true }));

  // Minimal single endpoint: POST /
  app.post('/', upload.single('image'), async (req, res) => {
    try {
      const prompt = req.body.prompt || req.query.prompt || null;
      const uploadedFile = req.file ? req.file.path : null;
      const imagePath = uploadedFile || req.body.image || null;

      if (!prompt && !imagePath) {
        return res.status(400).json({ error: 'Provide at least prompt or image' });
      }

      console.log(`[HTTP POST /] Received request - prompt: "${prompt}", image: "${imagePath}"`);
      const tempOut = path.resolve(`./storage/uploads/out_${Date.now()}.png`);

      const result = await runGeminiTask({
        prompt,
        image: imagePath,
        out: tempOut,
        headless: true
      });

      // Clean up uploaded temp file
      if (uploadedFile && fs.existsSync(uploadedFile)) {
        try { fs.unlinkSync(uploadedFile); } catch (_) {}
      }

      if (result.type === 'image' && result.buffer) {
        res.type('image/png');
        return res.send(result.buffer);
      } else {
        return res.json({ success: true, text: result.text });
      }

    } catch (err) {
      console.error('[HTTP Error]:', err.message);
      return res.status(500).json({ error: err.message });
    }
  });

  app.get('/', (req, res) => {
    res.json({
      service: 'Gemini Web Automation Express API',
      status: 'ready',
      usage: 'POST / with form-data (fields: prompt, image)'
    });
  });

  app.listen(port, () => {
    console.log('='.repeat(60));
    console.log(`Gemini Web Automation Express Server listening on port ${port}`);
    console.log(`Endpoint: POST http://localhost:${port}/`);
    console.log('='.repeat(60));
  });
}

// --- CLI Entrypoint ---
async function main() {
  const args = parseArgs();

  if (args.login) {
    await runLogin();
    return;
  }

  if (args.server) {
    startExpressServer(args.port);
    return;
  }

  // If called directly via CLI with arguments
  try {
    await runGeminiTask({
      prompt: args.prompt,
      image: args.image,
      out: args.out,
      headless: args.headless,
      timeout: args.timeout
    });
  } catch (err) {
    console.error('\n[x] ERROR:', err.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  runGeminiTask,
  runLogin,
  startExpressServer
};
