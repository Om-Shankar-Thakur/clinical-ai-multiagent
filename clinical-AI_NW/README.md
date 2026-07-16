# MedOrchestrator 🏥

**A Multi-Agent Clinical Decision Support System**

MedOrchestrator is an AI-powered clinical decision-support platform that orchestrates multiple specialized agents to analyze patient symptoms, lab results, and medications in parallel — producing differential diagnoses, evidence-based treatment recommendations, and drug-safety alerts under clinician supervision.

> **⚠️ Medical Disclaimer:** This system is a clinical decision-support aid only. It does NOT constitute a prescription or medical order. All treatment decisions must be made by a licensed clinician after independent evaluation.

---

## 🎯 What Does MedOrchestrator Do?

MedOrchestrator takes patient data (chief complaint, symptoms, lab values, current medications) and runs it through a coordinated pipeline of AI agents:

1. **Symptom Analysis** → Retrieves and ranks differential diagnoses using semantic matching against a disease knowledge base
2. **Lab Interpretation** → Validates hypotheses with rule-based lab analysis and flags critical values
3. **Diagnosis Arbitration** → Combines symptom and lab evidence into a weighted diagnostic ranking
4. **Treatment Planning** → Retrieves clinical guidelines and generates management options aligned with best practices
5. **Drug Safety Check** → Validates proposed treatments against current medications and flags interactions

The result: A structured report with confidence scores, dissenting opinions (when agents disagree), and safety warnings — ready for clinician review.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Streamlit Web Interface (Port 8501)             │  │
│  │   • Patient data input forms                                 │  │
│  │   • Structured result visualization                          │  │
│  │   • Critical alerts highlighting                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP POST /analyze
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API LAYER                                   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              FastAPI Backend (Port 8000)                     │  │
│  │   • REST API endpoints                                       │  │
│  │   • Request validation (Pydantic)                           │  │
│  │   • Singleton orchestrator management                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ orchestrator.run()
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Clinical Orchestrator                       │  │
│  │                                                              │  │
│  │   STEP 1: Parallel Agent Execution (ThreadPoolExecutor)     │  │
│  │   ┌──────────────────┐  ┌──────────────────────┐            │  │
│  │   │ Symptom Analyzer │  │ Lab Interpreter      │            │  │
│  │   │                  │  │                      │            │  │
│  │   │ • FAISS retrieval│  │ • Rule-based matching│            │  │
│  │   │ • Semantic match │  │ • Critical flagging  │            │  │
│  │   │ • Confidence score│ │ • Pattern validation│            │  │
│  │   └────────┬─────────┘  └──────────┬───────────┘            │  │
│  │            └────────────┬───────────┘                        │  │
│  │                         ▼                                    │  │
│  │   STEP 2: Diagnosis Arbitration                             │  │
│  │   • Merge symptom scores (55%) + lab scores (45%)           │  │
│  │   • Rank candidates by combined evidence                    │  │
│  │   • Detect dissenting opinions (agent disagreements)        │  │
│  │                         │                                    │  │
│  │                         ▼                                    │  │
│  │   STEP 3: Treatment Planning (RAG + LLM)                    │  │
│  │   ┌─────────────────────────────────────┐                   │  │
│  │   │ Treatment Planner Agent              │                  │  │
│  │   │ • Retrieve clinical guidelines       │                  │  │
│  │   │ • Generate management options (LLM) │                  │  │
│  │   │ • Confidence gating (threshold=0.4) │                  │  │
│  │   └──────────────┬──────────────────────┘                   │  │
│  │                  ▼                                           │  │
│  │   STEP 4: Drug Interaction Check (LLM)                      │  │
│  │   ┌─────────────────────────────────────┐                   │  │
│  │   │ Drug Interaction Checker Agent       │                  │  │
│  │   │ • Cross-reference current meds       │                  │  │
│  │   │ • Flag contraindications             │                  │  │
│  │   │ • Assess severity (low/medium/high)  │                  │  │
│  │   └──────────────┬──────────────────────┘                   │  │
│  │                  ▼                                           │  │
│  │   STEP 5: Final Report Assembly                             │  │
│  │   • Consolidated diagnosis + confidence                     │  │
│  │   • Treatment options + monitoring                          │  │
│  │   • Drug warnings + critical lab flags                      │  │
│  │   • Dissenting opinions + uncertainty notes                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DATA & AI LAYER                               │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ Disease Vector   │  │ Guideline Vector │  │ Azure OpenAI    │  │
│  │ Store (FAISS)    │  │ Store (FAISS)    │  │ (GPT)           │  │
│  │                  │  │                  │  │                 │  │
│  │ • 50+ diseases   │  │ • 5+ guidelines  │  │ • Treatment gen │  │
│  │ • Symptom embed  │  │ • Chunked text   │  │ • Drug check    │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │        Sentence-BERT Embedder (all-MiniLM-L6-v2)            │  │
│  │        • Converts text → 384-dim vectors                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Clinical Workflow

### Input Stage
```
Patient Data
├── Chief Complaint: "High fever with body ache"
├── Symptoms: ["fever", "body pain", "headache", "chills"]
├── Lab Results: {"platelets": 80000, "hematocrit": 52}
└── Current Medications: ["Ibuprofen"]
```

### Processing Pipeline

**Phase 1: Parallel Evidence Gathering (Step 1)**
```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│  Symptom Analyzer           │     │  Lab Interpreter            │
│                             │     │                             │
│  1. Encode symptoms → vector│     │  1. Match labs to thresholds│
│  2. FAISS search (top-5)    │     │  2. Flag critical values    │
│  3. Score by overlap        │     │  3. Match disease patterns  │
│  4. Rank confidence         │     │  4. Score hypothesis support│
│                             │     │                             │
│  Output:                    │     │  Output:                    │
│  • Dengue: 0.66 (high)      │     │  • Dengue: 0.50 (partial)   │
│  • Malaria: 0.67 (high)     │     │  • Critical: low platelets  │
└─────────────────────────────┘     └─────────────────────────────┘
          │                                    │
          └────────────────┬───────────────────┘
                           ▼
```

**Phase 2: Diagnosis Arbitration (Step 2)**
```
Combined Scoring: 0.55 × symptom_score + 0.45 × lab_score

Disease Rankings:
1. Dengue         → 0.588 (0.66 × 0.55 + 0.50 × 0.45) ✓ PRIMARY
2. Malaria        → 0.369 (0.67 × 0.55 + 0.00 × 0.45)
3. Dengue Fever   → 0.456

✓ Dissent Detected: Malaria ranks #1 in symptoms but #4 in labs
                           ▼
```

**Phase 3: Treatment Planning (Step 3)**
```
RAG Retrieval:
• Query: "Dengue treatment management guidelines"
• Top-5 guideline chunks retrieved from FAISS

LLM Generation (Azure GPT):
• System: "Format guidelines as JSON, no prescribing"
• Context: Diagnosis=Dengue, Confidence=0.588, Critical=low platelets
• Output: Conservative management options with monitoring

Confidence Gate: 0.588 > 0.4 ✓ PASS → Generate plan
                           ▼
```

**Phase 4: Drug Safety Check (Step 4)**
```
LLM Safety Review:
• Current: ["Ibuprofen"]
• Proposed: "Supportive care, hydration, platelet monitoring"
• Analysis: ⚠️ Ibuprofen + Dengue → High bleeding risk

Output:
{
  "warnings": ["Ibuprofen may increase bleeding risk"],
  "severity": "high",
  "review_required": true
}
                           ▼
```

**Phase 5: Final Report Assembly (Step 5)**
```json
{
  "diagnosis": {
    "diagnosis": "dengue",
    "confidence": 0.588,
    "uncertainty": true
  },
  "critical_flags": ["low platelets"],
  "treatment_plan": {
    "status": "draft_for_clinician_review",
    "management_options": [...]
  },
  "drug_interaction_check": {
    "warnings": ["Ibuprofen bleeding risk"],
    "severity": "high"
  },
  "dissenting_opinions": [
    {
      "disease": "malaria",
      "symptom_rank": 1,
      "lab_rank": 4,
      "note": "Symptom analysis ranks #1 but lab evidence ranks #4"
    }
  ]
}
```

---

## 🤖 Agent Specifications

| Agent | Role | Approach |
|-------|------|----------|
| **Symptom Analyzer** | Takes chief complaint + symptom list → retrieves relevant conditions from knowledge base → produces ranked differential diagnosis with reasoning | FAISS semantic retrieval + rule-based scoring |
| **Lab Interpreter** | Analyzes lab results in context of the differential → confirms/refutes hypotheses → flags critical values | Rule-based matching via `LAB_RULES` config |
| **Treatment Planner** | Synthesizes outputs from all agents → recommends treatment plan aligned with clinical guidelines → includes dosing, monitoring, and follow-up | RAG (guideline retrieval) + LLM formatting |
| **Drug Interaction Checker** | Reviews current medications + proposed treatments → checks for interactions, allergies, contraindications → flags risks | LLM-based safety review |

---

## ⚙️ Execution Flow — How It All Works

```mermaid
sequenceDiagram
    participant UI as Streamlit UI
    participant API as FastAPI
    participant Orch as Orchestrator
    participant SA as Symptom Analyzer
    participant LA as Lab Interpreter
    participant TP as Treatment Planner
    participant DC as Drug Checker
    participant FAISS as Vector Store
    participant LLM as Azure GPT

    UI->>API: POST /analyze (patient data)
    API->>Orch: orchestrator.run()
    
    par Parallel Execution
        Orch->>SA: analyze(symptoms)
        SA->>FAISS: retrieve_diseases()
        FAISS-->>SA: top-5 candidates
        SA-->>Orch: ranked differential
    and
        Orch->>LA: analyze(lab_results)
        LA->>LA: match LAB_RULES
        LA-->>Orch: lab hypotheses + flags
    end
    
    Orch->>Orch: arbitrate_diagnosis()
    Note right of Orch: Merge symptom + lab scores<br/>Detect dissenting opinions
    
    Orch->>TP: analyze(diagnosis, labs, drugs)
    TP->>FAISS: retrieve_guidelines()
    FAISS-->>TP: guideline chunks
    TP->>LLM: generate(guidelines, diagnosis)
    LLM-->>TP: structured treatment plan
    TP-->>Orch: management options
    
    Orch->>DC: check(meds, plan)
    DC->>LLM: safety_review()
    LLM-->>DC: interaction warnings
    DC-->>Orch: drug safety report
    
    Orch->>Orch: build_final_report()
    Orch-->>API: consolidated JSON report
    API-->>UI: display structured results
```

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Parallel Processing** | ThreadPoolExecutor runs Symptom + Lab agents concurrently (2× faster) |
| **Evidence Fusion** | Weighted arbitration (55% symptoms, 45% labs) prevents single-agent bias |
| **Transparency** | Dissenting opinions exposed when agents disagree by ≥2 ranks |
| **Safety-First** | Confidence gating (0.4 threshold), critical flag escalation, drug interaction validation |
| **Non-Prescriptive** | LLM prompts enforce "may consider" language, no imperative commands |
| **Guideline-Alignment** | RAG retrieval ensures every recommendation has evidence basis |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| Backend API | FastAPI + Uvicorn |
| LLM | Azure OpenAI (GPT) |
| Embeddings | Sentence-Transformers (`all-MiniLM-L6-v2`) |
| Vector Store | FAISS |
| Data | JSON disease database + chunked clinical guideline documents |

---

## Project Structure

```
clinical-AI_NW/
├── orchestrator.py                  # Pipeline coordinator
├── server.py                        # FastAPI backend
├── streamlit_app.py                 # Streamlit frontend
├── requirements.txt
├── .env                             # Azure OpenAI credentials
│
├── agents/
│   ├── symptom_analyzer.py          # Symptom → differential diagnosis
│   ├── lab_interpreter_agent.py     # Lab → hypothesis confirmation
│   ├── treatment_planner_agent.py   # Diagnosis → treatment plans
│   └── drug_interaction_checker_agent.py  # Medication safety
│
├── config/
│   ├── lab_rules.py                 # Rule-based lab thresholds
│   └── prompts.py                   # LLM system prompts
│
├── llm/
│   └── gemini_client.py             # Google Gemini wrapper
│
├── rag/
│   ├── embedder.py                  # Sentence-transformer encoding
│   ├── vector_store.py              # FAISS index management
│   ├── retriever.py                 # Semantic retrieval (diseases + guidelines)
│   ├── guideline_indexer.py         # Guideline chunk ingestion
│   └── ingest.py                    # Data ingestion pipeline
│
├── data/
│   ├── diseases.json                # Disease knowledge base
│   └── guidelines/                  # Clinical guideline text files
│
├── data_cleaning/
│   ├── guideline_preprocessor.py    # Guideline text chunking
│   └── pdf_TO_txt.py               # PDF → text extraction
│
└── models/
    └── all-MiniLM-L6-v2/           # Local embedding model
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Om-Shankar-Thakur/clinical-ai-multiagent.git
cd clinical-AI_NW
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your-api-key
GEMINI_MODEL=gemini-2.0-flash
```

### 5. Ingest data (first time only)

```bash
python rag/ingest.py
```

---

## Running the Application

### Start the FastAPI backend

```bash
uvicorn server:app --reload --port 8000
```

### Start the Streamlit frontend (in a separate terminal)

```bash
streamlit run streamlit_app.py
```

The UI will open at `http://localhost:8501`. The backend API is available at `http://localhost:8000/docs`.

---

## API Reference

### `POST /analyze`

Runs the full clinical pipeline.

**Request body:**
```json
{
  "chief_complaint": "High fever with body ache",
  "symptoms": ["fever", "body pain", "headache", "chills"],
  "lab_results": {"platelets": 80000, "hematocrit": 52},
  "current_medications": ["Ibuprofen"]
}
```

**Response:** Full orchestrator report with diagnosis, treatment plan, drug safety checks, and dissenting opinions.

### `GET /health`

Health check endpoint.

---

## Supported Lab Parameters

| Parameter | Critical Threshold | Signal |
|-----------|-------------------|--------|
| Platelets | < 100,000 | Low platelets (critical) |
| Hematocrit | > 50 | Elevated hematocrit |
| Sodium | > 145 | High sodium |
| Hemoglobin | < 10 | Low hemoglobin |
| Oxygen | < 92 | Low oxygen saturation (critical) |
| Glucose | > 200 | High blood sugar (critical) |

---

## License

This project is for educational and research purposes only. Not intended for clinical use without proper regulatory review and clinician oversight.
