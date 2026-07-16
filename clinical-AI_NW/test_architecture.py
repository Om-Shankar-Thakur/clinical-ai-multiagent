# test_architecture.py

"""
Automated tests for the planner-executor architecture.

These tests deliberately avoid heavy dependencies (FAISS, sentence-transformers,
google-genai) by stubbing the agents that need them, so the framework logic can
be verified anywhere with a plain Python install:

    python test_architecture.py        # runs all checks, prints PASS/FAIL
    pytest test_architecture.py         # also works if pytest is installed

The real domain agents are exercised by test_orchestrator.py (which needs the
full environment + indices + GEMINI_API_KEY).
"""

from __future__ import annotations

import json

from core.registry import AgentRegistry
from core.memory import ClinicalMemory
from core.base_agent import BaseAgent
from core.contracts import AgentResult, ExecutionPlan
from execution.clinical_executor import ClinicalExecutor
from execution.plan_normalizer import PlanNormalizer
from planning.clinical_planner import ClinicalPlanner
from agents.diagnosis_arbiter_agent import DiagnosisArbiterAgent
from agents.lab_interpreter_agent import LabInterpreterAgent
from agents.supervisor_agent import SupervisorAgent
from agents.adapters import DiagnosisArbiterAdapter
from agents.supervisor_agent import SupervisorAdapter
from agents.bootstrap import build_default_registry


# --------------------------------------------------------------------------- #
#  Test doubles
# --------------------------------------------------------------------------- #
class _FakeLLM:
    def __init__(self, output: str):
        self._output = output

    def generate(self, system_prompt, user_prompt):
        return self._output


def _stub(name, deps=None, req=None, conf=0.5, output=None, boom=False):
    class _S(BaseAgent):
        pass
    _S.name = name
    _S.dependencies = deps or []
    _S.requires = req or []

    def execute(self, memory):
        if boom:
            raise AssertionError(f"{name} must not run")
        return AgentResult(agent=name, output=output or {}, confidence=conf)

    _S.execute = execute
    _S.__abstractmethods__ = frozenset()  # execute is now provided
    _S.__name__ = f"Stub_{name}"
    return _S


# --------------------------------------------------------------------------- #
#  Registry
# --------------------------------------------------------------------------- #
def test_registry_is_lazy_and_safe():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return _stub("x")()

    reg = AgentRegistry()
    reg.register("x", factory)
    assert calls["n"] == 0, "registering must not instantiate"
    inst1 = reg.get("x")
    inst2 = reg.get("x")
    assert inst1 is inst2, "registry must cache singletons"
    assert calls["n"] == 1, "factory must run exactly once"
    try:
        reg.get("missing")
        assert False, "unknown agent must raise"
    except KeyError:
        pass


# --------------------------------------------------------------------------- #
#  Plan normalizer
# --------------------------------------------------------------------------- #
def test_normalizer_stages_for_all_data_scenarios():
    norm = PlanNormalizer(build_default_registry())

    def stages(agents):
        return norm.to_stages(ExecutionPlan(agents=agents))

    # both intake + treatment + drug
    assert stages(["symptom_agent", "lab_agent", "treatment_planner", "drug_checker"]) == [
        ["lab_agent", "symptom_agent"],
        ["diagnosis_arbiter"],
        ["treatment_planner"],
        ["drug_checker"],
        ["supervisor"],
    ]
    # symptoms only + treatment
    assert stages(["symptom_agent", "treatment_planner"]) == [
        ["symptom_agent"], ["diagnosis_arbiter"], ["treatment_planner"], ["supervisor"],
    ]
    # lab only -> arbiter bridge added, supervisor last
    assert stages(["lab_agent"]) == [["lab_agent"], ["diagnosis_arbiter"], ["supervisor"]]
    # drug selected without treatment -> closure pulls treatment + arbiter
    st = stages(["symptom_agent", "lab_agent", "drug_checker"])
    assert st[-1] == ["supervisor"]
    assert ["treatment_planner"] in st and ["diagnosis_arbiter"] in st


# --------------------------------------------------------------------------- #
#  Planner (LLM + fallback)
# --------------------------------------------------------------------------- #
def test_planner_uses_llm_output_when_valid():
    llm = _FakeLLM(json.dumps({
        "agents": ["symptom_agent", "lab_agent", "treatment_planner"],
        "parallel": ["symptom_agent", "lab_agent"],
        "reasoning": "both present",
    }))
    plan = ClinicalPlanner(llm=llm).plan(
        {"symptoms": ["fever"], "lab_results": {"platelets": 80000}, "current_medications": []}
    )
    assert plan.source == "llm"
    assert plan.agents == ["symptom_agent", "lab_agent", "treatment_planner"]


def test_planner_filters_hallucinated_agents():
    llm = _FakeLLM(json.dumps({"agents": ["ghost", "lab_agent"], "parallel": [], "reasoning": "x"}))
    plan = ClinicalPlanner(llm=llm).plan({"lab_results": {"sodium": 150}})
    assert plan.source == "llm"
    assert plan.agents == ["lab_agent"]


def test_planner_falls_back_on_bad_json():
    plan = ClinicalPlanner(llm=_FakeLLM("not json")).plan(
        {"symptoms": ["cough"], "lab_results": {}, "current_medications": []}
    )
    assert plan.source == "fallback"
    assert plan.agents == ["symptom_agent", "treatment_planner"]


# --------------------------------------------------------------------------- #
#  Lab interpreter: critical findings must contribute to lab_score via
#  synonym-mapped patterns (regression test for the "lab score always 0 for
#  hypoxemia-related diagnoses" bug: "low oxygen saturation" previously
#  extracted the key "oxygen saturation", which never matched the actual
#  lab_results field "oxygen").
# --------------------------------------------------------------------------- #
def test_lab_interpreter_matches_critical_oxygen_synonym():
    agent = LabInterpreterAgent()
    out = agent.analyze({
        "platelets": 120000, "hemoglobin": 10, "hematocrit": 40,
        "sodium": 140, "oxygen": 87, "glucose": 100,
    })
    assert "low oxygen saturation" in out["critical_flags"]
    by_disease = {h["disease"]: h for h in out["lab_hypotheses"]}
    assert "Community-Acquired Pneumonia" in by_disease
    assert by_disease["Community-Acquired Pneumonia"]["score"] > 0
    assert "low oxygen saturation" in by_disease["Community-Acquired Pneumonia"]["matched_lab_patterns"]


def test_lab_interpreter_matches_high_direction_not_just_elevated():
    # Regression test: the original code only recognised "elevated", so
    # "high glucose" never matched regardless of the glucose value.
    agent = LabInterpreterAgent()
    out = agent.analyze({"glucose": 250})
    by_disease = {h["disease"]: h for h in out["lab_hypotheses"]}
    matched_any_high_glucose = any(
        "high glucose" in h["matched_lab_patterns"] for h in out["lab_hypotheses"]
    )
    assert matched_any_high_glucose, "high glucose pattern should match when glucose > 200"


# --------------------------------------------------------------------------- #
#  Arbiter (numeric behaviour preserved)
# --------------------------------------------------------------------------- #
def test_arbiter_weighting_is_preserved():
    symptom = {"differential_diagnosis": [
        {"disease": "Dengue", "score": 0.8,
         "reasoning": {"confidence": "high", "matched_symptoms": ["fever"], "missing_symptoms": []},
         "description": "v"}]}
    lab = {"lab_hypotheses": [
        {"disease": "Dengue", "score": 0.7, "lab_support": "supports", "matched_lab_patterns": ["low platelets"]}]}
    out, dissent = DiagnosisArbiterAgent().arbitrate(symptom, lab)
    # 0.55*0.8 + 0.45*0.7 = 0.755
    assert out["final"]["diagnosis"] == "dengue"
    assert out["final"]["confidence"] == 0.755


# --------------------------------------------------------------------------- #
#  Supervisor
# --------------------------------------------------------------------------- #
def test_supervisor_flags_diagnosis_hallucination():
    ctx = {
        "diagnosis": {"diagnosis": "dengue", "confidence": 0.75, "uncertainty": False},
        "ranked_candidates": [{"disease": "dengue"}],
        "dissenting_opinions": [],
        "treatment": {"recommendation_status": "draft_for_clinician_review",
                      "primary_diagnosis": "typhoid", "management_options": [{"option": "x"}]},
        "drug": {"review_required": False, "severity": "low"},
        "current_medications": [],
        "agent_confidences": {"diagnosis_arbiter": 0.75, "treatment_planner": 0.75},
    }
    review = SupervisorAgent().review(ctx)
    assert review["approval_status"] == "rejected"
    assert not review["checks"]["treatment_diagnosis_consistent"]


def test_supervisor_approves_clean_case():
    ctx = {
        "diagnosis": {"diagnosis": "dengue", "confidence": 0.75, "uncertainty": False},
        "ranked_candidates": [{"disease": "dengue"}],
        "dissenting_opinions": [],
        "treatment": {"recommendation_status": "draft_for_clinician_review",
                      "primary_diagnosis": "dengue", "management_options": [{"option": "x"}]},
        "drug": {},
        "current_medications": [],
        "agent_confidences": {"diagnosis_arbiter": 0.75, "treatment_planner": 0.75},
    }
    review = SupervisorAgent().review(ctx)
    assert review["approval_status"] == "approved"


# --------------------------------------------------------------------------- #
#  Executor ordering + tracing
# --------------------------------------------------------------------------- #
def _diagnostic_registry(**overrides):
    reg = AgentRegistry()
    reg.register("symptom_agent", overrides.get("symptom_agent") or _stub(
        "symptom_agent", output={"differential_diagnosis": [
            {"disease": "Dengue", "score": 0.8,
             "reasoning": {"confidence": "high", "matched_symptoms": ["fever"], "missing_symptoms": []},
             "description": "v"}]}, conf=0.8))
    reg.register("lab_agent", overrides.get("lab_agent") or _stub(
        "lab_agent", output={"lab_hypotheses": [
            {"disease": "Dengue", "score": 0.7, "lab_support": "supports", "matched_lab_patterns": ["low platelets"]}],
            "critical_flags": ["low platelets"], "lab_signals": ["low platelets"]}, conf=0.7))
    reg.register("diagnosis_arbiter", DiagnosisArbiterAdapter)
    reg.register("treatment_planner", overrides.get("treatment_planner") or _stub(
        "treatment_planner", deps=["diagnosis_arbiter"], req=["diagnosis_arbiter"],
        output={"recommendation_status": "draft_for_clinician_review",
                "primary_diagnosis": "dengue", "management_options": [{"option": "rest"}],
                "uncertainty_notes": []}, conf=0.7))
    reg.register("drug_checker", overrides.get("drug_checker") or _stub(
        "drug_checker", deps=["treatment_planner"], req=["treatment_planner"],
        output={"warnings": [], "severity": "low", "review_required": False}, conf=0.9))
    reg.register("supervisor", SupervisorAdapter)
    return reg


def test_executor_orders_stages_and_traces():
    reg = _diagnostic_registry()
    mem = ClinicalMemory()
    mem.set_patient_context(chief_complaint="fever", symptoms=["fever"],
                            lab_results={"platelets": 80000}, current_medications=["x"])
    trace = ClinicalExecutor(reg, mem).execute(
        ExecutionPlan(agents=["symptom_agent", "lab_agent", "treatment_planner", "drug_checker"]),
        execution_id="exec-unit",
    )
    order = [r.agent for r in trace.records]
    assert order == ["lab_agent", "symptom_agent", "diagnosis_arbiter",
                     "treatment_planner", "drug_checker", "supervisor"]
    assert all(r.execution_id == "exec-unit" for r in trace.records)
    assert all(r.latency_ms >= 0 for r in trace.records)
    assert trace.records[-1].agent == "supervisor"


# --------------------------------------------------------------------------- #
#  Orchestrator: backward-compat + dynamic routing
# --------------------------------------------------------------------------- #
def _make_orchestrator(registry, llm):
    from orchestrator import ClinicalOrchestrator
    orch = ClinicalOrchestrator.__new__(ClinicalOrchestrator)
    orch.registry = registry
    orch._planner_llm = llm
    return orch


LEGACY_KEYS = [
    "patient_input", "diagnosis", "ranked_candidates", "lab_signals",
    "critical_flags", "treatment_plan", "drug_interaction_check",
    "dissenting_opinions", "clinician_action_required", "disclaimer",
]
ADDITIVE_KEYS = ["execution_plan", "execution_trace", "supervisor_review", "agent_confidences"]


def test_orchestrator_preserves_report_schema():
    reg = _diagnostic_registry()
    llm = _FakeLLM(json.dumps({
        "agents": ["symptom_agent", "lab_agent", "treatment_planner", "drug_checker"],
        "parallel": ["symptom_agent", "lab_agent"], "reasoning": "all"}))
    rep = _make_orchestrator(reg, llm).run("fever", ["fever"], {"platelets": 80000}, ["Ibuprofen"])
    for k in LEGACY_KEYS:
        assert k in rep, f"missing legacy key {k}"
    for k in ADDITIVE_KEYS:
        assert k in rep, f"missing additive key {k}"
    assert rep["diagnosis"]["diagnosis"] == "dengue"
    assert rep["clinician_action_required"] is True


def test_orchestrator_dynamic_routing_skips_unneeded_agents():
    # lab + drug agents raise if ever run; a symptoms-only plan must skip them.
    reg = _diagnostic_registry(
        lab_agent=_stub("lab_agent", boom=True),
        drug_checker=_stub("drug_checker", deps=["treatment_planner"], req=["treatment_planner"], boom=True),
    )
    llm = _FakeLLM(json.dumps({
        "agents": ["symptom_agent", "treatment_planner"], "parallel": [], "reasoning": "symptoms only"}))
    rep = _make_orchestrator(reg, llm).run("headache", ["headache"], {}, [])
    steps = [s["agent"] for s in rep["execution_trace"]["steps"]]
    assert "lab_agent" not in steps
    assert "drug_checker" not in steps
    assert steps == ["symptom_agent", "diagnosis_arbiter", "treatment_planner", "supervisor"]
    assert rep["lab_signals"] == []
    assert rep["drug_interaction_check"]["review_required"] is False


# --------------------------------------------------------------------------- #
#  Runner
# --------------------------------------------------------------------------- #
def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return passed == len(tests)


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_all() else 1)
