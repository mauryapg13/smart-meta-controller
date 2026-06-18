from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
import torch
import torch.nn.functional as F
import threading
import os
import logging
import requests
import re
import json
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from cryptography.fernet import Fernet

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Rate Limiter Configuration
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# AES-128 Shared Secret for Escalation Channel
SHARED_SECRET = b'J-9cZ5WqI8pQ1t3B0xLx9TzYvV7E6cK2fA4R5nF1mOo='
cipher = Fernet(SHARED_SECRET)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Model Loading State ---
class ModelStatus:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.is_loading = False
        self.error = None

model_status = ModelStatus()

def load_model():
    """Loads the model and tokenizer."""
    global model_status
    model_status.is_loading = True
    logger.info("Starting model loading...")
    try:
        # Construct absolute path to the model
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, "..", "models", "distilbert-prompt-classifier")
        logger.info(f"Loading model from: {model_path}")

        model_status.tokenizer = DistilBertTokenizerFast.from_pretrained(model_path)
        model_status.model = DistilBertForSequenceClassification.from_pretrained(model_path)
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Error loading model: {e}", exc_info=True)
        model_status.error = str(e)
    finally:
        model_status.is_loading = False

@app.on_event("startup")
async def startup_event():
    """Run model loading in a background thread."""
    thread = threading.Thread(target=load_model)
    thread.start()

# --- API Endpoints ---
class PromptRequest(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"message": "Smart Prompt Router API is running"}

@app.get("/health")
def health_check():
    """Provides the status of the model loading."""
    if model_status.is_loading:
        return {"status": "loading_model"}
    if model_status.error:
        return {"status": "error", "detail": model_status.error}
    if model_status.model and model_status.tokenizer:
        return {"status": "ready"}
    return {"status": "initializing"}


@app.post("/classify")
def classify_prompt(request: PromptRequest):
    """Classifies the prompt as 'light' or 'heavy'."""
    if model_status.is_loading:
        raise HTTPException(status_code=503, detail="Model is still loading. Please try again in a moment.")
    if not model_status.model or not model_status.tokenizer:
        raise HTTPException(status_code=500, detail=f"Model not available. Error: {model_status.error}")

    try:
        inputs = model_status.tokenizer(request.text, return_tensors="pt", truncation=True, padding=True, max_length=128)
        with torch.no_grad():
            logits = model_status.model(**inputs).logits

        probabilities = F.softmax(logits, dim=1).squeeze()
        predicted_class_id = torch.argmax(probabilities).item()
        confidence = probabilities[predicted_class_id].item()

        label_map = {0: "light", 1: "heavy"}
        predicted_label = label_map[predicted_class_id]

        return {"label": predicted_label, "confidence": confidence}
    except Exception as e:
        logger.error(f"Error during classification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during classification.")

import time

def sanitize_input(text: str) -> str:
    injection_patterns = r'(ignore previous|forget all|system prompt|disregard previous|bypass rules)'
    if re.search(injection_patterns, text, re.IGNORECASE):
        logger.warning(f"Prompt injection detected and blocked: {text}")
        raise HTTPException(status_code=400, detail="Invalid input: Prompt injection detected.")
    return text

@app.post("/chat")
@limiter.limit("5/second")
def chat(request: Request, prompt_req: PromptRequest):
    """Classifies the prompt and routes it to the appropriate LLM agent with Escalation Protocol."""
    prompt_req.text = sanitize_input(prompt_req.text)
    if model_status.is_loading:
        raise HTTPException(status_code=503, detail="Model is still loading. Please try again in a moment.")
    
    # 1. Classify the prompt and measure time
    start_time = time.time()
    try:
        classification_result = classify_prompt(prompt_req)
        label = classification_result["label"]
        confidence = classification_result["confidence"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")
    
    classification_time = time.time() - start_time

    # 2. Route based on classification with Escalation Protocol
    llm_backend_url = "http://localhost:8001"
    escalated = False

    # Escalation Rule A: Low Confidence on Light Model
    if label == "light" and confidence < 0.70:
        logger.info(f"Escalating to heavy due to low confidence ({confidence:.2f})")
        label = "heavy"
        escalated = True
    
    endpoint = "/light" if label == "light" else "/heavy"
    
    try:
        encrypted_payload = cipher.encrypt(json.dumps({"prompt": prompt_req.text}).encode('utf-8')).decode('utf-8')
        response = requests.post(
            f"{llm_backend_url}{endpoint}",
            json={"encrypted_data": encrypted_payload},
            timeout=30
        )
        response.raise_for_status()
        llm_data = response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling {label} LLM backend: {e}")
        # Escalation Rule B: Fallback on API Failure
        if label == "light":
            logger.info("Escalating to heavy agent due to light agent failure")
            label = "heavy"
            escalated = True
            try:
                encrypted_payload = cipher.encrypt(json.dumps({"prompt": prompt_req.text}).encode('utf-8')).decode('utf-8')
                fallback_resp = requests.post(
                    f"{llm_backend_url}/heavy",
                    json={"encrypted_data": encrypted_payload},
                    timeout=30
                )
                fallback_resp.raise_for_status()
                llm_data = fallback_resp.json()
            except Exception as heavy_e:
                raise HTTPException(status_code=502, detail=f"Both agents failed. Heavy error: {str(heavy_e)}")
        else:
            raise HTTPException(status_code=502, detail=f"Failed to communicate with LLM backend: {str(e)}")

    return {
        "routing_decision": label,
        "confidence": confidence,
        "agent_used": llm_data["model"],
        "response": llm_data["response"],
        "classification_time": classification_time,
        "escalated": escalated
    }

@app.post("/escalate-test")
@limiter.limit("5/second")
def escalate_test(request: Request, prompt_req: PromptRequest):
    """Bypasses ML classification to force an escalation test."""
    import time
    prompt_req.text = sanitize_input(prompt_req.text)
    
    start_time = time.time()
    
    # 1. Bypass ML: Force light routing with a fake low confidence score
    label = "light"
    confidence = 0.65
    classification_time = time.time() - start_time
    
    # 2. Route based on classification with Escalation Protocol
    llm_backend_url = "http://localhost:8001"
    escalated = False

    # Escalation Rule A: Low Confidence on Light Model
    if label == "light" and confidence < 0.70:
        logger.info(f"TEST ENDPOINT: Escalating to heavy due to forced low confidence ({confidence:.2f})")
        label = "heavy"
        escalated = True
    
    try:
        encrypted_payload = cipher.encrypt(json.dumps({"prompt": prompt_req.text}).encode('utf-8')).decode('utf-8')
        response = requests.post(
            f"{llm_backend_url}/heavy",
            json={"encrypted_data": encrypted_payload},
            timeout=30
        )
        response.raise_for_status()
        llm_data = response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling {label} LLM backend: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to communicate with LLM backend: {str(e)}")

    return {
        "routing_decision": label,
        "confidence": confidence,
        "agent_used": llm_data["model"],
        "response": llm_data["response"],
        "classification_time": classification_time,
        "escalated": escalated
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
