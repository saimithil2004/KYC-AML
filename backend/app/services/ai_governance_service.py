import logging
import inspect
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID, uuid4
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AIModel,
    ModelVersion,
    PromptTemplate,
    PromptVersion,
    AIExecution,
    AIFeedback,
    AIExplanation,
    ModelEvaluation,
    PromptTest,
    AIPolicy,
    AIApproval,
    AIUsageStatistics,
)

logger = logging.getLogger(__name__)

async def _safe_execute(db: Any, stmt: Any) -> Any:
    res = db.execute(stmt)
    if inspect.isawaitable(res):
        return await res
    return res

async def _safe_commit(db: Any) -> None:
    res = db.commit()
    if inspect.isawaitable(res):
        await res

async def _safe_refresh(db: Any, obj: Any) -> None:
    res = db.refresh(obj)
    if inspect.isawaitable(res):
        await res

# Default token pricing config (per 1,000 tokens)
PRICING_TABLE = {
    "gemini": {"input": 0.000075, "output": 0.000300},
    "openai": {"input": 0.002500, "output": 0.010000},
    "claude": {"input": 0.003000, "output": 0.015000},
    "default": {"input": 0.001000, "output": 0.003000},
}


class AIGovernanceService:
    """Enterprise AI Governance, prompt version control, model registry, cost metrics and policy gate checks."""

    # ─── Model Registry Operations ─────────────────────────────────────────────

    @staticmethod
    async def register_model(
        db: Any, name: str, provider: str, is_active: bool = True
    ) -> AIModel:
        """Register a new LLM model inside governance registry."""
        model = AIModel(id=uuid4(), name=name, provider=provider, is_active=is_active)
        db.add(model)
        await _safe_commit(db)
        await _safe_refresh(db, model)
        return model

    @staticmethod
    async def register_model_version(
        db: AsyncSession,
        model_id: UUID,
        version: str,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> ModelVersion:
        """Register specific snapshot versions under a model."""
        mv = ModelVersion(
            id=uuid4(),
            model_id=model_id,
            version=version,
            metadata_json=metadata_json or {},
            is_active=True,
        )
        db.add(mv)
        await db.commit()
        await db.refresh(mv)
        return mv

    @staticmethod
    async def get_active_model_version(
        db: AsyncSession, model_name: str
    ) -> Optional[Tuple[AIModel, ModelVersion]]:
        """Fetch the active model and version snapshot for routing."""
        stmt = (
            select(AIModel, ModelVersion)
            .join(ModelVersion, AIModel.id == ModelVersion.model_id)
            .where(AIModel.name == model_name)
            .where(AIModel.is_active == True)
            .where(ModelVersion.is_active == True)
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.first()

    # ─── Prompt Registry & Control ─────────────────────────────────────────────

    @staticmethod
    async def create_prompt_template(
        db: AsyncSession, name: str, description: Optional[str] = None
    ) -> PromptTemplate:
        """Create new template block grouping versions of prompts."""
        template = PromptTemplate(id=uuid4(), name=name, description=description)
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def create_prompt_version(
        db: AsyncSession,
        template_id: UUID,
        content: str,
        version: str,
        status: str = "draft",
    ) -> PromptVersion:
        """Append a new prompt draft revision content under template."""
        pv = PromptVersion(
            id=uuid4(),
            template_id=template_id,
            version=version,
            content=content,
            approved_status=status,
            is_active=False,
        )
        db.add(pv)
        await db.commit()
        await db.refresh(pv)
        return pv

    @staticmethod
    async def get_active_prompt_version(
        db: AsyncSession, template_name: str
    ) -> Optional[PromptVersion]:
        """Fetch the current published active prompt version content for runtimes."""
        stmt = (
            select(PromptVersion)
            .join(PromptTemplate, PromptTemplate.id == PromptVersion.template_id)
            .where(PromptTemplate.name == template_name)
            .where(PromptVersion.is_active == True)
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def switch_active_prompt_version(
        db: AsyncSession, template_id: UUID, version_id: UUID
    ) -> PromptVersion:
        """Set the active version under a prompt template. Only approved versions can be made active."""
        # 1. Verify prompt is approved
        stmt = select(PromptVersion).where(PromptVersion.id == version_id)
        res = await db.execute(stmt)
        pv = res.scalar_one_or_none()
        if not pv:
            raise ValueError("Prompt version not found.")
        if pv.approved_status not in ("approved", "published"):
            raise ValueError(
                f"Cannot switch active prompt version. Status is currently: '{pv.approved_status}' (must be approved first)."
            )

        # 2. Deactivate other versions under this template
        deact_stmt = (
            update(PromptVersion)
            .where(PromptVersion.template_id == template_id)
            .where(PromptVersion.id != version_id)
            .values(is_active=False)
        )
        await db.execute(deact_stmt)

        # 3. Activate target version
        pv.is_active = True
        pv.approved_status = "published"
        await db.commit()
        await db.refresh(pv)
        return pv

    @staticmethod
    async def rollback_prompt_version(
        db: AsyncSession, template_id: UUID, target_version_id: UUID, reviewer_id: UUID
    ) -> PromptVersion:
        """Roll back prompt template config to a legacy revision version."""
        # Logs rollback audit record
        pv = await AIGovernanceService.switch_active_prompt_version(
            db, template_id, target_version_id
        )
        approval = AIApproval(
            id=uuid4(),
            prompt_version_id=target_version_id,
            reviewer_id=reviewer_id,
            status="rollback",
            comments=f"Automated config rollback to version {pv.version}.",
        )
        db.add(approval)
        await db.commit()
        return pv

    @staticmethod
    def compare_prompt_contents(old_content: str, new_content: str) -> Dict[str, Any]:
        """Performs simple diff alignment comparisons between templates versions content."""
        import difflib

        diff = difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile="current",
            tofile="target",
            lineterm="",
        )
        return {"diff_raw": "\n".join(list(diff)), "equal": old_content == new_content}

    # ─── Approval Workflow States ──────────────────────────────────────────────

    @staticmethod
    async def approve_prompt_version(
        db: AsyncSession,
        version_id: UUID,
        reviewer_id: UUID,
        comments: Optional[str] = None,
    ) -> PromptVersion:
        """Transition status: pending -> approved."""
        stmt = select(PromptVersion).where(PromptVersion.id == version_id)
        res = await db.execute(stmt)
        pv = res.scalar_one_or_none()
        if not pv:
            raise ValueError("Prompt version not found.")

        pv.approved_status = "approved"
        approval = AIApproval(
            id=uuid4(),
            prompt_version_id=version_id,
            reviewer_id=reviewer_id,
            status="approved",
            comments=comments,
        )
        db.add(approval)
        await db.commit()
        await db.refresh(pv)
        return pv

    @staticmethod
    async def reject_prompt_version(
        db: AsyncSession,
        version_id: UUID,
        reviewer_id: UUID,
        comments: Optional[str] = None,
    ) -> PromptVersion:
        """Transition status: pending -> rejected."""
        stmt = select(PromptVersion).where(PromptVersion.id == version_id)
        res = await db.execute(stmt)
        pv = res.scalar_one_or_none()
        if not pv:
            raise ValueError("Prompt version not found.")

        pv.approved_status = "rejected"
        approval = AIApproval(
            id=uuid4(),
            prompt_version_id=version_id,
            reviewer_id=reviewer_id,
            status="rejected",
            comments=comments,
        )
        db.add(approval)
        await db.commit()
        await db.refresh(pv)
        return pv

    # ─── AI Test Suite Runs ───────────────────────────────────────────────────

    @staticmethod
    async def run_prompt_test(
        db: AsyncSession,
        version_id: UUID,
        test_input: str,
        expected_output: str,
        mock_llm_response: str,
    ) -> PromptTest:
        """Register validation test runs to verify output conforms to expected checks prior to publishing."""
        is_passed = expected_output.lower() in mock_llm_response.lower()
        test = PromptTest(
            id=uuid4(),
            prompt_version_id=version_id,
            test_input=test_input,
            expected_output=expected_output,
            actual_output=mock_llm_response,
            is_passed=is_passed,
        )
        db.add(test)
        await db.commit()
        await db.refresh(test)
        return test

    # ─── Execution Logging & Cost Calculation ──────────────────────────────────

    @staticmethod
    def calculate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
        """Compute estimated dollar cost based on input & output token consumption config pricing."""
        rates = PRICING_TABLE.get(provider.lower(), PRICING_TABLE["default"])
        in_cost = (input_tokens / 1000.0) * rates["input"]
        out_cost = (output_tokens / 1000.0) * rates["output"]
        return round(in_cost + out_cost, 6)

    @staticmethod
    async def log_execution(
        db: AsyncSession,
        model_name: str,
        template_name: str,
        prompt_content: str,
        response_content: str,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        customer_id: Optional[UUID] = None,
        case_id: Optional[UUID] = None,
        investigation_id: Optional[UUID] = None,
        sar_id: Optional[UUID] = None,
        risk_score_id: Optional[UUID] = None,
        monitoring_job_id: Optional[UUID] = None,
        report_id: Optional[UUID] = None,
        audit_log_id: Optional[UUID] = None,
    ) -> AIExecution:
        """Create persistent record of AI execution, calculating pricing costs."""
        # 1. Lookup active model version ID
        mv_id = None
        provider = "default"
        mv_res = await AIGovernanceService.get_active_model_version(db, model_name)
        if mv_res:
            model, m_ver = mv_res
            mv_id = m_ver.id
            provider = model.provider

        # 2. Lookup active prompt version ID
        pv_id = None
        pv_res = await AIGovernanceService.get_active_prompt_version(db, template_name)
        if pv_res:
            pv_id = pv_res.id

        # 3. Calculate cost
        cost = AIGovernanceService.calculate_cost(provider, input_tokens, output_tokens)
        total_tokens = input_tokens + output_tokens

        # 4. Save execution log
        exec_log = AIExecution(
            id=uuid4(),
            model_version_id=mv_id,
            prompt_version_id=pv_id,
            customer_id=customer_id,
            case_id=case_id,
            investigation_id=investigation_id,
            sar_id=sar_id,
            risk_score_id=risk_score_id,
            monitoring_job_id=monitoring_job_id,
            report_id=report_id,
            audit_log_id=audit_log_id,
            prompt_content=prompt_content,
            response_content=response_content,
            cost=cost,
            latency_ms=latency_ms,
            tokens_used=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(exec_log)
        await _safe_commit(db)
        await _safe_refresh(db, exec_log)
        return exec_log

    # ─── Human Feedback Loops ─────────────────────────────────────────────────

    @staticmethod
    async def log_human_feedback(
        db: AsyncSession,
        execution_id: UUID,
        user_id: Optional[UUID],
        rating: int,
        is_correct: bool = True,
        is_helpful: bool = True,
        comments: Optional[str] = None,
        decision_override: Optional[str] = None,
        escalation_reason: Optional[str] = None,
    ) -> AIFeedback:
        """Submit feedback override checks for executions."""
        fb = AIFeedback(
            id=uuid4(),
            execution_id=execution_id,
            user_id=user_id,
            rating=rating,
            is_correct=is_correct,
            is_helpful=is_helpful,
            comments=comments,
            decision_override=decision_override,
            escalation_reason=escalation_reason,
        )
        db.add(fb)
        await db.commit()
        await db.refresh(fb)
        return fb

    # ─── Policy Guardrails & Compliance Validation ─────────────────────────────

    @staticmethod
    async def get_active_policy(
        db: AsyncSession, policy_name: str
    ) -> Optional[AIPolicy]:
        """Fetch active governance policy configurations."""
        stmt = (
            select(AIPolicy)
            .where(AIPolicy.name == policy_name)
            .where(AIPolicy.is_active == True)
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def check_policy_guardrails(
        db: AsyncSession,
        policy_name: str,
        confidence: float,
        latency_ms: int,
        cost: float,
    ) -> Tuple[bool, List[str]]:
        """Validate AI metrics against active guardrails. Returns is_compliant flag and list of violations."""
        policy = await AIGovernanceService.get_active_policy(db, policy_name)
        if not policy:
            return True, []  # No policy active, pass

        rules = policy.rules_json or {}
        violations = []

        # Min confidence gate
        min_conf = float(rules.get("min_confidence_threshold") or 0.0)
        if confidence < min_conf:
            violations.append(
                f"Confidence score {confidence}% is below policy minimum {min_conf}%"
            )

        # Max latency gate
        max_lat = int(rules.get("max_latency_ms") or 0)
        if max_lat > 0 and latency_ms > max_lat:
            violations.append(
                f"Execution latency {latency_ms}ms exceeds policy maximum {max_lat}ms"
            )

        # Max cost gate
        max_c = float(rules.get("max_cost") or 0.0)
        if max_c > 0.0 and cost > max_c:
            violations.append(f"Execution cost ${cost} exceeds policy maximum ${max_c}")

        return len(violations) == 0, violations

    @staticmethod
    def detect_hallucinations(
        response_text: str, ground_truth_entities: List[str]
    ) -> Tuple[bool, float]:
        """Verify LLM outputs against customer data. Returns has_hallucinations flag and entities compliance score."""
        if not response_text or not ground_truth_entities:
            return False, 100.0

        matches = 0
        for entity in ground_truth_entities:
            if entity.lower() in response_text.lower():
                matches += 1

        accuracy_rate = (matches / len(ground_truth_entities)) * 100.0
        # If less than 60% of original reference entities are matched in summary, flag as potential hallucination
        has_hallucinations = accuracy_rate < 60.0
        return has_hallucinations, round(accuracy_rate, 2)

    # ─── Cost and Analytics Daily Aggregation ───────────────────────────────

    @staticmethod
    async def run_daily_usage_aggregation(
        db: AsyncSession, aggregate_date: date
    ) -> None:
        """Celery batch task to compile daily executions cost statistics."""
        # Query total token costs grouped by model versions
        stmt = (
            select(
                ModelVersion.version,
                AIModel.name,
                func.count(AIExecution.id).label("total_calls"),
                func.sum(AIExecution.tokens_used).label("total_tokens"),
                func.sum(AIExecution.input_tokens).label("input_tokens"),
                func.sum(AIExecution.output_tokens).label("output_tokens"),
                func.sum(AIExecution.cost).label("total_cost"),
                func.avg(AIExecution.latency_ms).label("avg_latency"),
            )
            .join(ModelVersion, AIExecution.model_version_id == ModelVersion.id)
            .join(AIModel, ModelVersion.model_id == AIModel.id)
            .where(func.date(AIExecution.created_at) == aggregate_date)
            .group_by(ModelVersion.version, AIModel.name)
        )
        res = await db.execute(stmt)
        rows = res.all()

        for row in rows:
            # Upsert into statistics table
            stat_stmt = select(AIUsageStatistics).where(
                and_(
                    AIUsageStatistics.date == aggregate_date,
                    AIUsageStatistics.model_name == f"{row.name}:{row.version}",
                )
            )
            stat_res = await db.execute(stat_stmt)
            stat = stat_res.scalar_one_or_none()

            if not stat:
                stat = AIUsageStatistics(
                    id=uuid4(),
                    date=aggregate_date,
                    model_name=f"{row.name}:{row.version}",
                )
                db.add(stat)

            stat.total_calls = int(row.total_calls or 0)
            stat.total_tokens = int(row.total_tokens or 0)
            stat.input_tokens = int(row.input_tokens or 0)
            stat.output_tokens = int(row.output_tokens or 0)
            stat.total_cost = float(row.total_cost or 0.0)
            stat.average_latency_ms = float(row.avg_latency or 0.0)

        await db.commit()
