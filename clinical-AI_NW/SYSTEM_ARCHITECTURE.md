# SYSTEM_ARCHITECTURE.md — clinical-AI_NW

Read-only architecture/diagram document. No source code was modified while producing this document.

## 1. High-Level Architecture

```mermaid
flowchart TB
    subgraph Presentation
        UI[Streamlit App<br/>streamlit_app.py]
    end

    subgraph API_Layer["API Layer"]
        API[FastAPI Server<br/>server.py<br/>/health, /analyze]
    end

    subgraph Orchestration
        ORCH[ClinicalOrchestrator<br/>orchestrator.py]
    end

    subgraph Agents
        SA[SymptomAnalyzerAgent]
        LA[LabInterpreterAgent]
        TP[TreatmentPlannerAgent]
        DI[DrugInteractionCheckerAgent]
    end

    subgraph RAG_Layer["RAG Layer"]
        EMB[Embedder<br/>SentenceTransformer MiniLM-L6-v2]
        VS1[VectorStore: vector_store<br/>FAISS IndexFlatL2 - diseases]
        VS2[VectorStore: guideline_store<br/>FAISS IndexFlatL2 - guidelines]
        RET[SemanticRetriever]
    end

    subgraph External
        AZ[Azure OpenAI<br/>Chat Completions]
    end

    subgraph Config_Data["Config & Data"]
        RULES[config/lab_rules.py]
        PROMPTS[config/prompts.py]
        DISEASES[data/diseases.json]
        GUIDES[data/processed/*.jsonl]
    end

    UI -- "POST /analyze (JSON)" --> API
    API --> ORCH
    ORCH --> SA
    ORCH --> LA
    ORCH --> TP
    ORCH --> DI

    SA --> RET
    TP --> RET
    RET --> EMB
    RET --> VS1
    RET --> VS2

    LA --> RULES
    LA --> DISEASES
    VS2 -. "built offline from" .-> GUIDES

    TP --> AZ
    DI --> AZ
    TP -.-> PROMPTS
    DI -.-> PROMPTS

    ORCH -- "JSON report" --> API
    API -- "JSON response" --> UI
```

## 2. Component Diagram

```mermaid
flowchart LR
    subgraph Frontend
        ST[streamlit_app.py]
    end

    subgraph Backend
        SV[server.py<br/>PatientInput / HealthResponse]
        OR[orchestrator.py<br/>ClinicalOrchestrator]
    end

    subgraph AgentLayer["agents/"]
        A1[symptom_analyzer.py]
        A2[lab_interpreter_agent.py]
        A3[treatment_planner_agent.py]
        A4[drug_interaction_checker_agent.py]
    end

    subgraph RAGLayer["rag/"]
        R1[embedder.py]
        R2[vector_store.py]
        R3[retriever.py]
        R4[ingest.py — offline]
        R5[guideline_indexer.py — offline]
    end

    subgraph LLMLayer["llm/"]
        L1[azure_client.py<br/>AzureLLM]
    end

    subgraph ConfigLayer["config/"]
        C1[lab_rules.py]
        C2[prompts.py]
    end

    subgraph OfflinePipeline["data_cleaning/ (offline)"]
        D1[pdf_TO_txt.py]
        D2[guideline_preprocessor.py]
    end

    ST -->|HTTP| SV
    SV --> OR
    OR --> A1 & A2 & A3 & A4
    A1 --> R3
    A3 --> R3
    R3 --> R1
    R3 --> R2
    A2 --> C1
    A3 --> L1
    A4 --> L1
    A3 --> C2
    A4 --> C2
    L1 -->|HTTPS| AZURE[(Azure OpenAI)]
    D1 --> D2 --> R5 --> R2
    R4 --> R2
```

## 3. Agent Communication

```mermaid
sequenceDiagram
    participant O as ClinicalOrchestrator
    participant SA as SymptomAnalyzerAgent
    participant LA as LabInterpreterAgent
    participant TP as TreatmentPlannerAgent
    participant DI as DrugInteractionCheckerAgent

    Note over O: Step 1 — ThreadPoolExecutor(max_workers=2)
    par Parallel analysis
        O->>SA: analyze(chief_complaint, symptoms)
        SA-->>O: symptom_candidates, confidence
    and
        O->>LA: analyze(lab_results)
        LA-->>O: lab_hypotheses, critical_flags, lab_signals
    end

    Note over O: Step 2 — pure Python arbitration (no agent call)
    O->>O: _arbitrate_diagnosis()<br/>0.55*symptom + 0.45*lab score

    Note over O: Step 3 — confidence-gated
    alt confidence >= 0.4
        O->>TP: analyze(diagnosis_output, lab_output)
        TP-->>O: treatment_plan (or insufficient-confidence response)
    else confidence < 0.4
        O->>O: _insufficient_confidence_response()
    end

    Note over O: Step 4 — only if medications supplied
    alt current_medications provided
        O->>DI: check(diagnosis, medications, treatment_plan)
        DI-->>O: raw LLM text -> _safe_parse_json()
    else no medications
        O->>O: skip drug interaction check
    end

    Note over O: Step 5
    O->>O: _build_final_report()
```

## 4. Sequence Diagram — Full Request

```mermaid
sequenceDiagram
    actor User
    participant ST as Streamlit UI
    participant API as FastAPI /analyze
    participant O as ClinicalOrchestrator
    participant RET as SemanticRetriever
    participant FAISS as FAISS VectorStore
    participant AZ as Azure OpenAI

    User->>ST: Fill form, click Analyze
    ST->>API: POST /analyze (JSON payload)
    API->>O: orchestrator.run(...)

    O->>O: _run_parallel() [symptom + lab agents]
    O->>RET: retrieve_diseases(symptoms)
    RET->>FAISS: search(embedded query, top_k=5)
    FAISS-->>RET: nearest disease metadata + distance
    RET-->>O: ranked disease candidates

    O->>O: _arbitrate_diagnosis()

    O->>RET: retrieve_guidelines(diagnosis query)
    RET->>FAISS: search(embedded query, top_k=5)
    FAISS-->>RET: guideline metadata (chunk text NOT stored — known defect)
    RET-->>O: guideline context (currently empty)

    O->>AZ: chat.completions.create (treatment planner prompt)
    AZ-->>O: JSON treatment plan text

    opt medications provided
        O->>AZ: chat.completions.create (drug interaction prompt)
        AZ-->>O: JSON interaction warnings text
    end

    O->>O: _build_final_report()
    O-->>API: report dict
    API-->>ST: JSON response
    ST-->>User: Rendered diagnosis, labs, treatment plan, warnings
```

## 5. Data Flow

```mermaid
flowchart LR
    IN[Patient Input:<br/>chief_complaint, symptoms,<br/>lab_results, medications] --> PARSE[Pydantic PatientInput]
    PARSE --> ORCH[ClinicalOrchestrator.run]

    ORCH --> SYM[Symptom candidates + confidence]
    ORCH --> LAB[Lab signals + critical flags + hypotheses]
    SYM --> ARB[Weighted arbitration]
    LAB --> ARB
    ARB --> DIAG[Primary diagnosis + dissenting opinions]

    DIAG --> PLAN[Treatment plan generation<br/>confidence-gated]
    PLAN --> DRUG{Medications supplied?}
    DRUG -- yes --> INTX[Drug interaction warnings]
    DRUG -- no --> SKIP[Skipped]

    DIAG --> REPORT[Final Report]
    PLAN --> REPORT
    INTX --> REPORT
    SKIP --> REPORT
    LAB --> REPORT
    REPORT --> OUT[JSON response -> Streamlit render]
```

## 6. RAG Flow

```mermaid
flowchart TB
    subgraph Offline["Offline Indexing (run manually)"]
        PDF[Raw WHO PDFs] --> P2T[pdf_TO_txt.py]
        P2T --> TXT[data/guidelines/*.txt]
        TXT --> PRE[guideline_preprocessor.py<br/>clean, chunk 400-700 tokens, enrich metadata]
        PRE --> JSONL[data/processed/*.jsonl<br/>content + metadata]
        JSONL --> GIDX[guideline_indexer.py]
        GIDX --> EMB1[Embedder.encode]
        EMB1 --> GSTORE[(guideline_store.index/.meta)]

        DISEASES[data/diseases.json] --> DIDX[ingest.py]
        DIDX --> EMB2[Embedder.encode]
        EMB2 --> DSTORE[(vector_store.index/.meta)]
    end

    subgraph Runtime["Runtime Retrieval"]
        Q1[Symptom query] --> ENC1[Embedder.encode]
        ENC1 --> SEARCH1[VectorStore.search - disease store]
        SEARCH1 --> DSTORE
        DSTORE --> RESULT1[Ranked disease metadata + distance]

        Q2["diagnosis + 'treatment management guidelines'"] --> ENC2[Embedder.encode]
        ENC2 --> SEARCH2[VectorStore.search - guideline store]
        SEARCH2 --> GSTORE
        GSTORE --> RESULT2["Guideline metadata (no chunk text — defect)"]
    end

    RESULT2 --> WARN["⚠ TreatmentPlannerAgent reads g.get('text','')<br/>which is absent from stored metadata schema"]
```

## 7. LLM Flow

```mermaid
sequenceDiagram
    participant Agent as Treatment/DrugInteraction Agent
    participant LLM as AzureLLM (llm/azure_client.py)
    participant SDK as AzureOpenAI SDK client
    participant Azure as Azure OpenAI Service

    Agent->>LLM: generate(system_prompt, user_prompt)
    LLM->>SDK: chat.completions.create(model=deployment,<br/>messages=[system, user], temperature=0.2)
    SDK->>Azure: HTTPS request (sync, no timeout/retry)
    Azure-->>SDK: completion response
    SDK-->>LLM: response.choices[0].message.content
    LLM-->>Agent: raw text (agent parses as JSON)

    Note over LLM,Azure: No retry/backoff/streaming.<br/>Any failure raises uncaught exception<br/>up to agent's try/except Exception.
```

## 8. API Flow

```mermaid
sequenceDiagram
    participant Client as Streamlit (requests)
    participant FastAPI as server.py
    participant Orch as ClinicalOrchestrator (singleton)

    Note over FastAPI: startup (lifespan)
    FastAPI->>Orch: ClinicalOrchestrator() — builds agents,<br/>loads FAISS + embedding model

    Client->>FastAPI: GET /health
    FastAPI-->>Client: HealthResponse

    Client->>FastAPI: POST /analyze {PatientInput}
    alt orchestrator ready
        FastAPI->>Orch: orchestrator.run(...) [blocking, sync]
        Orch-->>FastAPI: report dict
        FastAPI-->>Client: 200 JSON report
    else orchestrator not ready
        FastAPI-->>Client: 503 Orchestrator not ready
    end

    Note over FastAPI: async def handler but orchestrator.run()<br/>is synchronous — blocks the event loop<br/>for the full pipeline duration (FAISS + Azure calls)
```

## 9. Thread Execution

```mermaid
flowchart TB
    MAIN[orchestrator.run - main thread] --> POOL[ThreadPoolExecutor max_workers=2]
    POOL --> T1[Thread 1:<br/>symptom_agent.analyze]
    POOL --> T2[Thread 2:<br/>lab_agent.analyze]
    T1 --> JOIN[as_completed - collect results]
    T2 --> JOIN
    JOIN --> ERR{Exception per agent?}
    ERR -- yes --> FALLBACK[_agent_error_fallback]
    ERR -- no --> RESULT[agent output]
    FALLBACK --> MAIN2[main thread continues:<br/>arbitration, treatment, drug check]
    RESULT --> MAIN2

    style MAIN2 fill:#f9f,stroke:#333
    note1["Steps 2-5 (arbitration, treatment planning,<br/>drug interaction check, report build)<br/>run sequentially on the main thread —<br/>Azure OpenAI calls block it directly."]
```

## 10. Vector Search Pipeline

```mermaid
flowchart LR
    QUERY[Query text<br/>symptoms list OR diagnosis+guideline query] --> ENC[Embedder.encode<br/>SentenceTransformer MiniLM-L6-v2, 384-dim]
    ENC --> VEC[Query vector float32]
    VEC --> IDX{Which index?}
    IDX -- disease --> FAISS1[faiss.IndexFlatL2.search<br/>vector_store.index]
    IDX -- guideline --> FAISS2[faiss.IndexFlatL2.search<br/>guideline_store.index]
    FAISS1 --> META1[Lookup parallel metadata list<br/>by returned indices]
    FAISS2 --> META2[Lookup parallel metadata list<br/>by returned indices]
    META1 --> OUT1["[{...disease metadata, distance}]"]
    META2 --> OUT2["[{...guideline metadata (no content!), distance}]"]
    OUT1 --> SA[SymptomAnalyzerAgent scoring]
    OUT2 --> TP[TreatmentPlannerAgent prompt injection]
```

## Notes on Diagram Accuracy

These diagrams reflect the codebase as read during this analysis, including the known guideline-RAG content-field defect (see `PROJECT_ANALYSIS.md` §5, §14.1) and the sync-blocking-in-async-handler issue (§14.2). No source files were changed in producing this document.
