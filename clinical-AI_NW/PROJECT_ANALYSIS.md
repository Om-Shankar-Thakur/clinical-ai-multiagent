# PROJECT_ANALYSIS.md — clinical-AI_NW

Read-only architectural analysis. No source code was modified while producing this document.

## 1. Architecture Overview

clinical-AI_NW is a multi-agent clinical decision-support prototype ("MedOrchestrator") composed of four layers:

- **Presentation**: `streamlit_app.py` — a form-based UI (chief complaint, symptoms, labs, medications) that calls the backend over HTTP and renders the structured JSON report.
- **API**: `server.py` — a FastAPI service exposing `/health` and `/analyze`, holding a single `ClinicalOrchestrator` instance built once at startup (`lifespan` context manager).
- **Orchestration**: `orchestrator.py` — `ClinicalOrchestrator` coordinates four specialist agents in a fixed 5-step pipeline (parallel analysis → arbitration → treatment planning → drug interaction check → report assembly).
- **Agents + Data/AI**: `agents/*.py` implement the specialist logic; `rag/*.py` implements embedding + FAISS retrieval; `llm/azure_client.py` wraps Azure OpenAI; `config/*.py` holds static rules and prompts; `data/` and `data_cleaning/` hold the knowledge base and the offline preprocessing pipeline that produced it.

The design intentionally keeps the LLM constrained to non-prescriptive language (system prompts explicitly forbid drug names/doses/imperatives) and forces every result through a "clinician action required" disclaimer — this is a decision-support tool, not an autonomous prescriber, and that constraint is enforced at the prompt layer and in the final report assembly.

## 2. Folder Structure

```
clinical-AI_NW/
├── server.py                 # FastAPI app (entry point for API)
├── streamlit_app.py           # Streamlit UI (entry point for frontend)
├── orchestrator.py            # ClinicalOrchestrator — pipeline coordinator
├── llm/azure_client.py        # AzureLLM — Azure OpenAI chat wrapper
├── agents/                    # 4 specialist agents
├── rag/                       # Embedding, FAISS vector store, retriever, indexers
├── config/                    # Static lab thresholds + LLM system prompts
├── data/                      # diseases.json, raw guidelines, processed JSONL chunks
├── data_cleaning/              # Offline PDF→TXT and guideline chunking pipeline
├── models/all-MiniLM-L6-v2/    # Local sentence-transformers model artifacts
├── vector_store.index/.meta    # Persisted FAISS index for diseases
├── guideline_store.index/.meta # Persisted FAISS index for guidelines
└── test*.py                   # Manual print-based test scripts (no pytest/asserts)
```

## 3. Execution Flow: Streamlit → FastAPI → Orchestrator → Agents

1. User fills the Streamlit form; on submit, `call_api()` does `requests.post("http://localhost:8000/analyze", json=payload, timeout=120)`.
2. FastAPI's `analyze_patient(patient: PatientInput)` validates the payload via Pydantic and calls the singleton `orchestrator.run(...)` synchronously.
3. `ClinicalOrchestrator.run()` executes:
   - **Step 1 (parallel, `ThreadPoolExecutor(max_workers=2)`)**: `SymptomAnalyzerAgent.analyze()` and `LabInterpreterAgent.analyze()` run concurrently.
   - **Step 2**: `_arbitrate_diagnosis()` merges both outputs with a weighted score (`0.55*symptom + 0.45*lab`), picks the top diagnosis, flags uncertainty and dissenting opinions — pure Python, no LLM call.
   - **Step 3**: `TreatmentPlannerAgent.analyze()` — gated by a confidence threshold (0.4), retrieves guideline chunks via RAG, calls Azure OpenAI, parses JSON.
   - **Step 4**: `DrugInteractionCheckerAgent.check()` — only if medications were supplied; calls Azure OpenAI, result parsed defensively by the orchestrator.
   - **Step 5**: `_build_final_report()` assembles the consolidated report with a fixed disclaimer and `clinician_action_required: True`.
4. FastAPI returns the report dict as JSON; Streamlit stores it in `st.session_state["report"]` and renders it through dedicated `render_*` functions.

## 4. Module Responsibilities

| Module | Responsibility |
|---|---|
| `server.py` | HTTP boundary, request/response schema, orchestrator lifecycle |
| `streamlit_app.py` | Pure UI — form input, API call, result rendering. No business logic. |
| `orchestrator.py` | Pipeline sequencing, diagnosis arbitration, report assembly, defensive JSON parsing |
| `agents/symptom_analyzer.py` | Semantic + overlap-based disease ranking from symptoms |
| `agents/lab_interpreter_agent.py` | Rule-based lab flag detection + lab-pattern disease matching |
| `agents/treatment_planner_agent.py` | RAG-grounded (intended) LLM treatment plan generation, confidence-gated |
| `agents/drug_interaction_checker_agent.py` | LLM-based interaction/warning check against proposed plan |
| `rag/embedder.py` | Wraps local SentenceTransformer model for text→vector encoding |
| `rag/vector_store.py` | FAISS `IndexFlatL2` + parallel metadata list, persisted via pickle |
| `rag/retriever.py` | Loads both disease and guideline vector stores; exposes retrieve_diseases/retrieve_guidelines |
| `rag/ingest.py` | Offline builder for the disease FAISS index |
| `rag/guideline_indexer.py` | Offline builder for the guideline FAISS index |
| `llm/azure_client.py` | Thin synchronous wrapper over `AzureOpenAI.chat.completions.create` |
| `config/lab_rules.py` | Hardcoded lab thresholds (platelets, hematocrit, sodium, hemoglobin, oxygen, glucose) |
| `config/prompts.py` | System prompts constraining LLM output format and forbidding prescriptive language |
| `data_cleaning/*.py` | Offline-only: PDF extraction and multi-stage guideline text cleaning/chunking |

## 5. RAG Pipeline

Intended flow: raw WHO guideline text → `data_cleaning/guideline_preprocessor.py` (boilerplate/TOC/OCR-artifact removal, table-to-prose conversion, semantic chunking to 400–700 tokens, metadata enrichment) → `data/processed/*.jsonl` → `rag/guideline_indexer.py` embeds `record["content"]` and stores `record["metadata"]` in FAISS → `rag/retriever.py` embeds a query and returns nearest chunks' metadata + distance.

**Critical defect found**: `guideline_indexer.py` stores only the metadata dict (source, document_name, disease, guideline_type, section_title, target_population, publication_year) as FAISS payload — the actual chunk text (`record["content"]`) is never persisted into the vector store metadata. `TreatmentPlannerAgent.analyze()` then reads `g.get("text", "")` from retrieved results, which does not exist on that metadata schema, so `guideline_text` injected into the LLM prompt is effectively always empty. The system currently behaves as an ungrounded LLM generator for treatment plans, not a RAG-grounded one, despite the architecture intending otherwise.

Disease retrieval (`rag/ingest.py` → `vector_store.index`) does not have this defect for its own use case (symptom matching doesn't need the "text" field), but shares the same "metadata lacks content string" pattern, which is a latent risk if any future consumer expects it.

## 6. Azure OpenAI Integration

`llm/azure_client.py`'s `AzureLLM` reads `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` from `.env` (via `python-dotenv`), constructs a synchronous `AzureOpenAI` client once, and exposes `generate(system_prompt, user_prompt)` → `chat.completions.create(model=deployment, messages=[...], temperature=0.2)` → returns `choices[0].message.content`. There is no retry, timeout, streaming, or async client (`AsyncAzureOpenAI` is not used) — every call blocks the calling thread for the full round trip.

## 7. FAISS Usage

`rag/vector_store.py`'s `VectorStore` wraps `faiss.IndexFlatL2(dim)` (exact brute-force L2 search, no approximate index type — fine at current small corpus sizes but won't scale past low-thousands of vectors without index-type changes). Metadata is kept in a parallel Python list and persisted separately via `pickle` alongside `faiss.write_index`/`read_index` (`.index` + `.meta` file pair). `search(query_vector, top_k)` returns metadata entries annotated with `distance`. Two independent stores exist: `vector_store` (diseases) and `guideline_store` (guidelines), each loaded fully into memory by every `SemanticRetriever` instance.

## 8. Embedding Generation

`rag/embedder.py`'s `Embedder` loads a local `SentenceTransformer("models/all-MiniLM-L6-v2")` (384-dim model, vendored under `models/`) and exposes `encode(texts)`, wrapping single strings into a list before calling `model.encode(texts, convert_to_tensor=False)`. The same model is used for both disease and guideline embeddings, and is reloaded independently by every `SemanticRetriever` instantiation (no shared/cached instance across agents).

## 9. Current Orchestrator Behavior

- Symptom and lab analysis run concurrently via a 2-worker thread pool; agent-level exceptions are caught and replaced with fallback structures rather than propagating.
- Diagnosis arbitration is a deterministic weighted-score merge with explicit uncertainty flagging (confidence < 0.6) and dissenting-opinion detection when symptom-rank and lab-rank diverge by ≥2 positions — this is the one purely algorithmic (non-LLM) decision point in the pipeline.
- Treatment planning is gated by a hard confidence threshold (0.4); below it, the LLM is never called and a fixed "insufficient confidence" response is returned instead.
- Drug interaction checking is skipped entirely if no current medications were supplied.
- Every path terminates in a report carrying `clinician_action_required: True` and a disclaimer — the orchestrator is deliberately conservative about failure modes, though logging is inconsistent (mixed `print()`/`logging` usage) which limits observability into how often fallback paths trigger in practice.

## 10. Most Important Files (ranked)

1. `orchestrator.py` — the entire pipeline's control flow and business logic lives here.
2. `agents/treatment_planner_agent.py` — highest-risk module (RAG defect lives here; also the primary LLM-output safety gate).
3. `rag/retriever.py` + `rag/vector_store.py` — the retrieval layer whose schema mismatch causes the RAG defect.
4. `llm/azure_client.py` — single point of integration with the only external network dependency (aside from HTTP itself).
5. `server.py` — API boundary and orchestrator lifecycle; also the point where async/sync blocking mismatch originates.
6. `agents/lab_interpreter_agent.py` — encodes clinically meaningful thresholds; fragile pattern-matching logic warrants scrutiny.
7. `config/prompts.py` — the actual safety contract with the LLM (non-prescriptive constraints) lives here as prompt text, not code — worth version-controlling carefully.
8. `data_cleaning/guideline_preprocessor.py` — determines what ends up in the knowledge base; offline but foundational to RAG quality once the retrieval defect is fixed.

## 11. Dependency Graph (textual)

```
streamlit_app.py
  └── requests → server.py (HTTP boundary)

server.py
  └── orchestrator.py
        ├── agents/symptom_analyzer.py
        │     └── rag/retriever.py
        │           ├── rag/embedder.py (SentenceTransformer)
        │           └── rag/vector_store.py (FAISS, "vector_store")
        ├── agents/lab_interpreter_agent.py
        │     ├── config/lab_rules.py
        │     └── data/diseases.json
        ├── agents/treatment_planner_agent.py
        │     ├── rag/retriever.py
        │     │     └── rag/vector_store.py (FAISS, "guideline_store")
        │     ├── llm/azure_client.py (AzureOpenAI)
        │     └── config/prompts.py
        └── agents/drug_interaction_checker_agent.py
              ├── llm/azure_client.py
              └── config/prompts.py

Offline-only (not in request path):
  data_cleaning/pdf_TO_txt.py → data_cleaning/guideline_preprocessor.py
    → data/processed/*.jsonl → rag/guideline_indexer.py → guideline_store.index/.meta
  data/diseases.json → rag/ingest.py → vector_store.index/.meta
```

## 12. Important Classes / Functions

- `ClinicalOrchestrator.run/_run_parallel/_arbitrate_diagnosis/_check_drug_interactions/_build_final_report/_safe_parse_json` (`orchestrator.py`)
- `AzureLLM.generate` (`llm/azure_client.py`)
- `SymptomAnalyzerAgent.analyze/rank_and_reason` (`agents/symptom_analyzer.py`)
- `LabInterpreterAgent.analyze/_match_lab_patterns` (`agents/lab_interpreter_agent.py`)
- `TreatmentPlannerAgent.analyze/_parse_response/_insufficient_confidence_response` (`agents/treatment_planner_agent.py`)
- `DrugInteractionCheckerAgent.check` (`agents/drug_interaction_checker_agent.py`)
- `SemanticRetriever.retrieve_diseases/retrieve_guidelines` (`rag/retriever.py`)
- `VectorStore.add/search/save/load` (`rag/vector_store.py`)
- `Embedder.encode` (`rag/embedder.py`)
- `GuidelineIndexer.build_index` / `DiseaseIndexer.build_index` (offline indexers)

## 13. Current Strengths

- Clear separation of concerns across layers (UI / API / orchestration / agents / RAG / LLM).
- Deliberate, prompt-enforced safety posture: no prescriptive drug/dose language, mandatory disclaimer, confidence gating before invoking the LLM for treatment planning.
- Deterministic, explainable arbitration logic (weighted scoring, dissenting-opinion detection) rather than opaque LLM-only diagnosis merging.
- Parallelized independent agent calls (symptom + lab) reduce latency.
- Defensive fallback structures on agent failure keep the pipeline from hard-crashing on partial failures.
- Offline preprocessing pipeline for guidelines is thorough (boilerplate/OCR cleanup, semantic chunking, metadata enrichment, dedup, validation).

## 14. Current Architectural Issues

1. **RAG guideline retrieval is effectively broken** — vector store metadata never persisted the chunk text/content field, so treatment plans are generated without actual guideline grounding despite the design intent (see §5).
2. **Blocking synchronous work inside async FastAPI handlers** — `/analyze` is `async def` but calls a fully synchronous pipeline (FAISS search + blocking Azure HTTP calls), stalling the single event loop under concurrent load.
3. **Redundant resource loading** — each agent's own `SemanticRetriever` reloads both FAISS indices and a fresh SentenceTransformer instance; no shared singleton across the orchestrator.
4. **No LLM resilience** — no retries, timeouts, or backoff around Azure OpenAI calls; any transient failure surfaces as a raw exception caught only by a generic `except Exception`.
5. **Invalid-JSON-shaped prompt in `DrugInteractionCheckerAgent`** — uses `str(dict)` (Python repr) instead of `json.dumps(dict)`, inconsistent with the strict-JSON contract used elsewhere.
6. **Hardcoded relative paths** (`data/diseases.json`, `models/all-MiniLM-L6-v2`, `"vector_store"`/`"guideline_store"`) break if the process isn't launched from repo root; inconsistent with the `BASE_DIR`-relative pattern already used in `guideline_indexer.py`/`pdf_TO_txt.py`.
7. **Naive lab-pattern matching** — substring checks on "elevated"/"low"/"reduced" with hardcoded normal-range fallbacks (`9999`/`0`) covering only 3 of the labs actually referenced.
8. **CORS wide open, no auth** on `/analyze` while handling clinical data — acceptable for local demo only.
9. **No input validation/bounds checking** on lab values in `PatientInput` (arbitrary keys/values accepted, including physiologically impossible numbers).
10. **Tight coupling / no dependency injection** — agents construct their own `AzureLLM()`/`SemanticRetriever()` internally, hindering testability (confirmed by manual, assert-free test scripts that can't mock these internals).
11. **Inconsistent logging** — mixed `print()` and `logging` usage across the orchestrator and agents limits production observability into fallback-path frequency.

## 15. Technical Debt

- No automated test suite — `test.py`, `test_orchestrator.py`, `test_treatment_planner.py` are manual, print-based scripts with no assertions/pytest integration, so regressions (like the RAG defect above) can pass unnoticed.
- No CI/lint/type-checking configuration observed.
- No package `__init__.py` confirmed for `agents/` (implicit namespace package) — packaging consistency should be verified.
- No environment/config validation at startup (missing `.env` values fail late, inside the first LLM call, not at orchestrator construction).
- No versioning or migration strategy for the FAISS index files (`.index`/`.meta`) as the underlying data/model changes — a stale index silently serves outdated results after `diseases.json` or guideline data is updated without re-running the indexers.

## 16. Suggested Improvements

*(For future work — no changes made in this task.)*

1. Fix the guideline vector store schema to persist chunk content, and add a test asserting non-empty `guideline_text` reaches the treatment-planner prompt.
2. Move blocking pipeline execution off the event loop (`run_in_executor`, or switch to a fully sync WSGI-style deployment, or adopt `AsyncAzureOpenAI` + async FAISS wrapper).
3. Promote `SemanticRetriever`/`Embedder`/FAISS stores to shared singletons constructed once at orchestrator/app startup and injected into agents.
4. Add retry/backoff/timeout wrapping around `AzureLLM.generate`.
5. Replace `str(dict)` with `json.dumps(dict)` in `DrugInteractionCheckerAgent`.
6. Resolve all data/model paths via `Path(__file__).parent`-based `BASE_DIR` constants, consistently.
7. Broaden lab-pattern normal-range coverage or replace substring heuristics with structured range data per lab.
8. Restrict CORS and add authentication before any non-local deployment; add clinical-value bounds validation in `PatientInput`.
9. Introduce constructor-based dependency injection for `AzureLLM`/`SemanticRetriever` in every agent to enable proper unit testing with mocks.
10. Standardize on `logging` (structured, leveled) throughout; add metrics/counters for fallback-path activation rate.
11. Add a pytest-based automated test suite with assertions, including a regression test for the RAG grounding defect.
12. Add an index-freshness check (e.g., hash of source data vs. stored index metadata) to detect stale FAISS indices.
