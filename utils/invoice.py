"""PDF invoice generation with ReportLab (Invoice PDF Service)."""
from io import BytesIO

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from utils.helpers import money

INK = colors.HexColor("#1C2541")
MARIGOLD = colors.HexColor("#F5B700")


def rs(value):
    # Helvetica has no rupee glyph, so invoices use "Rs."
    return money(value, symbol="Rs. ")


def build_invoice(order) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Invoice {order.number}")
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Title"], alignment=0, textColor=INK, fontSize=22)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, leading=12)
    store = current_app.config["STORE_NAME"]

    story = [Paragraph(f"{store} - Tax Invoice", h), Spacer(1, 4 * mm)]

    pay = order.payment
    meta = [
        [Paragraph(f"<b>Invoice no.</b> INV-{order.number}", small),
         Paragraph(f"<b>Bill to</b><br/>{order.ship_name}<br/>{order.ship_address}<br/>"
                   f"{order.ship_city} - {order.ship_pincode}<br/>Phone: {order.ship_phone}", small)],
        [Paragraph(f"<b>Order date</b> {order.order_date:%d %b %Y, %I:%M %p}", small), ""],
        [Paragraph(f"<b>Payment</b> {order.payment_method}"
                   f"{' (' + pay.status + ')' if pay else ''}", small), ""],
        [Paragraph(f"<b>Status</b> {order.status}", small), ""],
    ]
    mt = Table(meta, colWidths=[80 * mm, 94 * mm])
    mt.setStyle(TableStyle([("SPAN", (1, 0), (1, 3)), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [mt, Spacer(1, 6 * mm)]

    rows = [["#", "Item", "Qty", "Unit price", "Amount"]]
    for n, it in enumerate(order.items, 1):
        rows.append([n, Paragraph(it.product.name, small), it.quantity,
                     rs(it.unit_price), rs(it.line_total)])
    rows += [["", "", "", "Subtotal", rs(order.subtotal)],
             ["", "", "", "Shipping", rs(order.shipping_fee)],
             ["", "", "", "Total", rs(order.total_amount)]]
    t = Table(rows, colWidths=[10 * mm, 88 * mm, 14 * mm, 30 * mm, 32 * mm])
    n = len(rows)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, n - 4), 0.4, colors.HexColor("#DCE0E8")),
        ("LINEABOVE", (3, n - 1), (-1, n - 1), 1.2, MARIGOLD),
        ("FONTNAME", (3, n - 1), (-1, n - 1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [t, Spacer(1, 10 * mm),
              Paragraph("This is a computer-generated invoice and does not need a signature.", small)]
    doc.build(story)
    return buf.getvalue()
