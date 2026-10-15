import io
import base64
import urllib.parse
import qrcode
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models.models import Order

def generate_upi_qr_data_url(upi_id: str, amount: int, bill_no: str, app_name: str = "Sangh Mart") -> str:
    """
    Generates a prefilled UPI QR code compliant with the specification:
    upi://pay?pa=UPIID&pn=Sangh~Mart&am=AMOUNT&tn=BILLREF&cu=INR
    Returns base64 PNG data URL.
    """
    safe_pn = urllib.parse.quote(app_name.replace(" ", "~"))
    safe_tn = urllib.parse.quote(bill_no)
    upi_string = f"upi://pay?pa={upi_id}&pn={safe_pn}&am={amount}&tn={safe_tn}&cu=INR"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(upi_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_data}", upi_string

def generate_order_pdf(order: Order, bill_header: str = "Sangh Mart") -> bytes:
    """
    Generates an on-demand PDF invoice bytes for the order (not stored on disk).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#d9531e'),
        alignment=1  # Center
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b'),
        alignment=1
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1e293b')
    )
    bold_style = ParagraphStyle(
        'BoldBody',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    elements = []
    elements.append(Paragraph(f"<b>{bill_header}</b>", title_style))
    elements.append(Paragraph("Vijayadashami Uniform Sales Receipt", subtitle_style))
    elements.append(Spacer(1, 15))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0'), spaceAfter=15))
    
    # Bill details table
    nagar_name = order.nagar.name if order.nagar else "N/A"
    seller_name = order.seller.name if order.seller else "N/A"
    date_str = order.created_at.strftime("%d-%b-%Y %I:%M %p")
    
    info_data = [
        [Paragraph(f"<b>Bill No:</b> {order.bill_no}", body_style), Paragraph(f"<b>Date:</b> {date_str}", body_style)],
        [Paragraph(f"<b>Buyer:</b> {order.buyer.name}", body_style), Paragraph(f"<b>Phone:</b> {order.buyer.phone}", body_style)],
        [Paragraph(f"<b>Nagar:</b> {nagar_name}", body_style), Paragraph(f"<b>Seller:</b> {seller_name}", body_style)],
        [Paragraph(f"<b>Order Status:</b> {order.order_status}", body_style), Paragraph(f"<b>Payment Status:</b> {order.payment_status}", bold_style)],
    ]
    info_table = Table(info_data, colWidths=[260, 260])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))
    
    # Items table
    items_header = [
        Paragraph("<b>Item</b>", bold_style),
        Paragraph("<b>Size</b>", bold_style),
        Paragraph("<b>Qty</b>", bold_style),
        Paragraph("<b>Rate (Rs.)</b>", bold_style),
        Paragraph("<b>Amount (Rs.)</b>", bold_style)
    ]
    items_rows = [items_header]
    for item in order.items:
        items_rows.append([
            Paragraph(item.item_name, body_style),
            Paragraph(item.size, body_style),
            Paragraph(str(item.quantity), body_style),
            Paragraph(f"{item.unit_price}", body_style),
            Paragraph(f"{item.line_total}", body_style)
        ])
        
    items_table = Table(items_rows, colWidths=[180, 80, 60, 100, 100])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#cbd5e1')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 15))
    
    # Totals summary table
    totals_data = [
        [Paragraph("<b>Total Amount:</b>", bold_style), Paragraph(f"<b>Rs. {order.total}</b>", bold_style)],
        [Paragraph("<b>Paid Amount:</b>", body_style), Paragraph(f"Rs. {order.paid_amount}", body_style)],
        [Paragraph("<b>Balance Due:</b>", bold_style), Paragraph(f"<font color='{'#dc2626' if order.balance > 0 else '#16a34a'}'><b>Rs. {order.balance}</b></font>", bold_style)]
    ]
    totals_table = Table(totals_data, colWidths=[420, 100])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(totals_table)
    
    # Payments breakdown
    if order.payments:
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("<b>Payment Transactions:</b>", bold_style))
        elements.append(Spacer(1, 4))
        pay_rows = [[
            Paragraph("<b>Date & Time</b>", bold_style),
            Paragraph("<b>Method</b>", bold_style),
            Paragraph("<b>Type</b>", bold_style),
            Paragraph("<b>UTR / Ref</b>", bold_style),
            Paragraph("<b>Amount (Rs.)</b>", bold_style)
        ]]
        for p in order.payments:
            p_time = p.confirmed_at.strftime("%d-%b %H:%M")
            pay_rows.append([
                Paragraph(p_time, body_style),
                Paragraph(p.method.upper(), body_style),
                Paragraph(p.kind.title(), body_style),
                Paragraph(p.utr or "-", body_style),
                Paragraph(f"{p.amount}", body_style)
            ])
        pay_table = Table(pay_rows, colWidths=[120, 80, 80, 140, 100])
        pay_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(pay_table)
        
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("Thank you for your purchase!", subtitle_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
