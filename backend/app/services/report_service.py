"""
Report Service — Phase 13
==========================
Generates the 15 types of compliance business intelligence reports, queries database
aggregates, and exports them to PDF, Excel (.xlsx), CSV, and JSON formats.
"""

import os
import csv
import json
import logging
from uuid import UUID, uuid4
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

# ReportLab and OpenPyXL imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from openpyxl import Workbook

from app.core.schema_helpers import ensure_phase13_schema
from app.models.models import (
    Customer, KYCProfile, Case, Alert, Transaction, RiskScore,
    MonitoringSchedule, AuditLog, AgentLog, Regulation, PolicyRule,
    Investigation, SAR, User, Report, ReportTemplate, ScheduledReport, ReportExecution
)

logger = logging.getLogger(__name__)


class ReportService:
    """Service layer to compile BI reports and generate formats."""

    @staticmethod
    async def compile_report_data(
        db: AsyncSession,
        report_type: str,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Compile tabular data for the requested report type using filters."""
        await ensure_phase13_schema(db)

        # Parse date filters if any
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")
        if start_date and isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", ""))
        if end_date and isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", ""))

        data: List[Dict[str, Any]] = []

        # ─── 1. Customer Summary ───
        if report_type == "customer_summary":
            q = select(Customer).join(KYCProfile, isouter=True)
            if filters.get("risk_level"):
                q = q.where(KYCProfile.risk_category == filters["risk_level"])
            res = await db.execute(q)
            customers = res.scalars().all()
            for c in customers:
                kyc = c.kyc_profile
                data.append({
                    "id": str(c.id),
                    "name": f"{c.first_name} {c.last_name}" if c.first_name else "Unknown",
                    "type": c.customer_type,
                    "status": c.status,
                    "risk_category": kyc.risk_category if kyc else "low",
                    "nationality": kyc.nationality if kyc else "N/A"
                })

        # ─── 2. High Risk Customers ───
        elif report_type == "high_risk_customers":
            q = select(Customer).join(KYCProfile).where(
                or_(KYCProfile.risk_category == "high", KYCProfile.risk_category == "critical")
            )
            res = await db.execute(q)
            customers = res.scalars().all()
            for c in customers:
                kyc = c.kyc_profile
                data.append({
                    "id": str(c.id),
                    "name": f"{c.first_name} {c.last_name}",
                    "risk_category": kyc.risk_category,
                    "score": float(kyc.risk_score) if kyc and kyc.risk_score else 0.0,
                    "nationality": kyc.nationality if kyc else "N/A"
                })

        # ─── 3. Risk Distribution ───
        elif report_type == "risk_distribution":
            q = select(
                KYCProfile.risk_category,
                func.count(KYCProfile.id).label("count")
            ).group_by(KYCProfile.risk_category)
            res = await db.execute(q)
            rows = res.all()
            for r in rows:
                data.append({
                    "risk_category": r[0] or "unknown",
                    "count": r[1]
                })

        # ─── 4. Transaction Summary ───
        elif report_type == "transaction_summary":
            q = select(Transaction)
            if start_date:
                q = q.where(Transaction.created_at >= start_date)
            if end_date:
                q = q.where(Transaction.created_at <= end_date)
            res = await db.execute(q)
            txs = res.scalars().all()
            for t in txs:
                data.append({
                    "id": str(t.id),
                    "receiver_name": t.receiver_name,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "status": t.status,
                    "type": t.transaction_type,
                    "created_at": t.created_at.isoformat()
                })

        # ─── 5. Suspicious Transactions ───
        elif report_type == "suspicious_transactions":
            q = select(Transaction).where(
                or_(Transaction.status == "failed", Transaction.status == "flagged")
            )
            res = await db.execute(q)
            txs = res.scalars().all()
            for t in txs:
                data.append({
                    "id": str(t.id),
                    "receiver": t.receiver_name,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "status": t.status,
                    "country": t.receiver_country
                })

        # ─── 6. Case Statistics ───
        elif report_type == "case_statistics":
            q = select(
                Case.status,
                Case.priority,
                func.count(Case.id).label("count")
            ).group_by(Case.status, Case.priority)
            res = await db.execute(q)
            rows = res.all()
            for r in rows:
                data.append({
                    "status": r[0],
                    "priority": r[1],
                    "count": r[2]
                })

        # ─── 7. Alert Statistics ───
        elif report_type == "alert_statistics":
            q = select(
                Alert.alert_type,
                Alert.status,
                func.count(Alert.id).label("count")
            ).group_by(Alert.alert_type, Alert.status)
            res = await db.execute(q)
            rows = res.all()
            for r in rows:
                data.append({
                    "alert_type": r[0],
                    "status": r[1],
                    "count": r[2]
                })

        # ─── 8. SAR Statistics ───
        elif report_type == "sar_statistics":
            q = select(
                SAR.status,
                func.count(SAR.id).label("count")
            ).group_by(SAR.status)
            res = await db.execute(q)
            rows = res.all()
            for r in rows:
                data.append({
                    "status": r[0],
                    "count": r[1]
                })

        # ─── 9. Investigation Statistics ───
        elif report_type == "investigation_statistics":
            q = select(
                Investigation.status,
                Investigation.risk_level,
                func.count(Investigation.id).label("count")
            ).group_by(Investigation.status, Investigation.risk_level)
            res = await db.execute(q)
            rows = res.all()
            for r in rows:
                data.append({
                    "status": r[0],
                    "risk_level": r[1],
                    "count": r[2]
                })

        # ─── 10. Monitoring Statistics ───
        elif report_type == "monitoring_statistics":
            q = select(MonitoringSchedule)
            res = await db.execute(q)
            schedules = res.scalars().all()
            for s in schedules:
                data.append({
                    "id": str(s.id),
                    "customer_id": str(s.customer_id),
                    "frequency": s.frequency,
                    "status": s.status,
                    "last_review": s.last_review_date.isoformat() if s.last_review_date else None,
                    "next_review": s.next_review_date.isoformat() if s.next_review_date else None
                })

        # ─── 11. Regulation Compliance ───
        elif report_type == "regulation_compliance":
            q = select(Regulation)
            res = await db.execute(q)
            regs = res.scalars().all()
            for r in regs:
                data.append({
                    "id": str(r.id),
                    "name": r.name,
                    "country": r.country or "Global",
                    "status": r.status or "active",
                    "effective_date": r.effective_date.isoformat() if r.effective_date else None
                })

        # ─── 12. Policy Rule Activity ───
        elif report_type == "policy_rule_activity":
            q = select(PolicyRule)
            res = await db.execute(q)
            rules = res.scalars().all()
            for r in rules:
                data.append({
                    "id": str(r.id),
                    "name": r.name,
                    "severity": r.severity or "medium",
                    "status": "active" if r.is_active else "inactive",
                    "description": r.description[:100] if r.description else "N/A"
                })

        # ─── 13. Agent Performance ───
        elif report_type == "agent_performance":
            # Select from AgentLog to check execution counts and step names
            q = select(
                AgentLog.agent_name,
                AgentLog.step_name,
                func.count(AgentLog.id).label("count")
            ).group_by(AgentLog.agent_name, AgentLog.step_name)
            res = await db.execute(q)
            rows = res.all()
            for r in rows:
                data.append({
                    "agent_name": r[0],
                    "step_name": r[1],
                    "count": r[2]
                })

        # ─── 14. Dashboard KPIs ───
        elif report_type == "dashboard_kpis":
            c_count = (await db.execute(select(func.count(Customer.id)))).scalar_one() or 0
            a_count = (await db.execute(select(func.count(Alert.id)))).scalar_one() or 0
            case_count = (await db.execute(select(func.count(Case.id)))).scalar_one() or 0
            tx_sum = (await db.execute(select(func.sum(Transaction.amount)))).scalar_one() or 0.0
            data.append({
                "total_customers": c_count,
                "total_alerts": a_count,
                "total_cases": case_count,
                "total_transaction_value": float(tx_sum)
            })

        # ─── 15. Audit Activity ───
        elif report_type == "audit_activity":
            q = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(100)
            res = await db.execute(q)
            logs = res.scalars().all()
            for l in logs:
                data.append({
                    "id": str(l.id),
                    "user_id": str(l.user_id) if l.user_id else "system",
                    "action": l.action,
                    "entity": l.entity_name,
                    "created_at": l.created_at.isoformat()
                })

        return data

    @staticmethod
    def generate_csv_bytes(data: List[Dict[str, Any]]) -> bytes:
        """Helper to output CSV binary text."""
        if not data:
            return b"No data available"
        
        import io
        output = io.StringIO()
        headers = list(data[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in data:
            # Format datetime objects or nested dicts as strings
            formatted_row = {
                k: (v.isoformat() if isinstance(v, (datetime, date)) else json.dumps(v) if isinstance(v, (dict, list)) else v)
                for k, v in row.items()
            }
            writer.writerow(formatted_row)
        
        return output.getvalue().encode("utf-8")

    @staticmethod
    def generate_json_bytes(data: List[Dict[str, Any]]) -> bytes:
        """Helper to output JSON string bytes."""
        return json.dumps(data, indent=2, default=str).encode("utf-8")

    @staticmethod
    def generate_excel_bytes(data: List[Dict[str, Any]], title: str) -> bytes:
        """Helper to generate Excel sheet using openpyxl."""
        import io
        wb = Workbook()
        ws = wb.active
        ws.title = "Report Data"

        # Apply basic formatting & headers
        if data:
            headers = list(data[0].keys())
            ws.append([h.replace("_", " ").title() for h in headers])
            for row in data:
                ws.append([
                    (str(v) if isinstance(v, (dict, list)) else v)
                    for v in row.values()
                ])
        else:
            ws.append(["No records matches filters"])

        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    @staticmethod
    def generate_pdf_bytes(data: List[Dict[str, Any]], title: str, filters: Dict[str, Any]) -> bytes:
        """Helper to generate styled compliance PDF utilizing ReportLab."""
        import io
        buffer = io.BytesIO()
        
        # Simple letter portrait setup
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom premium style definitions
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0f766e"), # Sleek Teal Color
            spaceAfter=15
        )
        
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#3f3f46")
        )

        bold_style = ParagraphStyle(
            "DocBold",
            parent=body_style,
            fontName="Helvetica-Bold"
        )

        story = []

        # 1. Header Section
        story.append(Paragraph("KYC / AML COMPLIANCE AUDIT RECORD", bold_style))
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 10))

        # 2. Executive Summary Info Metadata Box
        metadata_text = f"<b>Generated on:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}<br/>"
        metadata_text += f"<b>Filters:</b> {json.dumps(filters, default=str)}"
        story.append(Paragraph(metadata_text, body_style))
        story.append(Spacer(1, 20))

        # 3. Main Data Table
        if data:
            headers = list(data[0].keys())
            table_headers = [Paragraph(f"<b>{h.replace('_', ' ').title()}</b>", body_style) for h in headers]
            
            table_data = [table_headers]
            for idx, item in enumerate(data[:45]): # cap to fit on standard 1-2 pages gracefully
                row_cells = []
                for val in item.values():
                    cell_text = str(val) if val is not None else "N/A"
                    if len(cell_text) > 40:
                        cell_text = cell_text[:37] + "..."
                    row_cells.append(Paragraph(cell_text, body_style))
                table_data.append(row_cells)

            # Styled Table
            col_widths = [ (doc.width / len(headers)) ] * len(headers)
            t = Table(table_data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f4f4f5")),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e4e4e7")),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ]))
            story.append(t)
        else:
            story.append(Paragraph("<i>No data records found matching report criteria.</i>", body_style))

        # 4. Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph("CONFIDENTIAL · AML/KYC Platform BI Generated Document Output Footer", bold_style))

        doc.build(story)
        return buffer.getvalue()
