import os
import glob
from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        if self._pageNumber == 1:
            # Draw decorative border/accents on cover page
            self.setFillColor(colors.HexColor("#4F46E5"))
            self.rect(0, 0, 15, 792, fill=True, stroke=False)
            self.restoreState()
            return

        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header
        self.drawString(54, 750, "YOLOv8 Live Object Tracking & Analytics System")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 742, 558, 742)
        
        # Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 40, page_text)
        self.drawString(54, 40, "Confidential - Cortex Tracking Engine Report")
        self.line(54, 52, 558, 52)
        self.restoreState()

def get_image_flowable(img_path, target_width=450):
    if not img_path or not os.path.exists(img_path):
        return Paragraph(f"<font color='red'><b>Image Error:</b> File not found ({img_path})</font>", getSampleStyleSheet()['BodyText'])
    try:
        with PILImage.open(img_path) as img:
            w, h = img.size
            aspect = h / w
            target_height = target_width * aspect
            return Image(img_path, width=target_width, height=target_height)
    except Exception as e:
        return Paragraph(f"<font color='red'><b>Image Error:</b> Failed to load {img_path} ({e})</font>", getSampleStyleSheet()['BodyText'])

def build_pdf():
    # File Paths
    pdf_filename = "YOLOv8_Live_Tracking_Project_Report.pdf"
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [base_dir, os.getcwd()]
    brain_parent = os.path.expanduser(r"~\.gemini\antigravity-ide\brain")
    if os.path.exists(brain_parent):
        search_dirs.append(brain_parent)
    
    stream_images, analytics_images, settings_images = [], [], []
    for s_dir in search_dirs:
        stream_images.extend(glob.glob(os.path.join(s_dir, "**", "dashboard_stream_*.png"), recursive=True))
        analytics_images.extend(glob.glob(os.path.join(s_dir, "**", "dashboard_analytics_*.png"), recursive=True))
        settings_images.extend(glob.glob(os.path.join(s_dir, "**", "dashboard_settings_*.png"), recursive=True))
    
    stream_img = max(stream_images, key=os.path.getctime) if stream_images else None
    analytics_img = max(analytics_images, key=os.path.getctime) if analytics_images else None
    settings_img = max(settings_images, key=os.path.getctime) if settings_images else None

    # Setup Document
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=26,
        leading=32,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#4F46E5'),
        spaceAfter=30
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=14,
        spaceAfter=10,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#4F46E5'),
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        leftIndent=20,
        firstLineIndent=-10,
        spaceAfter=4
    )
    
    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B'),
        backColor=colors.HexColor('#F8FAFC'),
        borderColor=colors.HexColor('#E2E8F0'),
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=8
    )
    
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569')
    )
    
    meta_val_style = ParagraphStyle(
        'MetaValue',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )

    story = []

    # ================= PAGE 1: COVER PAGE =================
    story.append(Spacer(1, 40))
    
    # Category Header
    cover_header_data = [[Paragraph("<font color='white'><b>PROJECT DEVELOPMENT REPORT</b></font>", ParagraphStyle('CH', fontName='Helvetica-Bold', fontSize=10, leading=12))]]
    cover_header_table = Table(cover_header_data, colWidths=[480])
    cover_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#4F46E5')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(cover_header_table)
    story.append(Spacer(1, 50))
    
    # Title & Subtitle
    story.append(Paragraph("YOLOv8 Live Object Tracking & Analytics", title_style))
    story.append(Paragraph("A premium Computer Vision system combining deep learning detection with association filters.", subtitle_style))
    story.append(Spacer(1, 80))
    
    # Metadata Block
    metadata_data = [
        [Paragraph("System Architecture:", meta_label_style), Paragraph("React (Vite) + FastAPI + YOLOv8 + DeepSORT", meta_val_style)],
        [Paragraph("Target Models:", meta_label_style), Paragraph("YOLOv8 Nano, Small, Medium", meta_val_style)],
        [Paragraph("Report Status:", meta_label_style), Paragraph("Production Ready / Complete", meta_val_style)],
        [Paragraph("Created Location:", meta_label_style), Paragraph("c:/Users/SHANMUKH/.gemini/antigravity/scratch/yolov8-live-tracking", meta_val_style)],
        [Paragraph("Generated On:", meta_label_style), Paragraph("June 2026", meta_val_style)],
    ]
    meta_table = Table(metadata_data, colWidths=[130, 350])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#F1F5F9')),
    ]))
    story.append(meta_table)
    
    story.append(Spacer(1, 100))
    story.append(Paragraph("<font color='#64748B'><i>Prepared for High-Performance Intelligent Surveillance Operations.</i></font>", ParagraphStyle('ItalicText', fontName='Helvetica-Oblique', fontSize=9, textColor=colors.HexColor('#64748B'))))
    story.append(PageBreak())

    # ================= PAGE 2: ARCHITECTURE & CORE FEATURES =================
    story.append(Paragraph("1. Executive Summary & Architecture", h1_style))
    story.append(Paragraph("The <b>YOLOv8 Live Object Tracking System</b> is a high-frequency computer vision pipeline engineered to perform object detection, identity association, and real-time telemetry streaming. The application integrates modern deep learning models with classic tracking algorithms to maintain stable target identities across frames even during occlusion.", body_style))
    
    story.append(Paragraph("1.1 Data Processing Flow", h2_style))
    story.append(Paragraph("The system is divided into two primary services working asynchronously:", body_style))
    story.append(Paragraph("• <b>Backend Server (FastAPI)</b>: Manages OpenCV frame capturing, carries out model inference via Ultralytics YOLOv8, tracks object bounding boxes with DeepSORT or ByteTrack, and streams processed frames as standard JPEG multipart feeds. Telemetry data is broadcasted on a separate WebSocket endpoint.", bullet_style))
    story.append(Paragraph("• <b>Frontend Dashboard (React + TypeScript)</b>: A glass-morphic UI rendered using Vite. It consumes the FastAPI live MJPEG feed, establishes a WebSocket connection to fetch active coordinates, visualizes tracking trails, and provides a control panel to alter parameters (IoU thresholds, model selection) dynamically.", bullet_style))
    
    story.append(Paragraph("1.2 Installation & Startup Code", h2_style))
    story.append(Paragraph("Setting up and launching the software package is accomplished via standard Python commands:", body_style))
    story.append(Paragraph("pip install -r requirements.txt<br/>python backend/server.py", code_style))
    
    story.append(PageBreak())

    # ================= PAGE 3: PRIMARY FEED SCREENSHOT =================
    story.append(Paragraph("2. Telemetry Feed Interface", h1_style))
    story.append(Paragraph("The core interface provides a glass-panel dashboard for camera controls and telemetry monitoring. Users can choose among multiple streams (Mock simulation, PC Webcam, Browser camera, or Video File Upload).", body_style))
    story.append(Spacer(1, 10))
    
    # Embed Live Feed screenshot
    story.append(get_image_flowable(stream_img, target_width=470))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Figure 1:</b> The primary 'Telemetry Feed' viewport. The screen demonstrates simulated neon grids, electric-colored bounding boxes with rounded corners, overlay badges showing tracking ID numbers, class labels, and live frame-per-second performance metrics.", ParagraphStyle('CapStyle', fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=colors.HexColor('#475569'))))
    
    story.append(PageBreak())

    # ================= PAGE 4: SESSION ANALYTICS SCREENSHOT =================
    story.append(Paragraph("3. Session Analytics Dashboard", h1_style))
    story.append(Paragraph("The Analytics dashboard records object occurrence distributions and maps target counts over time. It allows operations managers to identify peak traffic, compute object density distributions, and monitor average latency.", body_style))
    story.append(Spacer(1, 10))
    
    # Embed Analytics screenshot
    story.append(get_image_flowable(analytics_img, target_width=470))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Figure 2:</b> Analytics tab displaying the average processing FPS, unique object counts, an interactive SVG Line Chart tracking target quantities over a 25-frame historical window, and the active categories percentage distribution list.", ParagraphStyle('CapStyle', fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=colors.HexColor('#475569'))))
    
    story.append(PageBreak())

    # ================= PAGE 5: SYSTEM CONFIG & BENCHMARKS =================
    story.append(Paragraph("4. System Configuration & Model Benchmarks", h1_style))
    story.append(Paragraph("The 'System Config' tab provides sliders to configure intersection-over-union limits and detection confidence thresholds. Toggle switches control whether bounding boxes, labels, scores, and center trails are displayed on the stream overlay.", body_style))
    story.append(Spacer(1, 5))
    
    story.append(get_image_flowable(settings_img, target_width=470))
    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>Figure 3:</b> Configuration panel featuring dynamic range slider adjustments and UI toggle switches that sync parameter updates directly to the FastAPI server in real time.", ParagraphStyle('CapStyle', fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=colors.HexColor('#475569'))))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("4.1 Performance Benchmark Matrix", h2_style))
    
    # Benchmark Table
    table_data = [
        ["Model Name", "Parameters", "Typical CPU FPS", "Typical GPU FPS", "Memory Footprint"],
        ["YOLOv8 Nano", "3.2M", "15 - 20 FPS", "60 - 80 FPS", "~12 MB"],
        ["YOLOv8 Small", "11.2M", "8 - 12 FPS", "45 - 60 FPS", "~30 MB"],
        ["YOLOv8 Medium", "25.9M", "3 - 5 FPS", "25 - 35 FPS", "~78 MB"]
    ]
    bench_table = Table(table_data, colWidths=[110, 85, 95, 95, 95])
    bench_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(bench_table)

    story.append(Spacer(1, 20))
    story.append(Paragraph("5. Technical Conclusion", ParagraphStyle('TC_Head', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.HexColor('#0F172A'))))
    story.append(Paragraph("The integration of YOLOv8 with real-time trackers provides high-quality surveillance data. Native trackers (ByteTrack/BotSORT) operate with negligible CPU overhead, while DeepSORT provides superior identity stability under complex occlusion conditions at the cost of additional feature extraction compute requirements.", body_style))

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print("PDF Generation complete!")

if __name__ == "__main__":
    build_pdf()
