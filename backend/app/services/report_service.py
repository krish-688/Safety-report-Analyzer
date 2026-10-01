"""PDF Incident Investigation Dossier Report Generation Service.

Builds executive petrochemical HSE reports using ReportLab.
"""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import CorrectiveAction, Incident, IncidentEquipment, IncidentRootCause, Investigation, User


def generate_incident_pdf_dossier(db: Session, incident: Incident) -> bytes:
    """Generate a comprehensive PDF investigation dossier for an incident."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
    )
    subtitle_style = ParagraphStyle(
        "SubHeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"),
    )
    section_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#C2410C"),  # HSE Rust/Amber
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
    )
    bold_body = ParagraphStyle(
        "ReportBodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    badge_style = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#FFFFFF"),
        alignment=1,  # Center
    )

    elements = []

    # 1. Header & Title Banner
    plant_name = incident.plant.name if incident.plant else f"Plant #{incident.plant_id}"
    occurred_str = incident.occurred_at.strftime("%Y-%m-%d %H:%M UTC")

    elements.append(
        Table(
            [
                [
                    Paragraph("🛡️ <b>SafeTrack AI</b> | Petrochemical HSE Intelligence", subtitle_style),
                    Paragraph(f"<b>Dossier Ref:</b> {incident.reference}", ParagraphStyle("RefRight", parent=subtitle_style, alignment=2)),
                ]
            ],
            colWidths=[300, 240],
        )
    )
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#E65100"), spaceAfter=10, spaceBefore=4))

    elements.append(Paragraph(f"Incident Investigation Dossier: {incident.title}", header_style))
    elements.append(Paragraph(f"Facility: <b>{plant_name}</b> · Occurred: <b>{occurred_str}</b> · Status: <b>{incident.status.value.upper()}</b>", subtitle_style))
    elements.append(Spacer(1, 12))

    # 2. Key Metadata Summary Table
    risk_color = "#DC2626" if incident.risk_level and incident.risk_level.value == "CRITICAL" else "#EA580C"
    meta_table_data = [
        [
            Paragraph("<b>Reference</b>", bold_body), Paragraph(incident.reference, body_style),
            Paragraph("<b>Severity</b>", bold_body), Paragraph(incident.severity.value, body_style),
        ],
        [
            Paragraph("<b>Operating Unit</b>", bold_body), Paragraph(plant_name, body_style),
            Paragraph("<b>Risk Level</b>", bold_body), Paragraph(f"<font color='{risk_color}'><b>{incident.risk_level.value if incident.risk_level else 'N/A'}</b></font>", body_style),
        ],
        [
            Paragraph("<b>Incident Type</b>", bold_body), Paragraph(incident.incident_type, body_style),
            Paragraph("<b>Injuries / Fatalities</b>", bold_body), Paragraph(str(incident.injuries), body_style),
        ],
        [
            Paragraph("<b>Workflow Status</b>", bold_body), Paragraph(incident.status.value, body_style),
            Paragraph("<b>Reported Date</b>", bold_body), Paragraph(incident.created_at.strftime("%Y-%m-%d %H:%M") if incident.created_at else "N/A", body_style),
        ],
    ]

    t_meta = Table(meta_table_data, colWidths=[110, 160, 110, 160])
    t_meta.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(t_meta)
    elements.append(Spacer(1, 14))

    # 3. Description & Initial Response
    elements.append(Paragraph("1. Incident Narrative & Immediate Actions", section_style))
    desc_p = Paragraph(f"<b>Event Description:</b><br/>{incident.description}", body_style)
    action_p = Paragraph(f"<b>Immediate Containment Taken:</b><br/>{incident.immediate_actions or 'None reported.'}", body_style)
    damage_p = Paragraph(f"<b>Damage & Loss Details:</b><br/>{incident.damage_details or 'None reported.'}", body_style)

    narrative_table = Table([[desc_p], [Spacer(1, 4)], [action_p], [Spacer(1, 4)], [damage_p]], colWidths=[540])
    narrative_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(narrative_table)
    elements.append(Spacer(1, 14))

    # 4. Equipment Involved
    elements.append(Paragraph("2. Equipment Assets Involved", section_style))
    eq_links = incident.equipment_links
    if not eq_links:
        elements.append(Paragraph("<i>No specific tagged equipment linked to this event.</i>", body_style))
    else:
        eq_headers = [Paragraph("<b>Tag</b>", bold_body), Paragraph("<b>Equipment Name</b>", bold_body), Paragraph("<b>Category</b>", bold_body)]
        eq_rows = [eq_headers]
        for l in eq_links:
            eq = l.equipment
            if eq:
                eq_rows.append([
                    Paragraph(eq.tag, body_style),
                    Paragraph(eq.name, body_style),
                    Paragraph(eq.equipment_type, body_style),
                ])
        t_eq = Table(eq_rows, colWidths=[100, 260, 180])
        t_eq.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(t_eq)
    elements.append(Spacer(1, 14))

    # 5. Root Causes (NLP & Manual)
    elements.append(Paragraph("3. Root Cause Analysis (NLP & Engineering Review)", section_style))
    root_causes = db.scalars(
        select(IncidentRootCause)
        .where(IncidentRootCause.incident_id == incident.id)
        .options(joinedload(IncidentRootCause.root_cause))
    ).all()

    if not root_causes:
        elements.append(Paragraph("<i>Root cause analysis has not yet been performed for this incident.</i>", body_style))
    else:
        rc_headers = [
            Paragraph("<b>Cause Category</b>", bold_body),
            Paragraph("<b>Source</b>", bold_body),
            Paragraph("<b>Confidence</b>", bold_body),
            Paragraph("<b>Review Status</b>", bold_body),
            Paragraph("<b>Evidence / Findings</b>", bold_body),
        ]
        rc_rows = [rc_headers]
        for rc in root_causes:
            c_name = rc.root_cause.name if rc.root_cause else "Unspecified"
            conf_str = f"{int(rc.confidence * 100)}%" if rc.confidence else "N/A"
            rc_rows.append([
                Paragraph(c_name, body_style),
                Paragraph(rc.source.value, body_style),
                Paragraph(conf_str, body_style),
                Paragraph(rc.review_status.value, body_style),
                Paragraph(rc.evidence or "-", body_style),
            ])
        t_rc = Table(rc_rows, colWidths=[140, 55, 65, 80, 200])
        t_rc.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(t_rc)
    elements.append(Spacer(1, 14))

    # 6. Formal Investigation Details
    elements.append(Paragraph("4. Formal Investigation & 5-Why Methodology", section_style))
    inv = db.scalar(
        select(Investigation)
        .where(Investigation.incident_id == incident.id)
        .options(joinedload(Investigation.investigator))
    )

    if not inv:
        elements.append(Paragraph("<i>No formal investigation record started.</i>", body_style))
    else:
        inv_name = inv.investigator.name if inv.investigator else "Unassigned"
        due_str = inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "N/A"
        closed_str = inv.closed_at.strftime("%Y-%m-%d %H:%M") if inv.closed_at else "Open / In Progress"

        inv_summary = [
            [
                Paragraph("<b>Lead Investigator</b>", bold_body), Paragraph(inv_name, body_style),
                Paragraph("<b>Target Due Date</b>", bold_body), Paragraph(due_str, body_style),
            ],
            [
                Paragraph("<b>Investigation Status</b>", bold_body), Paragraph(closed_str, body_style),
                Paragraph("<b>Created Date</b>", bold_body), Paragraph(inv.created_at.strftime("%Y-%m-%d") if inv.created_at else "N/A", body_style),
            ],
        ]
        t_inv = Table(inv_summary, colWidths=[120, 150, 120, 150])
        t_inv.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ])
        )
        elements.append(t_inv)
        elements.append(Spacer(1, 6))

        if inv.findings:
            elements.append(Paragraph(f"<b>Key Findings & Root Cause Logic:</b><br/>{inv.findings}", body_style))
            elements.append(Spacer(1, 4))
        if inv.evidence:
            elements.append(Paragraph(f"<b>Physical / Documentary Evidence:</b><br/>{inv.evidence}", body_style))
            elements.append(Spacer(1, 4))
    elements.append(Spacer(1, 10))

    # 7. Corrective & Preventive Actions (CAPA)
    elements.append(Paragraph("5. Corrective & Preventive Actions (CAPA)", section_style))
    actions = db.scalars(
        select(CorrectiveAction)
        .where(CorrectiveAction.incident_id == incident.id)
        .options(joinedload(CorrectiveAction.owner))
        .order_by(CorrectiveAction.due_date.asc())
    ).all()

    if not actions:
        elements.append(Paragraph("<i>No corrective actions logged for this incident.</i>", body_style))
    else:
        act_headers = [
            Paragraph("<b>Type</b>", bold_body),
            Paragraph("<b>Action Description</b>", bold_body),
            Paragraph("<b>Owner</b>", bold_body),
            Paragraph("<b>Target Due</b>", bold_body),
            Paragraph("<b>Status</b>", bold_body),
        ]
        act_rows = [act_headers]
        for act in actions:
            owner_name = act.owner.name if act.owner else "Unassigned"
            act_rows.append([
                Paragraph(act.action_type.value, body_style),
                Paragraph(act.description, body_style),
                Paragraph(owner_name, body_style),
                Paragraph(act.due_date.strftime("%Y-%m-%d"), body_style),
                Paragraph(f"<b>{act.status.value}</b>", body_style),
            ])
        t_act = Table(act_rows, colWidths=[70, 220, 95, 75, 80])
        t_act.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(t_act)
    elements.append(Spacer(1, 14))

    # 8. Verification & Sign-off Footer
    elements.append(
        KeepTogether([
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94A3B8"), spaceBefore=10, spaceAfter=8),
            Table(
                [
                    [
                        Paragraph(f"<b>Certified Closed:</b> {'Yes' if incident.status.value == 'Closed' else 'Pending Final Verification'}", body_style),
                        Paragraph(f"<b>Report Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ParagraphStyle("GenDate", parent=body_style, alignment=2)),
                    ],
                    [
                        Paragraph("<i>SafeTrack AI HSE Incident Compliance Platform — Petrochemical Operations</i>", subtitle_style),
                        Paragraph("<i>Confidential — Internal HSE Record</i>", ParagraphStyle("Conf", parent=subtitle_style, alignment=2)),
                    ],
                ],
                colWidths=[270, 270],
            ),
        ])
    )

    doc.build(elements)
    return buffer.getvalue()
