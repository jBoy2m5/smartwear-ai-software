from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkerType(str, Enum):
    EXPERT = "EXPERT"
    TRAINEE = "TRAINEE"


class ActionPhase(BaseModel):
    phase: str
    start_time: float = Field(ge=0)
    end_time: float = Field(ge=0)
    peak_force_N: Optional[float] = None

    @model_validator(mode="after")
    def end_time_follows_start_time(self):
        if self.end_time < self.start_time:
            raise ValueError("end_time must be greater than or equal to start_time")
        return self


class DtwMetrics(BaseModel):
    similarity_score: float = Field(ge=0, le=100)
    muda_detected_seconds: float = Field(ge=0)


class RobotTrajectoryPoint(BaseModel):
    t: float = Field(ge=0)
    pos: List[float] = Field(min_length=3, max_length=3)
    force: float = Field(ge=0)


class SessionIngest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "session_id": "CYCLE_DENSO_001",
                    "worker_type": "EXPERT",
                    "key_frames": [
                        "frame_assemble_01.jpg",
                        "frame_assemble_02.jpg",
                    ],
                    "action_phases": [
                        {"phase": "REACH", "start_time": 0.0, "end_time": 1.8},
                        {
                            "phase": "ASSEMBLY",
                            "start_time": 1.8,
                            "end_time": 4.2,
                            "peak_force_N": 5.4,
                        },
                    ],
                    "dtw_metrics": {
                        "similarity_score": 91.5,
                        "muda_detected_seconds": 0.8,
                    },
                    "robot_trajectory_points": [
                        {"t": 0.1, "pos": [0.12, 0.45, 0.88], "force": 0.0},
                        {"t": 2.0, "pos": [0.15, 0.48, 0.70], "force": 5.4},
                    ],
                }
            ]
        }
    )

    session_id: str
    worker_type: WorkerType
    key_frames: List[str]
    action_phases: List[ActionPhase]
    dtw_metrics: DtwMetrics
    robot_trajectory_points: List[RobotTrajectoryPoint]


class IngestResponse(BaseModel):
    status: str
    session_id: str
    message: str