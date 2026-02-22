from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Added import
from google import genai
import shutil
import os
import time
from fastapi.responses import FileResponse

app = FastAPI()

# --- START OF PERMISSION CODE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows your HTML file to connect
    allow_credentials=True,
    allow_methods=["*"],  # Allows POST, GET, etc.
    allow_headers=["*"],
)
# --- END OF PERMISSION CODE ---

# Replace with your actual working API Key
API_KEY = "AIzaSyB-kSchSdt6ceCjRLzrGOkQTG4KST5FS3k"
client = genai.Client(api_key=API_KEY)

def get_working_model():
    """Finds the correct model name to avoid 404 errors."""
    try:
        for m in client.models.list():
            if "generateContent" in m.supported_actions:
                if "flash" in m.name and "1.5" in m.name:
                    return m.name
                elif "flash" in m.name:
                    return m.name
    except Exception as e:
        print(f"Auth Error: {e}")
    return "gemini-1.5-flash"

@app.get("/")
def home():
    return FileResponse("index.html")

@app.post("/analyze-audio")
async def analyze_audio(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    try:
        # 1. Save file locally
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Upload to Gemini
        print(f"Uploading {temp_path}...")
        uploaded_file = client.files.upload(file=temp_path)

        # 3. Wait for processing
        while uploaded_file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        print("\nUpload Complete. Analyzing...")

        # 4. Generate analysis
        model_name = get_working_model()
        response = client.models.generate_content(
            model=model_name,
            contents=[
                "Analisis audio ini sebagai pakar siber. Adakah ini scam? Balas dalam Bahasa Melayu dengan ringkas.",
                uploaded_file
            ]
        )

        # Return is_scam logic for your History UI
        is_scam = "scam" in response.text.lower() or "bahaya" in response.text.lower()
        return {"analysis": response.text, "is_scam": is_scam}

    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)