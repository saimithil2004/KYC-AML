import logging
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AIExplanation, AIExecution

logger = logging.getLogger(__name__)

class ExplainabilityService:
    """Responsible for generating explainability reports for AI compliance decisions."""

    @staticmethod
    def compile_reasoning_tree(
        agent_name: str,
        risk_score: float,
        rules_evaluated: List[Dict[str, Any]],
        triggers: List[str]
    ) -> Dict[str, Any]:
        """Generate a hierarchical decision tree mapping logic nodes."""
        return {
            "node": agent_name,
            "risk_score": risk_score,
            "status": "triggered" if triggers else "clear",
            "evaluations": [
                {
                    "rule": rule.get("code", "RULE"),
                    "name": rule.get("name", "Rule Check"),
                    "outcome": "triggered" if rule.get("triggered") else "clear",
                    "details": rule.get("details", "")
                }
                for rule in rules_evaluated
            ],
            "children": [
                {
                    "node": trigger,
                    "status": "flagged"
                } for trigger in triggers
            ]
        }

    @staticmethod
    async def generate_explanation_report(
        db: AsyncSession,
        execution_id: UUID,
        agent_name: str,
        overall_score: float,
        findings: List[str],
        rules_triggered: List[str],
        matched_entities: List[str],
        missing_evidence: List[str] = None,
        alternative_outcomes: List[str] = None
    ) -> AIExplanation:
        """Create and persist an explainability report linked to an AI execution record."""
        
        # 1. Executive Summary formulation
        summary_text = (
            f"Agent '{agent_name}' evaluated the subject and assessed a risk score of {overall_score}/100. "
            f"The evaluation triggered {len(rules_triggered)} compliance rules and identified {len(matched_entities)} matched entity markers. "
            f"Primary findings: {', '.join(findings[:3]) if findings else 'No major issues flagged.'}"
        )

        # 2. Risk factor level and recommendations
        if overall_score >= 80.0:
            rec_actions = "Route to standard automated processing. No further action needed."
            confidence = 95.0
        elif overall_score >= 50.0:
            rec_actions = "Requires manual compliance desk analysis. Perform secondary PII and PEP checking."
            confidence = 75.0
        else:
            rec_actions = "Flag as high-risk event. Immediate Supervisor escalation. Review transaction history for potential SAR filing."
            confidence = 55.0

        # Construct alternatives details
        tree_evals = [{"code": r, "name": f"Rule {r}", "triggered": True} for r in rules_triggered]
        reasoning_tree = ExplainabilityService.compile_reasoning_tree(
            agent_name=agent_name,
            risk_score=overall_score,
            rules_evaluated=tree_evals,
            triggers=findings
        )

        if alternative_outcomes:
            reasoning_tree["alternative_outcomes"] = alternative_outcomes

        # 3. Create Explanation Model object
        explanation = AIExplanation(
            id=uuid4(),
            execution_id=execution_id,
            decision_summary=summary_text,
            reasoning_tree=reasoning_tree,
            confidence=confidence,
            supporting_evidence="Matched triggers:\n" + "\n".join([f"- {f}" for f in findings]),
            matched_rules="; ".join(rules_triggered) if rules_triggered else "None",
            matched_entities="; ".join(matched_entities) if matched_entities else "None",
            missing_evidence="; ".join(missing_evidence) if missing_evidence else "None",
            recommended_actions=rec_actions
        )

        db.add(explanation)
        await db.commit()
        await db.refresh(explanation)
        return explanation
