# Smart Meta-controller: Energy Efficient Dynamic Routing for LLMs

The **Smart Meta-controller** is an intelligent, energy-efficient routing system designed to dynamically allocate user-generated queries to different Large Language Models (LLMs) based on task complexity. 

By avoiding a "one size fits all" monolithic approach, this architecture routes 60-80% of tasks to highly efficient, lightweight agents, reserving computationally expensive deep agents only for the tasks that truly require them. This dramatically reduces GPU consumption and latency while maintaining perfect reliability through a robust **Escalation Protocol**.

---

## 📁 Folder Structure

```
.
├── backend/                   # Main Meta-controller Gateway (Port 8000)
│   ├── app.py                 # Core routing, rate-limiting, and escalation logic
│   └── requirements.txt       # Dependencies for the meta-controller
├── llm_backend/               # Internal LLM Execution Layer (Port 8001)
│   ├── main.py                # Endpoints for Light & Heavy Agents
│   ├── config.py              # AES encryption utilities
│   └── .env                   # Environment variables (API Keys)
├── frontend/                  # Web-based Telemetry Dashboard
│   └── index.html             # Real-time monitoring UI
├── API_AND_SECURITY.md        # Comprehensive API & Security Documentation
└── requirements.txt           # Core ML and data processing dependencies
```

---

## 🏗️ Architecture Overview

The system operates via a decoupled, two-tier microservice architecture:

### 1. The Meta-controller (Main Backend - Port 8000)
The central coordinating engine. It intercepts user queries and uses a **fine-tuned DistilBERT** model (capable of 97% classification accuracy in ~15ms) to proactively predict task complexity as either `light` or `heavy`.

### 2. The LLM Execution Layer (LLM Backend - Port 8001)
A secure, internal service that executes the actual LLM generation. It hosts two distinct endpoints:
- **Light Agent (`/light`):** Handles simple queries. Highly efficient, low latency.
- **Deep Agent (`/heavy`):** Handles complex queries requiring deep analytical reasoning. 

### 3. The Dynamic Escalation Protocol
A fail-safe safety net ensuring that simple agents don't hallucinate or fail on complex tasks. 
- **Confidence Thresholding:** If DistilBERT predicts "light" but its confidence is below `70%`, the Meta-controller automatically overrides the decision and escalates the query to the Deep Agent.
- **Fail-Safe Fallback:** If the Light Agent encounters an API failure or crash, the Meta-controller catches the exception and reroutes the prompt to the Deep Agent to guarantee a response.

---

## 🔒 Security & API Management

The architecture is heavily fortified against four critical LLM vulnerabilities:

1. **Prompt Injection Defense:** A strict regex-based Input Validation (`sanitize_input`) intercepts malicious commands (e.g., `"ignore previous instructions"`) and blocks them at the gateway with a `400 Bad Request`.
2. **DDoS Prevention:** The public API endpoints (`/chat` and `/escalate-test`) are rate-limited to **5 Queries Per Second (QPS)** using the `slowapi` library.
3. **Data Privacy (Payload Encryption):** The internal communication channel between the Meta-controller and the LLM Execution Layer is secured using **AES-128 Encryption (Fernet)**. Prompts are encrypted before transmission and decrypted just before LLM execution, preventing session data leakage and packet sniffing.
4. **Adversarial Defenses:** Attackers attempting to trick the classifier by masking complex queries inside simple phrasing will trigger a drop in the classifier's confidence score, safely catching them in the `< 70%` escalation threshold.

---

## ⚙️ API Structure

### Public Endpoints (Port 8000)
- `POST /chat`: The primary entry point. Accepts `{"text": "query"}`. Applies sanitization, classification, rate-limiting, and encryption before routing.
- `POST /escalate-test`: A backdoor for UI testing that bypasses DistilBERT and hardcodes a `65%` confidence score to forcefully trigger an escalation.

### Internal Endpoints (Port 8001)
- `POST /light` & `POST /heavy`: Internal execution endpoints. They *only* accept AES-128 encrypted payloads `{"encrypted_data": "..."}`, ensuring security across microservices.

---

## 🚀 Setup & Configuration

### 1. Install Dependencies
Install dependencies for both the core machine learning scripts and the backend microservices.
```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

### 2. Download the DistilBERT Model
To keep the Git repository lightweight, the massive DistilBERT model weights are **not included in the repository** (they are added to `.gitignore`). You must download the weights before running the backend.

1. Download the pre-trained DistilBERT weights from [Insert Download Link Here].
2. Extract the downloaded folder and place it in the project root so that the path looks exactly like this: `models/distilbert-prompt-classifier/`.

### 3. Configure Your Custom LLM API (Groq by Default)

> **Note:** To demonstrate and test this project, the **Groq API** was used to power the agents (`llama-3.1-8b-instant` for Light, `llama-3.3-70b-versatile` for Deep). However, you can easily configure this to use your own preferred API (e.g., OpenAI, Anthropic, local Ollama).

**Steps to configure your own APIs:**
1. Open `llm_backend/main.py`.
2. Locate the API client initialization. Currently, it uses `from groq import Groq` and initializes `client = Groq(api_key=...)`.
3. Replace the `Groq` client with your preferred provider's SDK (e.g., `from openai import OpenAI`).
4. Update the `.env` file in the `llm_backend` directory with your new API Key.
5. In the `@app.post("/light")` and `@app.post("/heavy")` routes, change the model names (e.g., `"gpt-4o-mini"` for Light, `"gpt-4o"` for Heavy) and adjust the API call syntax to match your provider.

### 4. Start the Servers

You need to run both microservices simultaneously.

**Terminal 1: Start the LLM Backend**
```bash
cd llm_backend
uvicorn main:app --port 8001
```

**Terminal 2: Start the Meta-Controller**
```bash
cd backend
python3 app.py
```
*(The Meta-controller will run on `http://0.0.0.0:8000`. The first launch will load the DistilBERT weights into memory).*

### 5. Launch the Dashboard
Open `frontend/index.html` in any web browser. 

The dashboard provides a sleek, dark-mode terminal UI that gives you real-time visual telemetry. It displays the Routing Decision, the Confidence Score, Execution Time, and a dynamic telemetry bar that shifts colors depending on the agent used (Green for Light, Red for Heavy, Gold for Escalated).