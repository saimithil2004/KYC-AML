"""
Investigation Workspace Service — Phase 12
===========================================
Orchestrates cases investigations, evidence files upload/hash/delete, case notes logs with audit tracking,
investigator team assignments, timeline event logs tracking, and SAR draft/approval state workflows.
"""

import os
import hashlib
import logging
from uuid import UUID, uuid4
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schema_helpers import ensure_phase12_schema
from app.models.models import (
    Customer,
    Case,
    User,
    Investigation,
    Evidence,
    CaseNote,
    SAR,
    TimelineEvent,
    Assignment,
    AuditLog,
    RiskScore,
    Alert,
    MonitoringHistory,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class InvestigationService:
    """Core workspace manager for case investigations and SAR operations."""

    @staticmethod
    async def get_or_create_investigation(
        db: AsyncSession, case_id: UUID, current_user_id: UUID
    ) -> Investigation:
        """Fetch or initialize a workspace investigation for a case."""
        await ensure_phase12_schema(db)

        # 1. Check if investigation already exists
        res = await db.execute(
            select(Investigation).where(Investigation.case_id == case_id)
        )
        inv = res.scalars().first()

        if not inv:
            # Load Case & Customer ID
            case_res = await db.execute(select(Case).where(Case.id == case_id))
            case_obj = case_res.scalars().first()
            if not case_obj:
                raise ValueError("Case not found.")

            # Calculate initial AI summary from AgentLog/Risk if exists, or use default template
            inv = Investigation(
                id=uuid4(),
                case_id=case_id,
                customer_id=case_obj.customer_id,
                status="open",
                risk_level="medium",
                assigned_to=case_obj.assigned_to,
                ai_summary={
                    "case_summary": "Initial compliance review workspace established. Case logs pending analysis.",
                    "suspicious_behaviour_analysis": "Pending investigation audit review.",
                    "recommended_actions": [
                        "Conduct initial alert matching checks",
                        "Verify customer ID profile",
                    ],
                    "questions_for_investigator": [
                        "Is this a duplicate customer profile?",
                        "Are transactional flags valid?",
                    ],
                    "missing_evidence_suggestions": ["Proof of residential address"],
                    "risk_explanation": "Initial review baseline.",
                },
            )
            db.add(inv)
            await db.flush()

            # Create initial timeline event
            await InvestigationService.log_timeline_event(
                db=db,
                investigation_id=inv.id,
                event_type="case_created",
                title="Investigation Workspace Opened",
                description="Compliance officer initialized investigation workspace.",
                actor_id=current_user_id,
            )

            # Log audit
            await AuditService.log(
                db=db,
                user_id=current_user_id,
                action="CREATE_INVESTIGATION",
                entity_name="investigation",
                entity_id=inv.id,
                new_values={
                    "case_id": str(case_id),
                    "customer_id": str(case_obj.customer_id),
                },
            )
            await db.commit()
            await db.refresh(inv)

        return inv

    @staticmethod
    async def get_investigation_details(
        db: AsyncSession, investigation_id: UUID
    ) -> Dict[str, Any]:
        """Gathers full multi-panel workspace view payload (Part 1)."""
        await ensure_phase12_schema(db)

        # 1. Load Investigation
        inv_res = await db.execute(
            select(Investigation).where(Investigation.id == investigation_id)
        )
        inv = inv_res.scalars().first()
        if not inv:
            raise ValueError("Investigation not found.")

        # 2. Customer & KYC
        cust_res = await db.execute(
            select(Customer).where(Customer.id == inv.customer_id)
        )
        cust = cust_res.scalars().first()
        kyc = cust.kyc_profile if cust else None

        # 3. Documents
        docs = cust.documents if cust else []

        # 4. Alerts
        alerts_res = await db.execute(
            select(Alert).where(Alert.customer_id == inv.customer_id)
        )
        alerts = alerts_res.scalars().all()

        # 5. Transactions
        # Fetching transactions via account transfers if any
        from app.models.models import Account, Transaction

        tx_res = await db.execute(
            select(Transaction)
            .join(Account, Account.id == Transaction.sender_account_id)
            .where(Account.customer_id == inv.customer_id)
        )
        txs = tx_res.scalars().all()

        # 6. Risk Scores
        risk_res = await db.execute(
            select(RiskScore)
            .where(RiskScore.customer_id == inv.customer_id)
            .order_by(desc(RiskScore.created_at))
        )
        risks = risk_res.scalars().all()

        # 7. Monitoring History
        mon_res = await db.execute(
            select(MonitoringHistory)
            .where(MonitoringHistory.customer_id == inv.customer_id)
            .order_by(desc(MonitoringHistory.screening_date))
        )
        history = mon_res.scalars().all()

        # 8. Notes
        notes_res = await db.execute(
            select(CaseNote)
            .where(CaseNote.investigation_id == investigation_id)
            .order_by(CaseNote.created_at.desc())
        )
        notes = notes_res.scalars().all()

        # 9. Evidence
        ev_res = await db.execute(
            select(Evidence)
            .where(Evidence.investigation_id == investigation_id)
            .order_by(Evidence.timestamp.desc())
        )
        evidences = ev_res.scalars().all()

        # 10. SARs
        sar_res = await db.execute(
            select(SAR)
            .where(SAR.investigation_id == investigation_id)
            .order_by(SAR.created_at.desc())
        )
        sars = sar_res.scalars().all()

        # 11. Timeline
        timeline_res = await db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.investigation_id == investigation_id)
            .order_by(TimelineEvent.timestamp.asc())
        )
        timeline = timeline_res.scalars().all()

        # 12. Assignments history
        assign_res = await db.execute(
            select(Assignment)
            .where(Assignment.investigation_id == investigation_id)
            .order_by(Assignment.assigned_at.desc())
        )
        assignments = assign_res.scalars().all()

        return {
            "investigation": inv,
            "customer": cust,
            "kyc_profile": kyc,
            "documents": docs,
            "alerts": alerts,
            "transactions": txs,
            "risk_scores": risks,
            "monitoring_history": history,
            "notes": notes,
            "evidence": evidences,
            "sars": sars,
            "timeline": timeline,
            "assignments": assignments,
        }

    @staticmethod
    async def add_note(
        db: AsyncSession, investigation_id: UUID, author_id: UUID, note_text: str
    ) -> CaseNote:
        """Add case note. Rich text formatting & mentions handled on frontend."""
        await ensure_phase12_schema(db)

        note = CaseNote(
            id=uuid4(),
            investigation_id=investigation_id,
            author_id=author_id,
            note_text=note_text,
        )
        db.add(note)
        await db.flush()

        # Timeline
        await InvestigationService.log_timeline_event(
            db=db,
            investigation_id=investigation_id,
            event_type="comment_added",
            title="Note Added by Investigator",
            description=f"Note: {note_text[:100]}...",
            actor_id=author_id,
        )

        # Audit
        await AuditService.log(
            db=db,
            user_id=author_id,
            action="ADD_CASE_NOTE",
            entity_name="case_note",
            entity_id=note.id,
            new_values={"investigation_id": str(investigation_id)},
        )
        await db.commit()
        await db.refresh(note)
        return note

    @staticmethod
    async def edit_note(
        db: AsyncSession, note_id: UUID, author_id: UUID, new_text: str
    ) -> CaseNote:
        """Edit an existing note and record audit log entry (Part 3)."""
        await ensure_phase12_schema(db)

        res = await db.execute(select(CaseNote).where(CaseNote.id == note_id))
        note = res.scalars().first()
        if not note:
            raise ValueError("Note not found.")
        if note.author_id != author_id:
            raise PermissionError("Only the author can edit this note.")

        note.note_text = new_text
        note.updated_at = datetime.utcnow()
        await db.flush()

        await AuditService.log(
            db=db,
            user_id=author_id,
            action="EDIT_CASE_NOTE",
            entity_name="case_note",
            entity_id=note_id,
            new_values={"investigation_id": str(note.investigation_id)},
        )
        await db.commit()
        await db.refresh(note)
        return note

    @staticmethod
    async def delete_note(db: AsyncSession, note_id: UUID, author_id: UUID) -> bool:
        """Delete an existing case note (Part 3)."""
        await ensure_phase12_schema(db)

        res = await db.execute(select(CaseNote).where(CaseNote.id == note_id))
        note = res.scalars().first()
        if not note:
            return False
        if note.author_id != author_id:
            raise PermissionError("Only the author can delete this note.")

        await db.delete(note)
        await AuditService.log(
            db=db,
            user_id=author_id,
            action="DELETE_CASE_NOTE",
            entity_name="case_note",
            entity_id=note_id,
            old_values={"investigation_id": str(note.investigation_id)},
        )
        await db.commit()
        return True

    @staticmethod
    async def add_evidence(
        db: AsyncSession,
        investigation_id: UUID,
        file_name: str,
        evidence_type: str,
        file_content: bytes,
        uploaded_by: UUID,
        description: Optional[str] = None,
    ) -> Evidence:
        """Part 2 - Store evidence and compute SHA256 checksum hash."""
        await ensure_phase12_schema(db)

        # Compute hash
        sha256_hash = hashlib.sha256(file_content).hexdigest()

        # Store in local evidence directory mock
        evidence_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "evidence_files"
        )
        os.makedirs(evidence_dir, exist_ok=True)
        file_id = uuid4()
        storage_path = os.path.join(evidence_dir, f"{file_id}_{file_name}")

        with open(storage_path, "wb") as f:
            f.write(file_content)

        evidence = Evidence(
            id=file_id,
            investigation_id=investigation_id,
            file_name=file_name,
            evidence_type=evidence_type.lower(),
            file_path=storage_path,
            description=description,
            uploaded_by=uploaded_by,
            file_hash=sha256_hash,
        )
        db.add(evidence)
        await db.flush()

        # Timeline
        await InvestigationService.log_timeline_event(
            db=db,
            investigation_id=investigation_id,
            event_type="evidence_uploaded",
            title="Evidence Document Uploaded",
            description=f"File: {file_name} ({evidence_type}), Hash: {sha256_hash[:8]}...",
            actor_id=uploaded_by,
        )

        # Audit
        await AuditService.log(
            db=db,
            user_id=uploaded_by,
            action="UPLOAD_EVIDENCE",
            entity_name="evidence",
            entity_id=evidence.id,
            new_values={
                "investigation_id": str(investigation_id),
                "file_name": file_name,
            },
        )
        await db.commit()
        await db.refresh(evidence)
        return evidence

    @staticmethod
    async def delete_evidence(
        db: AsyncSession, evidence_id: UUID, actor_id: UUID
    ) -> bool:
        """Remove evidence record and purge file from local workspace."""
        await ensure_phase12_schema(db)

        res = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
        ev = res.scalars().first()
        if not ev:
            return False

        # Remove local file if exists
        if os.path.exists(ev.file_path):
            try:
                os.remove(ev.file_path)
            except Exception as e:
                logger.error(f"Error purging local evidence file: {e}")

        # Timeline
        await InvestigationService.log_timeline_event(
            db=db,
            investigation_id=ev.investigation_id,
            event_type="evidence_uploaded",  # keep timeline category
            title="Evidence Removed",
            description=f"Evidence file {ev.file_name} was deleted from case records.",
            actor_id=actor_id,
        )

        # Audit
        await AuditService.log(
            db=db,
            user_id=actor_id,
            action="DELETE_EVIDENCE",
            entity_name="evidence",
            entity_id=evidence_id,
            old_values={
                "investigation_id": str(ev.investigation_id),
                "file_name": ev.file_name,
            },
        )

        await db.delete(ev)
        await db.commit()
        return True

    @staticmethod
    async def assign_case(
        db: AsyncSession,
        investigation_id: UUID,
        assignee_id: UUID,
        role: str,  # investigator, supervisor
        current_user_id: UUID,
    ) -> Assignment:
        """Part 4 - Reassign investigator or supervisor to investigation workspace."""
        await ensure_phase12_schema(db)

        res = await db.execute(
            select(Investigation).where(Investigation.id == investigation_id)
        )
        inv = res.scalars().first()
        if not inv:
            raise ValueError("Investigation not found.")

        # Update core owner columns
        if role == "supervisor":
            inv.assigned_supervisor_id = assignee_id
        else:
            inv.assigned_to = assignee_id
        inv.updated_at = datetime.utcnow()

        # Log assignment entry
        assignment = Assignment(
            id=uuid4(),
            investigation_id=investigation_id,
            assigned_by=current_user_id,
            assigned_to=assignee_id,
            role=role,
        )
        db.add(assignment)
        await db.flush()

        # Fetch names for narrative details
        user_res = await db.execute(select(User).where(User.id == assignee_id))
        user_obj = user_res.scalars().first()
        assignee_name = user_obj.email if user_obj else str(assignee_id)

        # Timeline
        await InvestigationService.log_timeline_event(
            db=db,
            investigation_id=investigation_id,
            event_type=(
                "case_assigned" if role == "investigator" else "supervisor_assigned"
            ),
            title=f"Reassigned {role.title()}",
            description=f"Assigned owner updated to {assignee_name}.",
            actor_id=current_user_id,
        )

        # Audit
        await AuditService.log(
            db=db,
            user_id=current_user_id,
            action=f"ASSIGN_{role.upper()}",
            entity_name="investigation",
            entity_id=investigation_id,
            new_values={"assigned_to": str(assignee_id)},
        )
        await db.commit()
        await db.refresh(assignment)
        return assignment

    @staticmethod
    async def get_investigator_workloads(db: AsyncSession) -> List[Dict[str, Any]]:
        """Calculates workload counts for user dashboard balancing (Part 4)."""
        await ensure_phase12_schema(db)

        # Fetch active open investigation case counts by assigned investigator
        res = await db.execute(
            select(
                User.id, User.email, func.count(Investigation.id).label("active_cases")
            )
            .join(Investigation, Investigation.assigned_to == User.id, isouter=True)
            .where(or_(Investigation.status != "closed", Investigation.id == None))
            .group_by(User.id, User.email)
        )
        rows = res.all()
        return [
            {"user_id": str(r[0]), "email": r[1], "active_cases": r[2]} for r in rows
        ]

    @staticmethod
    async def generate_sar(
        db: AsyncSession,
        investigation_id: UUID,
        narrative: str,
        reason: str,
        risk_indicators: List[str],
        recommendation: str,
        created_by: UUID,
    ) -> SAR:
        """Part 6 - Initialize Suspicious Activity Report draft for investigation."""
        await ensure_phase12_schema(db)

        # Format custom SAR number: SAR-YYYY-UUID_PREFIX
        year = datetime.utcnow().year
        sar_num = f"SAR-{year}-{uuid4().hex[:8].upper()}"

        sar = SAR(
            id=uuid4(),
            investigation_id=investigation_id,
            sar_number=sar_num,
            narrative=narrative,
            reason=reason,
            risk_indicators=risk_indicators,
            recommendation=recommendation,
            status="draft",
            created_by=created_by,
        )
        db.add(sar)
        await db.flush()

        # Update parent case sar_filed indicator
        res = await db.execute(
            select(Investigation).where(Investigation.id == investigation_id)
        )
        inv = res.scalars().first()
        if inv:
            case_res = await db.execute(select(Case).where(Case.id == inv.case_id))
            case_obj = case_res.scalars().first()
            if case_obj:
                case_obj.sar_filed = True

        # Timeline
        await InvestigationService.log_timeline_event(
            db=db,
            investigation_id=investigation_id,
            event_type="sar_generated",
            title="SAR Report Drafted",
            description=f"Generated draft report: {sar_num}.",
            actor_id=created_by,
        )

        # Audit
        await AuditService.log(
            db=db,
            user_id=created_by,
            action="DRAFT_SAR",
            entity_name="sar",
            entity_id=sar.id,
            new_values={
                "investigation_id": str(investigation_id),
                "sar_number": sar_num,
            },
        )
        await db.commit()
        await db.refresh(sar)
        return sar

    @staticmethod
    async def update_sar_status(
        db: AsyncSession,
        sar_id: UUID,
        status: str,  # submitted, approved, rejected, archived
        actor_id: UUID,
    ) -> SAR:
        """Transitions SAR report status workflow (Part 6)."""
        await ensure_phase12_schema(db)

        res = await db.execute(select(SAR).where(SAR.id == sar_id))
        sar = res.scalars().first()
        if not sar:
            raise ValueError("SAR not found.")

        old_status = sar.status
        sar.status = status.lower()
        sar.updated_at = datetime.utcnow()
        await db.flush()

        # Timeline
        await InvestigationService.log_timeline_event(
            db=db,
            investigation_id=sar.investigation_id,
            event_type="sar_generated",
            title=f"SAR {status.title()}",
            description=f"Transitioned report status from {old_status} to {status.lower()}.",
            actor_id=actor_id,
        )

        # Audit
        await AuditService.log(
            db=db,
            user_id=actor_id,
            action=f"SAR_{status.upper()}",
            entity_name="sar",
            entity_id=sar_id,
            old_values={"status": old_status},
            new_values={"status": status},
        )
        await db.commit()
        await db.refresh(sar)
        return sar

    @staticmethod
    async def transition_case_status(
        db: AsyncSession,
        investigation_id: UUID,
        action: str,  # close, reopen, escalate, return, edd_required
        actor_id: UUID,
    ) -> Investigation:
        """Transitions case workflow state machines and raises compliance notification entries (Part 8)."""
        await ensure_phase12_schema(db)

        res = await db.execute(
            select(Investigation).where(Investigation.id == investigation_id)
        )
        inv = res.scalars().first()
        if not inv:
            raise ValueError("Investigation not found.")

        case_res = await db.execute(select(Case).where(Case.id == inv.case_id))
        case_obj = case_res.scalars().first()

        old_status = inv.status
        event_title = ""
        event_desc = ""

        if action == "close":
            inv.status = "closed"
            if case_obj:
                case_obj.status = "resolved"
            event_title = "Case Closed"
            event_desc = "Investigation closed and resolved successfully."
        elif action == "reopen":
            inv.status = "open"
            if case_obj:
                case_obj.status = "under_investigation"
            event_title = "Case Re-opened"
            event_desc = "Reopened closed investigation case file."
        elif action == "escalate":
            inv.status = "escalated"
            if case_obj:
                case_obj.status = "escalated"
            event_title = "Case Escalated"
            event_desc = "Case escalated to compliance supervisor."
        elif action == "return":
            inv.status = "open"
            if case_obj:
                case_obj.status = "under_investigation"
            event_title = "Case Returned"
            event_desc = "Returned escalated case back to investigator queue."
        elif action == "edd_required":
            inv.status = "edd_required"
            if case_obj:
                case_obj.status = "edd_required"
            event_title = "EDD Required Flag Set"
            event_desc = "Flagged case file for Enhanced Due Diligence review."

        inv.updated_at = datetime.utcnow()
        if case_obj:
            case_obj.updated_at = datetime.utcnow()

        await db.flush()

        # Log timeline event
        await InvestigationService.log_timeline_event(
            db=db,
            investigation_id=investigation_id,
            event_type=(
                "decision_made" if action in ("close", "return") else "case_escalated"
            ),
            title=event_title,
            description=event_desc,
            actor_id=actor_id,
        )

        # Log audit entry
        await AuditService.log(
            db=db,
            user_id=actor_id,
            action=f"INVESTIGATION_{action.upper()}",
            entity_name="investigation",
            entity_id=investigation_id,
            old_values={"status": old_status},
            new_values={"status": inv.status},
        )
        await db.commit()
        await db.refresh(inv)
        return inv

    @staticmethod
    async def log_timeline_event(
        db: AsyncSession,
        investigation_id: UUID,
        event_type: str,
        title: str,
        description: str,
        actor_id: Optional[UUID] = None,
    ) -> TimelineEvent:
        """Create chronological timeline event log (Part 5)."""
        await ensure_phase12_schema(db)

        ev = TimelineEvent(
            id=uuid4(),
            investigation_id=investigation_id,
            event_type=event_type,
            title=title,
            description=description,
            actor_id=actor_id,
        )
        db.add(ev)
        await db.flush()
        return ev

    @staticmethod
    async def get_dashboard_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Gathers investigation statistics for dashboard aggregation panel (Part 13)."""
        await ensure_phase12_schema(db)

        # 1. Open investigations
        open_invs = (
            await db.execute(
                select(func.count(Investigation.id)).where(
                    Investigation.status != "closed"
                )
            )
        ).scalar_one() or 0

        # 2. Pending SARs
        pending_sars = (
            await db.execute(select(func.count(SAR.id)).where(SAR.status == "draft"))
        ).scalar_one() or 0

        # 3. SARs Submitted
        submitted_sars = (
            await db.execute(
                select(func.count(SAR.id)).where(SAR.status == "submitted")
            )
        ).scalar_one() or 0

        # 4. Total evidence files uploaded
        total_evidence = (
            await db.execute(select(func.count(Evidence.id)))
        ).scalar_one() or 0

        # 5. Average investigation resolution time in hours
        # Calculation: average difference between Case.created_at and Investigation.updated_at for closed investigations
        avg_res_time = 0.0
        closed_inv_res = await db.execute(
            select(Investigation).where(Investigation.status == "closed")
        )
        closed_invs = closed_inv_res.scalars().all()
        if closed_invs:
            tot_hours = 0.0
            for ci in closed_invs:
                diff = ci.updated_at - ci.created_at
                tot_hours += diff.total_seconds() / 3600.0
            avg_res_time = tot_hours / len(closed_invs)

        # 6. Investigator workload breakdown
        workloads = await InvestigationService.get_investigator_workloads(db)

        # 7. Recently assigned cases
        recent_cases_res = await db.execute(
            select(Investigation).order_by(Investigation.created_at.desc()).limit(5)
        )
        recent_cases = recent_cases_res.scalars().all()
        recent_list = []
        for rc in recent_cases:
            cust_res = await db.execute(
                select(Customer).where(Customer.id == rc.customer_id)
            )
            cust = cust_res.scalars().first()
            recent_list.append(
                {
                    "investigation_id": str(rc.id),
                    "customer_name": (
                        f"{cust.first_name or ''} {cust.last_name or ''}".strip()
                        if cust
                        else "Unknown"
                    ),
                    "status": rc.status,
                    "risk_level": rc.risk_level,
                    "created_at": rc.created_at.isoformat(),
                }
            )

        return {
            "open_investigations": open_invs,
            "pending_sar": pending_sars,
            "sar_submitted": submitted_sars,
            "evidence_uploaded": total_evidence,
            "average_investigation_time_hours": round(avg_res_time, 1),
            "investigator_workload": workloads,
            "recently_assigned_cases": recent_list,
        }
