"""Pydantic models for benchmark data contracts.

These models are the internal representation. They must serialize
to the public JSON schemas under schemas/.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Variant(str, Enum):
    baseline = "baseline"
    tool_variant = "tool_variant"


class BenchmarkTrack(str, Enum):
    legacy_agent = "legacy_agent"
    tool_only = "tool_only"
    quality_eval = "quality_eval"


class EvaluatorModelClass(str, Enum):
    none = "none"
    small = "small"
    expensive = "expensive"


class RunStatus(str, Enum):
    passed = "passed"
    failed = "failed"
    error = "error"


class RunValidity(str, Enum):
    valid = "valid"
    invalid = "invalid"


class ValidationStatus(str, Enum):
    passed = "passed"
    failed = "failed"
    skipped = "skipped"


class CorrectnessScore(str, Enum):
    passed = "pass"
    minor_issue = "minor_issue"
    failed = "fail"


class SafetyScore(str, Enum):
    clear = "clear"
    review_needed = "review_needed"
    unsafe = "unsafe"


# --- Task manifest models ---


class CompletionContract(BaseModel):
    kind: str
    fields: list[str] = Field(default_factory=list)


class TaskStep(BaseModel):
    step_id: str
    name: str
    objective: str
    required_tool: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    completion_contract: CompletionContract
    artifact_requirements: list[str] = Field(default_factory=list)


class BaselinePolicy(BaseModel):
    remove_tool_under_test: bool = True


class ToolVariantPolicy(BaseModel):
    enforce_tool_under_test: bool = True


class TaskManifest(BaseModel):
    task_id: str
    title: str
    family: str
    repo: str
    pinned_commit: str
    objective: str
    task_description: str
    success_criteria: list[str]
    validation_commands: list[str]
    human_review_triggers: list[str] = Field(default_factory=list)
    fixture_files: list[str] = Field(default_factory=list)
    steps: list[TaskStep]
    baseline_policy: BaselinePolicy = Field(default_factory=BaselinePolicy)
    tool_variant_policy: ToolVariantPolicy = Field(default_factory=ToolVariantPolicy)


class InputArtifactSpec(BaseModel):
    name: str
    source: str
    target_name: str
    primary: bool = False


class ToolInvocationSpec(BaseModel):
    tool_id: str
    args: list[str] = Field(default_factory=list)
    baseline_args: list[str] = Field(default_factory=list)
    output_artifact: str = "tool_output.txt"
    output_mode: str = "stdout"
    baseline_strategy: str = "identity"
    timeout_seconds: float = 120.0


class DeterministicCheckSpec(BaseModel):
    name: str
    command: str


class QualityEvalSpec(BaseModel):
    question: str
    raw_validation_commands: list[str] = Field(default_factory=list)
    reduced_validation_commands: list[str] = Field(default_factory=list)
    small_model_allowed: bool = True
    expensive_model_allowed: bool = False
    escalation_note: str | None = None


class V2TaskManifest(BaseModel):
    version: str = "v2"
    task_id: str
    title: str
    family: str
    repo: str
    pinned_commit: str
    objective: str
    task_description: str
    success_criteria: list[str]
    human_review_triggers: list[str] = Field(default_factory=list)
    input_artifacts: list[InputArtifactSpec]
    tool_invocation: ToolInvocationSpec
    deterministic_checks: list[DeterministicCheckSpec] = Field(default_factory=list)
    quality_evaluation: QualityEvalSpec | None = None


class PhaseRecord(BaseModel):
    name: str
    track: BenchmarkTrack
    status: RunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    validation_status: ValidationStatus = ValidationStatus.skipped
    notes: list[str] = Field(default_factory=list)


class ToolEfficacyMetrics(BaseModel):
    raw_bytes: int | None = None
    reduced_bytes: int | None = None
    raw_tokens: int | None = None
    reduced_tokens: int | None = None
    reduction_ratio: float | None = None
    deterministic_valid: bool | None = None
    deterministic_check_count: int = 0


class QualityRetentionMetrics(BaseModel):
    raw_quality_score: float | None = None
    reduced_quality_score: float | None = None
    quality_delta: float | None = None
    llm_call_count_small: int = 0
    llm_call_count_expensive: int = 0
    escalation_reason: str | None = None
    evaluator_model_class: EvaluatorModelClass = EvaluatorModelClass.none
    raw_llm_tokens: int | None = None
    reduced_llm_tokens: int | None = None


# --- Run record models ---


class RunRecord(BaseModel):
    run_id: str
    task_id: str
    family: str
    variant: Variant
    agent_id: str
    adapter_version: str
    repo_commit: str
    status: RunStatus
    validity: RunValidity
    reported_input_tokens: int | None = None
    reported_output_tokens: int | None = None
    reported_total_tokens: int | None = None
    elapsed_seconds: float | None = None
    repair_iterations: int = 0
    validation_status: ValidationStatus
    files_changed: int = 0
    diff_size: int = 0
    artifact_dir: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    track: BenchmarkTrack = BenchmarkTrack.legacy_agent
    task_version: str | None = None
    phase_records: list[PhaseRecord] = Field(default_factory=list)
    tool_metrics: ToolEfficacyMetrics | None = None
    quality_metrics: QualityRetentionMetrics | None = None


# --- Qualification models ---


class QualificationRecord(BaseModel):
    agent_id: str
    adapter_version: str
    qualified: bool
    reported_token_support: bool = False
    forced_tool_support: bool = False
    trace_support: bool = False
    run_completion_support: bool = False
    failure_reason: str | None = None
    evidence_paths: list[str] = Field(default_factory=list)


# --- Event models ---


class EventRecord(BaseModel):
    timestamp: datetime
    run_id: str
    step_id: str
    event_type: str
    actor: str
    payload: dict = Field(default_factory=dict)


# --- Scorecard models ---


class VariantMetrics(BaseModel):
    """Averaged metrics for one variant (baseline or tool_variant) within a family."""

    variant: Variant
    run_count: int
    avg_tokens: float | None = None
    std_dev_tokens: float | None = None
    validation_pass_rate: float | None = None
    first_pass_success_rate: float | None = None
    avg_repair_iterations: float | None = None
    avg_elapsed_seconds: float | None = None
    std_dev_elapsed: float | None = None


class FamilyScorecard(BaseModel):
    """Per-family comparison between the baseline and tool_variant."""

    family: str
    baseline: VariantMetrics
    tool_variant: VariantMetrics
    token_delta: float | None = None
    token_reduction_pct: float | None = None


class SuiteScorecard(BaseModel):
    """Full suite scorecard aggregating all family results with suite-level metadata."""

    agent_id: str
    generated_at: datetime
    repo_commit: str
    families: list[FamilyScorecard] = Field(default_factory=list)


class ToolEfficacyVariantMetrics(BaseModel):
    variant: Variant
    run_count: int
    avg_raw_bytes: float | None = None
    avg_reduced_bytes: float | None = None
    avg_raw_tokens: float | None = None
    avg_reduced_tokens: float | None = None
    avg_reduction_ratio: float | None = None
    deterministic_pass_rate: float | None = None
    avg_elapsed_seconds: float | None = None


class ToolEfficacyFamilyScorecard(BaseModel):
    family: str
    baseline: ToolEfficacyVariantMetrics
    tool_variant: ToolEfficacyVariantMetrics


class ToolEfficacySuiteScorecard(BaseModel):
    generated_at: datetime
    repo_commit: str
    families: list[ToolEfficacyFamilyScorecard] = Field(default_factory=list)


class QualityRetentionVariantMetrics(BaseModel):
    variant: Variant
    run_count: int
    avg_raw_quality_score: float | None = None
    avg_reduced_quality_score: float | None = None
    avg_quality_delta: float | None = None
    llm_call_count_small: int = 0
    llm_call_count_expensive: int = 0
    avg_raw_llm_tokens: float | None = None
    avg_reduced_llm_tokens: float | None = None


class QualityRetentionFamilyScorecard(BaseModel):
    family: str
    baseline: QualityRetentionVariantMetrics
    tool_variant: QualityRetentionVariantMetrics


class QualityRetentionSuiteScorecard(BaseModel):
    generated_at: datetime
    repo_commit: str
    families: list[QualityRetentionFamilyScorecard] = Field(default_factory=list)
