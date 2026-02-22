from __future__ import annotations

import csv
import io
from typing import Iterable


class InterviewReportGenerator:
    """Generate interview report artifacts from current interview models."""

    @staticmethod
    def _row_for_session(session) -> list:
        case = session.case
        applicant = case.applicant
        total_flags = case.interrogation_flags.count()
        resolved_flags = case.interrogation_flags.filter(status="resolved").count()
        duration_minutes = round((session.duration_seconds or 0) / 60.0, 1)
        estimated_cost = round(duration_minutes * 0.50, 2)

        return [
            session.session_id,
            applicant.get_full_name(),
            session.created_at.strftime("%Y-%m-%d %H:%M"),
            duration_minutes,
            session.total_questions_asked,
            round(session.overall_score, 1) if session.overall_score is not None else "",
            round(session.confidence_score, 1) if session.confidence_score is not None else "",
            total_flags,
            resolved_flags,
            session.status,
            case.final_decision,
            estimated_cost,
        ]

    @classmethod
    def generate_csv_report(cls, sessions: Iterable, filename: str = "interview_report.csv") -> str:
        del filename  # backward-compatible parameter, output is returned as string
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Session ID",
                "Applicant",
                "Date",
                "Duration (min)",
                "Questions Asked",
                "Overall Score",
                "Confidence Score",
                "Flags Total",
                "Flags Resolved",
                "Status",
                "Decision",
                "Cost ($)",
            ]
        )
        for session in sessions:
            writer.writerow(cls._row_for_session(session))
        return output.getvalue()

    @classmethod
    def generate_pdf_report(cls, session) -> bytes:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("reportlab is required to generate PDF interview reports.") from exc

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=20,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=18,
        )
        elements.append(Paragraph(f"Interview Report: {session.session_id}", title_style))
        elements.append(Spacer(1, 0.2 * inch))

        case = session.case
        applicant = case.applicant
        summary_rows = [
            ["Applicant", applicant.get_full_name()],
            ["Case ID", case.case_id],
            ["Date", session.created_at.strftime("%Y-%m-%d %H:%M")],
            ["Duration", f"{round((session.duration_seconds or 0) / 60.0, 1)} minutes"],
            ["Questions Asked", str(session.total_questions_asked)],
            ["Overall Score", f"{round(session.overall_score, 1)}%" if session.overall_score is not None else "N/A"],
            ["Status", session.status.upper()],
            ["Decision", case.final_decision.upper()],
        ]

        summary_table = Table(summary_rows, colWidths=[2.0 * inch, 4.0 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 0.35 * inch))

        elements.append(Paragraph("Interview Summary", styles["Heading2"]))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(session.interview_summary or "No summary generated yet.", styles["Normal"]))

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
