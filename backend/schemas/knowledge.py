"""Human-authored task knowledge; capture roles are independent of review."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Step(BaseModel):
    model_config = ConfigDict(extra='forbid')
    step_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    title: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=4000)
    why: str = Field(default='', max_length=4000)
    tips: str = Field(default='', max_length=4000)
    common_errors: str = Field(default='', max_length=4000)
    safety: str = Field(default='', max_length=4000)
    acceptable_variation: str = Field(default='', max_length=4000)
    start_s: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    end_s: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    keyframe: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_.-]+\.png$')
    @model_validator(mode='after')
    def times(self):
        if (self.start_s is None) != (self.end_s is None):
            raise ValueError('Both start and end times are required')
        if self.start_s is not None and self.end_s <= self.start_s:
            raise ValueError('Step end must follow start')
        return self


class Procedure(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,64}$')
    version: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,32}$')
    title: str = Field(min_length=1, max_length=200)
    department: str = Field(max_length=100)
    tools: str = Field(max_length=4000)
    success_criteria: str = Field(max_length=4000)
    steps: list[Step] = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def unique_steps(self):
        if len({step.step_id for step in self.steps}) != len(self.steps):
            raise ValueError('Procedure step IDs must be unique')
        return self


class CaptureContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['expert', 'worker', 'demo'] = 'demo'
    task_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_.-]{1,64}$')
    procedure_version: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_.-]{1,32}$')
    reference_session_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_.-]{1,64}$')
    participant_id: str = Field(default='', max_length=100)
    consent_confirmed: bool = False
    purpose: str = Field(default='training_demo', max_length=200)
    trial_stage: Literal['reference', 'before_learning', 'after_learning', 'practice', 'technical'] = 'practice'
    @model_validator(mode='after')
    def selected(self):
        if self.role != 'demo' and (not self.task_id or not self.procedure_version
                                   or not self.participant_id.strip() or not self.consent_confirmed):
            raise ValueError('Task/version, participant and consent are required')
        if self.role == 'worker' and not self.reference_session_id:
            raise ValueError('Worker requires an approved expert reference')
        if self.role != 'worker' and self.reference_session_id:
            raise ValueError('Only a worker capture can select an expert reference')
        return self


class SessionKnowledge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(default=0, ge=0)
    context: CaptureContext
    source_session_name: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,100}$')
    reference_revision: int | None = Field(default=None, ge=1)
    steps: list[Step] = Field(default_factory=list, max_length=50)
    review_status: Literal['draft', 'approved', 'retired'] = 'draft'
    reviewer: str = Field(default='', max_length=100)
    review_rationale: str = Field(default='', max_length=4000)
    clarity_confirmed: bool = False
    outcome: Literal['unknown', 'passed', 'failed'] = 'unknown'
    prompt_count: int | None = Field(default=None, ge=0)
    confirmed_errors: str = Field(default='', max_length=4000)
    confirmed_error_count: int | None = Field(default=None, ge=0)
    conditions_note: str = Field(default='', max_length=2000)
    sop_viewed_confirmed: bool = False
    source_archive_sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    retention_policy: str = Field(default='local_project_review_required', max_length=200)
    license_status: Literal['unknown', 'project_internal', 'approved_for_training'] = 'unknown'
