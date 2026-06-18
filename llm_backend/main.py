# Setup Instructions:
# 1. Install dependencies:
#    pip install -r requirements.txt
#
# 2. Add your API keys to the .env file:
#    GROQ_API_KEY=your-groq-key-here
#
# 3. Run the server (on port 8001 to avoid conflict):
#    uvicorn main:app --reload --port 8001

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException 
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from groq import Groq 
from config import settings

# Initialize Groq client
client = None
if settings.groq_api_key and not settings.groq_api_key.startswith("your-groq-key-here"):
    client = Groq(api_key=settings.groq_api_key)

app = FastAPI()

from cryptography.fernet import Fernet
import json

# AES-128 Shared Secret (Must match backend/app.py)
SHARED_SECRET = b'J-9cZ5WqI8pQ1t3B0xLx9TzYvV7E6cK2fA4R5nF1mOo='
cipher = Fernet(SHARED_SECRET)

class EncryptedRequest(BaseModel):
    encrypted_data: str

class LLMResponse(BaseModel):
    model: str
    response: str

def decrypt_prompt(encrypted_data: str) -> str:
    try:
        decrypted_bytes = cipher.decrypt(encrypted_data.encode('utf-8'))
        data = json.loads(decrypted_bytes.decode('utf-8'))
        return data["prompt"]
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid encrypted payload")

@app.post("/light", response_model=LLMResponse)
async def query_light(request: EncryptedRequest):
    prompt = decrypt_prompt(request.encrypted_data)
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    if not client:
        raise HTTPException(status_code=500, detail="Groq API key not configured.")

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "model": "llama-3.1-8b-instant (Light Agent)",
            "response": response.choices[0].message.content
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/heavy", response_model=LLMResponse)
async def query_heavy(request: EncryptedRequest):
    prompt = decrypt_prompt(request.encrypted_data)
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    if not client:
        raise HTTPException(status_code=500, detail="Groq API key not configured.")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "model": "llama-3.3-70b (Deep Agent)",
            "response": response.choices[0].message.content
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
