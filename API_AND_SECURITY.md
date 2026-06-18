# Meta-Controller API & Security Documentation

This document outlines the API structure, routing logic, and comprehensive security measures implemented across the Smart Meta-controller architecture.

---

## 1. System Architecture Overview

The system utilizes a two-tier microservice architecture to decouple the intelligent routing logic from the actual Large Language Model (LLM) execution. 

1. **Main Backend (Meta-Controller) - Port 8000:** Acts as the public-facing gateway. It intercepts user queries, sanitizes inputs, runs the DistilBERT complexity classifier, and routes the request.
2. **LLM Execution Backend - Port 8001:** An internal, secured service that handles communication with the Groq API. It hosts the endpoints for both the "Light Agent" (`llama-3.1-8b-instant`) and the "Deep Agent" (`llama-3.3-70b-versatile`).

---

## 2. API Structure & Endpoints

### A. Main Backend (Public Gateway)

#### `POST /chat`
- **Role:** The primary entry point for all user queries.
- **Process:** 
  1. Validates and sanitizes the input.
  2. Passes the prompt to the fine-tuned DistilBERT model to predict complexity (Light vs. Heavy).
  3. Enforces the **Escalation Protocol** (routes to Heavy if confidence is < 70%).
  4. Encrypts the payload and forwards it to the LLM Execution Backend.
- **Payload:** `{"text": "User's prompt here"}`
- **Response:** Returns the routing decision, confidence score, actual agent used, the LLM response, execution time, and an `escalated` boolean flag.

#### `POST /escalate-test`
- **Role:** A testing backdoor to validate the Escalation Protocol and frontend UI.
- **Process:** Bypasses the DistilBERT ML model entirely. It hardcodes a "light" classification with a forced `0.65` (65%) confidence score, ensuring the system artificially triggers the < 70% threshold and escalates the request to the Deep Agent.
- **Payload & Response:** Identical to `/chat`.

### B. LLM Execution Backend (Internal Service)

> **WARNING:** These endpoints are not meant to be exposed to the public. They only accept AES-encrypted payloads originating from the Main Backend.

#### `POST /light`
- **Role:** Executes simple queries using the highly efficient `llama-3.1-8b-instant` model.
- **Process:** Decrypts the incoming AES-128 payload, extracts the prompt, and queries the Groq API.
- **Payload:** `{"encrypted_data": "gAAAAAB..."}`

#### `POST /heavy`
- **Role:** Executes complex or escalated queries using the powerful `llama-3.3-70b-versatile` model.
- **Process:** Decrypts the incoming AES-128 payload, extracts the prompt, and queries the Groq API.
- **Payload:** `{"encrypted_data": "gAAAAAB..."}`

---

## 3. Comprehensive Security Implementation

Based on the vulnerabilities identified in the research paper, the system implements four distinct layers of security at different stages of the pipeline.

### Layer 1: Input Validation & Sanitization (Prompt Injection)
- **Where it is applied:** In `backend/app.py` via the `sanitize_input()` function, executed immediately when `/chat` or `/escalate-test` receives a request.
- **How it works:** Uses strict Regex pattern matching to scan for common prompt injection vectors (e.g., `"ignore previous"`, `"forget all"`, `"system prompt"`, `"bypass rules"`).
- **Purpose:** Prevents attackers from hijacking the system's foundational instructions or jailbreaking the backend logic. Malicious requests are instantly rejected with a `400 Bad Request`.

### Layer 2: API Rate Limiting (DDoS Prevention)
- **Where it is applied:** In `backend/app.py` via the `slowapi` library (`@limiter.limit("5/second")` decorators on endpoints).
- **How it works:** Tracks incoming requests based on the client's IP address and enforces a strict limit of 5 Queries Per Second (QPS).
- **Purpose:** Protects the exposed public endpoints from Distributed Denial of Service (DDoS) attacks and ensures the backend and Groq API quotas are not overwhelmed by malicious traffic spikes.

### Layer 3: Payload Encryption (Data Privacy)
- **Where it is applied:** Across the network boundary between `backend/app.py` (Encryption) and `llm_backend/main.py` (Decryption).
- **How it works:** Utilizes the `cryptography.fernet` module. The Meta-controller encrypts the user's prompt using AES-128 with a shared, url-safe base64-encoded secret key before transmitting it over HTTP. The receiving LLM backend decrypts the payload before processing.
- **Purpose:** Prevents packet sniffing and session data leakage across the escalation channel. Even if the internal network is compromised, the prompts remain completely unreadable.

### Layer 4: Adversarial Defenses (Model Security)
- **Where it is applied:** In the routing logic of `backend/app.py`.
- **How it works:** Leverages **Confidence Thresholding**. If an attacker attempts to craft a deceptive prompt designed to confuse the DistilBERT classifier (e.g., hiding a complex mathematical proof behind the phrase "This is a simple query"), the conflicting linguistic patterns will drastically lower the model's confidence score.
- **Purpose:** Because the system automatically escalates any query with a confidence score below 70%, these adversarial attacks are safely caught by the threshold and diverted to the highly capable Deep Agent, neutralizing the threat.
