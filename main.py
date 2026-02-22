from google import genai
import time

# 1. SETUP: Ensure your key is pasted perfectly here
API_KEY = "AIzaSyB-kSchSdt6ceCjRLzrGOkQTG4KST5FS3k" # Paste your key carefully
client = genai.Client(api_key=API_KEY)

def get_working_model():
    """Finds the correct model name to avoid 404 errors."""
    print("Checking your available models...")
    try:
        # List all models available to your specific API Key
        for m in client.models.list():
            if "generateContent" in m.supported_actions:
                # We prioritize 'flash' for speed/cost
                if "flash" in m.name:
                    return m.name
    except Exception as e:
        print(f"Auth Error: {e}")
    return None

def run_awas_test(audio_file):
    model_name = get_working_model()
    
    if not model_name:
        print("❌ FAILED: API Key is invalid or has no access to models.")
        return

    print(f"✅ Found working model: {model_name}")
    
    try:
        # 2. UPLOAD
        print(f"Uploading {audio_file}...")
        uploaded_file = client.files.upload(file=audio_file)

        # 3. WAIT
        while uploaded_file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        print("\nUpload Complete. Analyzing...")

        # 4. GENERATE
        response = client.models.generate_content(
            model=model_name, # Uses the name we found automatically
            contents=[
                "Analisis audio ini sebagai pakar siber. Adakah ini scam? Balas dalam Bahasa Melayu.",
                uploaded_file
            ]
        )

        print("\n--- SAHABAT AWAS ANALYSIS ---")
        print(response.text)

    except Exception as e:
        print(f"\n[ERROR]: {e}")

if __name__ == "__main__":
    run_awas_test("scam_audio.mp3")