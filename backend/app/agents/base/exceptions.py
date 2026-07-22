from datetime import datetime
from typing import Any, Dict, Optional


class AgentBaseException(Exception):
    """Base exception for all agent framework errors with structured audit metadata."""

    def __init__(
        self,
        message: str,
        error_code: str = "GENERIC_AGENT_ERROR",
        details: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
        timestamp: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.severity = severity
        self.timestamp = timestamp or datetime.utcnow().isoformat()

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message} (Severity: {self.severity}, Details: {self.details})"


class AgentExecutionError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
    ):
        super().__init__(message, "AGENT_EXECUTION_ERROR", details, severity)


class AgentValidationError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "WARNING",
    ):
        super().__init__(message, "AGENT_VALIDATION_ERROR", details, severity)


class RegistryError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
    ):
        super().__init__(message, "REGISTRY_ERROR", details, severity)


class RetryableError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "WARNING",
    ):
        super().__init__(message, "RETRYABLE_ERROR", details, severity)


class NonRetryableError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "CRITICAL",
    ):
        super().__init__(message, "NON_RETRYABLE_ERROR", details, severity)


class ConfigurationError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "CRITICAL",
    ):
        super().__init__(message, "CONFIGURATION_ERROR", details, severity)


class ExternalAPIError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
    ):
        super().__init__(message, "EXTERNAL_API_ERROR", details, severity)


class DatabaseError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
    ):
        super().__init__(message, "DATABASE_ERROR", details, severity)


class RiskCalculationError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
    ):
        super().__init__(message, "RISK_CALCULATION_ERROR", details, severity)


class DocumentVerificationError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
    ):
        super().__init__(message, "DOCUMENT_VERIFICATION_ERROR", details, severity)


class PolicyEngineError(AgentBaseException):
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
    ):
        super().__init__(message, "POLICY_ENGINE_ERROR", details, severity)
