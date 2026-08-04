"""
Signal Protocol - Deterministic Signal Schema for Agent Communication (Law 14).
Every agent emits exactly ONE typed signal on completion. The Kernel routes based on signal type.
"""

from typing import Literal
from datetime import datetime


# All possible signal types in the system
SignalType = Literal[
    # Success Signals
    "CONTEXT_CURATED",
    "TASK_DECOMPOSED",
    "ARCHITECTURE_READY",
    "CODE_GENERATED",
    "TESTS_PASSED",
    "PROJECT_ASSEMBLED",
    
    # Failure Signals
    "VALIDATION_FAILED",
    "TESTS_FAILED",
    "ARCHITECTURE_INCOMPLETE",
    "INTEGRATION_FAILED",
    
    # Alert Signals
    "SECURITY_BREACH",
    "CONTEXT_ROT_DETECTED",
    "NEEDS_CLARIFICATION",
    "HUMAN_CHECKPOINT",
    
    # Terminal Signals
    "MAX_RETRIES_EXCEEDED",
    "PIPELINE_COMPLETE"
]


SUCCESS_SIGNALS = {
    "CONTEXT_CURATED", "TASK_DECOMPOSED", "ARCHITECTURE_READY",
    "CODE_GENERATED", "TESTS_PASSED", "PROJECT_ASSEMBLED"
}

FAILURE_SIGNALS = {
    "VALIDATION_FAILED", "TESTS_FAILED",
    "ARCHITECTURE_INCOMPLETE", "INTEGRATION_FAILED"
}

ALERT_SIGNALS = {
    "SECURITY_BREACH", "CONTEXT_ROT_DETECTED",
    "NEEDS_CLARIFICATION", "HUMAN_CHECKPOINT"
}

TERMINAL_SIGNALS = {
    "MAX_RETRIES_EXCEEDED", "PIPELINE_COMPLETE"
}


class AgentSignal:
    """
    Typed, immutable signal emitted by every agent on completion.
    The Kernel reads these signals and routes deterministically.
    """
    
    def __init__(
        self,
        signal_type: str,
        source_agent: str,
        data: dict = None,
        quality_score: float = 1.0,
        retry_count: int = 0
    ):
        all_valid = SUCCESS_SIGNALS | FAILURE_SIGNALS | ALERT_SIGNALS | TERMINAL_SIGNALS
        if signal_type not in all_valid:
            raise ValueError(f"Invalid signal type: {signal_type}. Must be one of: {all_valid}")
            
        self.signal_type = signal_type
        self.source_agent = source_agent
        self.timestamp = datetime.now().isoformat()
        self.data = data or {}
        self.quality_score = quality_score
        self.retry_count = retry_count
        
    @property
    def is_success(self) -> bool:
        return self.signal_type in SUCCESS_SIGNALS
    
    @property
    def is_failure(self) -> bool:
        return self.signal_type in FAILURE_SIGNALS
    
    @property
    def is_alert(self) -> bool:
        return self.signal_type in ALERT_SIGNALS
    
    @property
    def is_terminal(self) -> bool:
        return self.signal_type in TERMINAL_SIGNALS
        
    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp,
            "data": self.data,
            "quality_score": self.quality_score,
            "retry_count": self.retry_count
        }
    
    def __repr__(self) -> str:
        return f"AgentSignal({self.signal_type}, from={self.source_agent}, q={self.quality_score})"
