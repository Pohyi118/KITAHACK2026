import os
import sys
import asyncio
import shutil
import time
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from pyaxmlparser import APK

# --- 1. WINDOWS COMPATIBILITY FIX ---
# Crucial for Playwright to run alongside FastAPI on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI()

# --- 2. STATIC FOLDER & CORS SETUP ---
# Auto-creates the 'static' folder for evidence.png if it doesn't exist
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. API CONFIGURATION ---
API_KEY = "AIzaSyB-kSchSdt6ceCjRLzrGOkQTG4KST5FS3k"
client = genai.Client(api_key=API_KEY)

# --- 4. SYSTEM PROMPTS (The AI's "Brain") ---

URL_SYSTEM_PROMPT = """
Act as a Senior Forensic Web Security Analyst. Detect scams mimicking brands like Maybank, DHL, or Shopee.
Analyze network DNA, redirects, and content. Respond strictly in JSON:
{
  "risk_score": (0-100),
  "is_malicious": (boolean),
  "summary": "Professional summary in Bahasa Melayu.",
  "captured_threats": ["List specifically identified red flags"],
  "verdict_en": "1-sentence final recommendation."
}
"""

AUDIO_SYSTEM_PROMPT = """
Act as a Senior Cyber-Security Expert. Analyze audio for voice cloning (deepfakes) or scams.
Respond strictly in JSON:
{
  "risk_score": (number),
  "is_scam": (boolean),
  "analysis_ms": "Ringkasan profesional dalam Bahasa Melayu.",
  "red_flags": ["list of signs"]
}
"""

APK_SYSTEM_PROMPT = """
Act as an Android Security Sandbox. Analyze APK permissions for dangerous patterns.
Respond strictly in JSON:
{
  "risk_level": "High/Medium/Low",
  "threat_summary": "English explanation of risks.",
  "suspicious_permissions": ["list of permissions"],
  "recommendation": "Clear action for the user"
}
"""

# --- 5. ENDPOINTS ---

@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# --- FEATURE 1: DEEP URL SCAN (Combined from analysis-engine & service) ---
@app.post("/analyze-url")
async def analyze_url(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        redirect_chain = []
        page.on("framenavigated", lambda frame: redirect_chain.append(frame.url))

        try:
            # Deep Scan logic: Inspects network, SSL, and captures evidence
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            security_info = await response.security_details()
            
            # Save visual proof for the WhatsApp Chat UI
            evidence_path = os.path.join("static", "evidence.png")
            await page.screenshot(path=evidence_path)

            analysis_payload = {
                "url": url,
                "redirects": redirect_chain,
                "issuer": security_info.issuer if security_info else "Unknown",
                "content_snippet": await page.content()[:500]
            }

            gemini_result = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=[f"Judge this site behavior: {json.dumps(analysis_payload)}"],
                config=types.GenerateContentConfig(
                    system_instruction=URL_SYSTEM_PROMPT,
                    response_mime_type="application/json"
                )
            )
            
            result = json.loads(gemini_result.text)
            # Add image URL for the bot interface
            result["image_url"] = f"/static/evidence.png?t={int(time.time())}"
            return result

        except Exception as e:
            return {"error": f"Gagal mengimbas: {str(e)}", "risk_score": 100}
        finally:
            await browser.close()

# --- FEATURE 2: VOICE & CLONE DETECTION ---
@app.post("/analyze-audio")
async def analyze_audio(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        uploaded = client.files.upload(file=temp_path)
        while uploaded.state.name == "PROCESSING":
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)

        response = client.models.generate_content(
            model="gemini-1.5-pro",
            contents=["Analyze this audio for scams or AI cloning.", uploaded],
            config=types.GenerateContentConfig(
                system_instruction=AUDIO_SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

# --- FEATURE 3: APK PERMISSION SANDBOX ---
@app.post("/analyze-apk")
async def analyze_apk(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        apk = APK(temp_path)
        perm_text = ", ".join(apk.get_permissions())

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[f"Analyze these permissions: {perm_text}"],
            config=types.GenerateContentConfig(
                system_instruction=APK_SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": f"Failed to sandbox APK: {str(e)}"}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)