"""
Investigation-ready PDF report generator.
Summarizes a case: query address, trace hops, VASP attribution, risk flags.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io


def generate_case_report(case: dict) -> bytes:
    """
    `case` is a dict with: id, query_address, matched_vasp, confidence,
    match_method, risk_flags, trace (full TraceResult), created_at.
    Returns raw PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], fontSize=18)
    story = []

    story.append(Paragraph("Cryptocurrency Wallet Attribution Report", title_style))
    story.append(Paragraph(f"Case #{case['id']}  |  Generated: {case['created_at']}", styles["Normal"]))
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("Summary", styles["Heading2"]))
    summary_rows = [
        ["Query Address", case["query_address"]],
        ["Chain", "Bitcoin"],
        ["Matched VASP", case["matched_vasp"] or "Unresolved"],
        ["Confidence", f"{case['confidence']:.0%}"],
        ["Match Method", case["match_method"]],
        ["Risk Flags", ", ".join(case["risk_flags"]) or "None detected"],
    ]
    summary_table = Table(summary_rows, colWidths=[4.5 * cm, 10 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.8 * cm))

    story.append(Paragraph("Transaction Hop Trail", styles["Heading2"]))
    hop_rows = [["Hop", "Address", "Tx Hash", "Timestamp", "Amount (BTC)"]]
    for h in case["trace"]["hops"]:
        hop_rows.append([
            str(h["hop_index"]),
            h["address"][:16] + "...",
            h["tx_hash"][:16] + "...",
            h["timestamp"],
            f"{h['amount_btc']:.6f}",
        ])
    hop_table = Table(hop_rows, colWidths=[1.5 * cm, 4 * cm, 4 * cm, 4.5 * cm, 3 * cm])
    hop_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
    ]))
    story.append(hop_table)
    story.append(Spacer(1, 0.8 * cm))

    story.append(Paragraph(
        "Note: exchange-tag coverage is based on a curated seed list of publicly "
        "documented addresses. Production deployment would extend coverage via a "
        "licensed VASP address database.",
        styles["Italic"]
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
