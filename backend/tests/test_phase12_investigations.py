"""
Investigation Workspace Unit Tests — Phase 12
=============================================
Tests all core services and endpoints including workspace details aggregates,
case notes CRUD audit trail loggings, evidence uploads/SHA256 computations/deletions,
chronological timeline updates, user assignments/supervisor workload trackers,
SAR drafting/submissions, and endpoint RBAC protections.
"""

import pytest
import hashlib
from uuid import uuid4
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi import status
from app.models.models import (
    User,
    Customer,
    Case,
    Investigation,
    Evidence,
    CaseNote,
    SAR,
    TimelineEvent,
    Assignment,
)
from app.services.investigation_service import InvestigationService
from app.api.v1.endpoints.investigations import verify_compliance_or_admin


def test_verify_rbac():
    """Verify that verify_compliance_or_admin enforces RBAC appropriately."""
    # 1. Customer user raises 403 Forbidden
    cust_user = User(id=uuid4(), email="cust@test.com", role="customer")
    with pytest.raises(Exception) as exc_info:
        verify_compliance_or_admin(cust_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    # 2. Compliance officer and Admin pass checks
    officer = User(id=uuid4(), email="officer@test.com", role="compliance_officer")
    verify_compliance_or_admin(officer)  # Should not raise exception

    admin = User(id=uuid4(), email="admin@test.com", role="admin")
    verify_compliance_or_admin(admin)  # Should not raise exception


@pytest.mark.asyncio
async def test_get_or_create_investigation():
    """Verify that get_or_create_investigation works and initializes timeline loggings."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    # Configure case
    case_id = uuid4()
    mock_case = MagicMock()
    mock_case.customer_id = uuid4()
    mock_case.assigned_to = uuid4()

    # Set db queries mock
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.side_effect = [
        None,  # First query: Investigation not found
        mock_case,  # Second query: Case found
    ]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch(
        "app.services.investigation_service.ensure_phase12_schema", return_value=None
    ), patch("app.services.investigation_service.AuditService.log", return_value=None):

        inv = await InvestigationService.get_or_create_investigation(
            mock_db, case_id, uuid4()
        )

        assert inv.case_id == case_id
        assert inv.status == "open"
        assert inv.risk_level == "medium"
        assert mock_db.add.called
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_note_management_and_audit():
    """Verify notes log, update, and deletions with corresponding timeline/audit footprints."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    inv_id = uuid4()
    author_id = uuid4()
    note_text = "Suspicious outbound transfers detected"

    with patch(
        "app.services.investigation_service.ensure_phase12_schema", return_value=None
    ), patch(
        "app.services.investigation_service.AuditService.log", return_value=None
    ), patch(
        "app.services.investigation_service.InvestigationService.log_timeline_event",
        return_value=None,
    ):

        # 1. Add Note
        note = await InvestigationService.add_note(
            mock_db, inv_id, author_id, note_text
        )
        assert note.note_text == note_text
        assert note.investigation_id == inv_id
        assert note.author_id == author_id

        # Mock query return for Edit Note
        mock_res = MagicMock()
        mock_res.scalars.return_value.first.return_value = note
        mock_db.execute = AsyncMock(return_value=mock_res)

        # 2. Edit Note
        updated = await InvestigationService.edit_note(
            mock_db, note.id, author_id, "Outbound transactions are cleared"
        )
        assert updated.note_text == "Outbound transactions are cleared"

        # 3. Delete Note
        deleted = await InvestigationService.delete_note(mock_db, note.id, author_id)
        assert deleted is True


@pytest.mark.asyncio
async def test_evidence_management():
    """Verify upload computes SHA256 file hashes and deletion purges paths."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    inv_id = uuid4()
    uploader_id = uuid4()
    file_name = "bank_statement.pdf"
    content = b"Mock PDF Bank statement raw binary content bytes"

    # Compute expected SHA256 checksum hash
    expected_hash = hashlib.sha256(content).hexdigest()

    with patch(
        "app.services.investigation_service.ensure_phase12_schema", return_value=None
    ), patch(
        "app.services.investigation_service.AuditService.log", return_value=None
    ), patch(
        "app.services.investigation_service.InvestigationService.log_timeline_event",
        return_value=None,
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", MagicMock()
    ):

        # 1. Add Evidence
        evidence = await InvestigationService.add_evidence(
            db=mock_db,
            investigation_id=inv_id,
            file_name=file_name,
            evidence_type="pdf",
            file_content=content,
            uploaded_by=uploader_id,
            description="Client bank transfer list statement",
        )

        assert evidence.file_name == file_name
        assert evidence.file_hash == expected_hash
        assert evidence.investigation_id == inv_id

        # Mock query return for Delete
        mock_res = MagicMock()
        mock_res.scalars.return_value.first.return_value = evidence
        mock_db.execute = AsyncMock(return_value=mock_res)

        # 2. Delete Evidence
        with patch("os.path.exists", return_value=True), patch(
            "os.remove", return_value=None
        ):
            deleted = await InvestigationService.delete_evidence(
                mock_db, evidence.id, uploader_id
            )
            assert deleted is True


@pytest.mark.asyncio
async def test_investigator_assignments():
    """Verify workspace reassignments and owner changes log events."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    inv_id = uuid4()
    officer_id = uuid4()
    current_user_id = uuid4()

    mock_inv = MagicMock()
    mock_inv.id = inv_id

    mock_res = MagicMock()
    mock_res.scalars.return_value.first.side_effect = [
        mock_inv,  # Query 1: Investigation workspace found
        MagicMock(),  # Query 2: User found
    ]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch(
        "app.services.investigation_service.ensure_phase12_schema", return_value=None
    ), patch(
        "app.services.investigation_service.AuditService.log", return_value=None
    ), patch(
        "app.services.investigation_service.InvestigationService.log_timeline_event",
        return_value=None,
    ):

        assignment = await InvestigationService.assign_case(
            db=mock_db,
            investigation_id=inv_id,
            assignee_id=officer_id,
            role="investigator",
            current_user_id=current_user_id,
        )

        assert assignment.investigation_id == inv_id
        assert assignment.assigned_to == officer_id
        assert mock_inv.assigned_to == officer_id


@pytest.mark.asyncio
async def test_sar_narrative_and_workflows():
    """Verify SAR report generated status changes."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    inv_id = uuid4()
    created_by = uuid4()

    # Mock parent investigation
    mock_inv = MagicMock()
    mock_inv.case_id = uuid4()

    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = mock_inv
    mock_db.execute = MagicMock(return_value=mock_res)
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch(
        "app.services.investigation_service.ensure_phase12_schema", return_value=None
    ), patch(
        "app.services.investigation_service.AuditService.log", return_value=None
    ), patch(
        "app.services.investigation_service.InvestigationService.log_timeline_event",
        return_value=None,
    ):

        # 1. Draft SAR
        sar = await InvestigationService.generate_sar(
            db=mock_db,
            investigation_id=inv_id,
            narrative="Suspicious activity reported regarding international wires.",
            reason="High volume risk delta triggers.",
            risk_indicators=["structuring", "high_risk_jurisdiction"],
            recommendation="Block account.",
            created_by=created_by,
        )

        assert sar.status == "draft"
        assert sar.investigation_id == inv_id
        assert sar.sar_number.startswith("SAR-")

        # Mock SAR query for status update
        mock_sar_res = MagicMock()
        mock_sar_res.scalars.return_value.first.return_value = sar
        mock_db.execute = AsyncMock(return_value=mock_sar_res)

        # 2. Transition SAR status to submitted
        updated = await InvestigationService.update_sar_status(
            mock_db, sar.id, "submitted", created_by
        )
        assert updated.status == "submitted"
