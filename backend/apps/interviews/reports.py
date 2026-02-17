# backend/apps/interviews/reports.py
from datetime import datetime
import csv
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from .models import DynamicInterviewSession

class InterviewReportGenerator:
    """Generate PDF and CSV reports for interviews"""
    
    @staticmethod
    def generate_csv_report(sessions, filename="interview_report.csv"):
        """Generate CSV report of interview sessions"""
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Session ID',
            'Applicant',
            'Date',
            'Duration (min)',
            'Questions Asked',
            'Overall Score',
            'Deception Score',
            'Flags Total',
            'Flags Resolved',
            'Status',
            'Recommendation',
            'Cost ($)'
        ])
        
        # Data rows
        for session in sessions:
            writer.writerow([
                session.session_id,
                session.application.applicant.full_name,
                session.created_at.strftime('%Y-%m-%d %H:%M'),
                round(session.duration_seconds / 60, 1) if session.duration_seconds else 0,
                session.current_question_number,
                round(session.overall_score, 1) if session.overall_score else 0,
                round(session.confidence_score, 1) if session.confidence_score else 0,
                session.interrogation_flags.count(),
                session.interrogation_flags.filter(status='resolved').count(),
                session.status,
                session.recommendations,
                round((session.duration_seconds / 60) * 0.50, 2) if session.duration_seconds else 0
            ])
        
        return output.getvalue()
    
    @staticmethod
    def generate_pdf_report(session):
        """Generate detailed PDF report for single interview"""
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1F2937'),
            spaceAfter=30
        )
        
        elements.append(Paragraph(f"Interview Report: {session.session_id}", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Summary Section
        summary_data = [
            ['Applicant', session.application.applicant.full_name],
            ['Date', session.created_at.strftime('%Y-%m-%d %H:%M')],
            ['Duration', f"{round(session.duration_seconds / 60, 1)} minutes"],
            ['Questions Asked', str(session.current_question_number)],
            ['Overall Score', f"{round(session.overall_score, 1)}%" if session.overall_score else 'N/A'],
            ['Status', session.status.upper()],
            ['Recommendation', session.recommendations or 'Pending']
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F3F4F6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1F2937')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB'))
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Interrogation Flags
        elements.append(Paragraph("Interrogation Flags", styles['Heading2']))
        elements.append(Spacer(1, 0.2*inch))
        
        flags = session.interrogation_flags.all()
        if flags:
            flag_data = [['Type', 'Severity', 'Context', 'Status']]
            for flag in flags:
                flag_data.append([
                    flag.flag_type.replace('_', ' ').title(),
                    flag.severity.upper(),
                    flag.context[:50] + '...' if len(flag.context) > 50 else flag.context,
                    flag.status.upper()
                ])
            
            flag_table = Table(flag_data, colWidths=[1.5*inch, 1*inch, 3*inch, 1*inch])
            flag_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')])
            ]))
            
            elements.append(flag_table)
        else:
            elements.append(Paragraph("No flags identified.", styles['Normal']))
        
        elements.append(Spacer(1, 0.5*inch))
        
        # AI Summary
        elements.append(Paragraph("AI Analysis Summary", styles['Heading2']))
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph(session.interview_summary or "Analysis pending.", styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        
        return pdf
