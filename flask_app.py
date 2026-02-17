import os
import json
import yaml
import uuid
from io import BytesIO
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, field

from flask import Flask, request, jsonify, render_template, send_file, abort, make_response
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from services.settlement_drafter import MSMESettlementEngine

# Import modular services
from textprocessor import TextProcessor
from config import config
from services.prediction import (
    run_xgb_prediction,
    generate_settlement_draft_text,
    dispute_types,
    jurisdictions,
)
from services.document import convert_document
from services.negotiation_engine import NegotiationSessionManager

negotiation_manager = NegotiationSessionManager()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
print("starting Flask app setup tests...")


# ---------------------------------------------------------------------------
# Flask setup
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_FILE_SIZE * 10  # allow batch uploads

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.RESULT_FOLDER, exist_ok=True)




def format_output(result, output_format: str):
    """Return (content_string, mimetype, extension)."""
    fmt = output_format.lower()
    if fmt == "markdown":
        content = result.document.export_to_markdown()
        return content, "text/markdown", "md"
    elif fmt == "json":
        data = result.document.export_to_dict()
        content = json.dumps(data, indent=2, default=str)
        return content, "application/json", "json"
    elif fmt == "yaml":
        data = result.document.export_to_dict()
        content = yaml.safe_dump(data, default_flow_style=False)
        return content, "text/yaml", "yaml"
    else:
        raise ValueError(f"Unsupported output format: {fmt}")


# ---------------------------------------------------------------------------
# Frontend route
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        supported_extensions=config.SUPPORTED_EXTENSIONS,
        output_formats=config.OUTPUT_FORMATS,
        dispute_types=dispute_types,
        jurisdictions=jurisdictions,
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
@app.route("/api/ping", methods=["GET"])
def api_ping():
    return jsonify({"success": True, "message": "pong"})

@app.route("/schema", methods=["GET"])
def scheme():
    return render_template('scheme.html', dispute_types=dispute_types, jurisdictions=jurisdictions)
@app.route("/api/convert", methods=["POST"])
def api_convert():
    """
    Convert an uploaded document.

    Form fields / multipart:
        file            – the document to convert (required)
        output_format   – markdown | json | yaml  (default: markdown)
        use_ocr         – true | false             (default: true)

    Returns the converted content as a downloadable file,
    or JSON with the content when ?inline=true is passed.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    uploaded = request.files["file"]
    if uploaded.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if ext not in config.SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    output_format = request.form.get("output_format", "markdown").lower()
    if output_format not in config.OUTPUT_FORMATS:
        return jsonify({"error": f"Unsupported output format: {output_format}"}), 400

    use_ocr = request.form.get("use_ocr", "true").lower() in ("true", "1", "yes")

    try:
        file_bytes = uploaded.read()
        result = convert_document(file_bytes, uploaded.filename, use_ocr)
        content, mimetype, out_ext = format_output(result, output_format)

        # If caller wants inline JSON response (e.g. frontend AJAX)
        inline = request.args.get("inline", "false").lower() in ("true", "1")
        if inline:
            return jsonify({
                "filename": f"{uploaded.filename.rsplit('.', 1)[0]}.{out_ext}",
                "format": output_format,
                "content": content if isinstance(content, str) else json.loads(content),
            })

        # Otherwise return as downloadable file
        out_filename = f"{uploaded.filename.rsplit('.', 1)[0]}.{out_ext}"
        buf = BytesIO(content.encode("utf-8"))
        buf.seek(0)
        return send_file(
            buf,
            mimetype=mimetype,
            as_attachment=True,
            download_name=out_filename,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/convert/batch", methods=["POST"])
def api_convert_batch():
    """
    Convert multiple uploaded documents at once.

    Form fields / multipart:
        files[]         – one or more documents to convert (required)
        output_format   – markdown | json | yaml  (default: markdown)
        use_ocr         – true | false             (default: true)

    Returns JSON with results for each file.
    """
    files = request.files.getlist("files[]")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files provided"}), 400

    output_format = request.form.get("output_format", "markdown").lower()
    if output_format not in config.OUTPUT_FORMATS:
        return jsonify({"error": f"Unsupported output format: {output_format}"}), 400

    use_ocr = request.form.get("use_ocr", "true").lower() in ("true", "1", "yes")

    results = []
    for uploaded in files:
        if uploaded.filename == "":
            continue

        ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
        if ext not in config.SUPPORTED_EXTENSIONS:
            results.append({
                "original_filename": uploaded.filename,
                "success": False,
                "error": f"Unsupported file type: .{ext}",
            })
            continue

        try:
            file_bytes = uploaded.read()
            result = convert_document(file_bytes, uploaded.filename, use_ocr)
            content, mimetype, out_ext = format_output(result, output_format)

            results.append({
                "original_filename": uploaded.filename,
                "filename": f"{uploaded.filename.rsplit('.', 1)[0]}.{out_ext}",
                "format": output_format,
                "content": content if isinstance(content, str) else json.loads(content),
                "success": True,
            })
        except Exception as e:
            results.append({
                "original_filename": uploaded.filename,
                "success": False,
                "error": str(e),
            })

    return jsonify({"results": results, "total": len(results)})


@app.route("/api/formats", methods=["GET"])
def api_formats():
    """Return supported input extensions and output formats."""
    return jsonify({
        "supported_extensions": config.SUPPORTED_EXTENSIONS,
        "output_formats": config.OUTPUT_FORMATS,
        "max_file_size_bytes": config.MAX_FILE_SIZE,
    })


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    """
    Convert a document and generate an AI summary.
    
    Form fields / multipart:
        file            – the document to convert (required)
        use_ocr         – true | false             (default: true)
        max_tokens      – max tokens for summary   (default: 500)
        temperature     – 0-2, sampling temp       (default: 0.7)
        
    Returns JSON with the converted text and AI-generated summary.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    uploaded = request.files["file"]
    if uploaded.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if ext not in config.SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    use_ocr = request.form.get("use_ocr", "true").lower() in ("true", "1", "yes")
    max_tokens = int(request.form.get("max_tokens", 500))
    temperature = float(request.form.get("temperature", 0.7))

    try:
        # Convert document to markdown
        file_bytes = uploaded.read()
        result = convert_document(file_bytes, uploaded.filename, use_ocr)
        text_content, _, _ = format_output(result, "markdown")
        
        # Generate summary using TextProcessor
        processor = TextProcessor()
        summary_result = processor.summarize(
            text=text_content,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return jsonify({
            "filename": uploaded.filename,
            "text_content": text_content,
            "summary": summary_result["summary"],
            "metadata": {
                "model": summary_result["model"],
                "tokens_used": summary_result["tokens_used"],
                "finish_reason": summary_result["finish_reason"]
            },
            "success": True
        })

    except ValueError as e:
        return jsonify({"error": f"Configuration error: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/summarize-text", methods=["POST"])
def api_summarize_text():
    """
    Generate an AI summary from provided text (no file upload).
    
    JSON body:
        text            – the text to summarize (required)
        max_tokens      – max tokens for summary   (default: 500)
        temperature     – 0-2, sampling temp       (default: 0.7)
        
    Returns JSON with the AI-generated summary.
    """
    data = request.get_json()
    
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400
    
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Text cannot be empty"}), 400
    
    max_tokens = int(data.get("max_tokens", 500))
    temperature = float(data.get("temperature", 0.7))
    
    try:
        # Generate summary using TextProcessor
        processor = TextProcessor()
        summary_result = processor.summarize(
            text=text,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return jsonify({
            "summary": summary_result["summary"],
            "metadata": {
                "model": summary_result["model"],
                "tokens_used": summary_result["tokens_used"],
                "finish_reason": summary_result["finish_reason"]
            },
            "success": True
        })
    
    except ValueError as e:
        return jsonify({"error": f"Configuration error: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/extract-key-points", methods=["POST"])
def api_extract_key_points():
    """
    Convert a document and extract key points using AI.
    
    Form fields / multipart:
        file            – the document to convert (required)
        use_ocr         – true | false             (default: true)
        num_points      – number of key points     (default: 5)
        
    Returns JSON with the converted text and extracted key points.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    uploaded = request.files["file"]
    if uploaded.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if ext not in config.SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    use_ocr = request.form.get("use_ocr", "true").lower() in ("true", "1", "yes")
    num_points = int(request.form.get("num_points", 5))

    try:
        # Convert document to markdown
        file_bytes = uploaded.read()
        result = convert_document(file_bytes, uploaded.filename, use_ocr)
        text_content, _, _ = format_output(result, "markdown")
        
        # Extract key points using TextProcessor
        processor = TextProcessor()
        points_result = processor.extract_key_points(
            text=text_content,
            num_points=num_points
        )
        
        return jsonify({
            "filename": uploaded.filename,
            "text_content": text_content,
            "key_points": points_result["key_points"],
            "metadata": {
                "model": points_result["model"],
                "tokens_used": points_result["tokens_used"]
            },
            "success": True
        })

    except ValueError as e:
        return jsonify({"error": f"Configuration error: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Convert a document and perform custom AI analysis.
    
    Form fields / multipart:
        file            – the document to convert (required)
        instruction     – analysis instruction     (required)
        use_ocr         – true | false             (default: true)
        max_tokens      – max tokens for response  (default: 1000)
        
    Returns JSON with the converted text and analysis results.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    if "instruction" not in request.form:
        return jsonify({"error": "Analysis instruction is required"}), 400

    uploaded = request.files["file"]
    if uploaded.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if ext not in config.SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    instruction = request.form.get("instruction")
    use_ocr = request.form.get("use_ocr", "true").lower() in ("true", "1", "yes")
    max_tokens = int(request.form.get("max_tokens", 1000))

    try:
        # Convert document to markdown
        file_bytes = uploaded.read()
        result = convert_document(file_bytes, uploaded.filename, use_ocr)
        text_content, _, _ = format_output(result, "markdown")
        
        # Perform custom analysis using TextProcessor
        processor = TextProcessor()
        analysis_result = processor.custom_analysis(
            text=text_content,
            instruction=instruction,
            max_tokens=max_tokens
        )
        
        return jsonify({
            "filename": uploaded.filename,
            "instruction": instruction,
            "text_content": text_content,
            "analysis": analysis_result["result"],
            "metadata": {
                "model": analysis_result["model"],
                "tokens_used": analysis_result["tokens_used"]
            },
            "success": True
        })

    except ValueError as e:
        return jsonify({"error": f"Configuration error: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/analyze-case", methods=["POST"])
def api_analyze_case():
    """Converts doc, extracts features, runs prediction, and drafts settlement."""
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    uploaded = request.files["file"]
    file_bytes = uploaded.read()
    result = convert_document(file_bytes, uploaded.filename, True)
    text_content = result.document.export_to_markdown()

    processor = TextProcessor()
    case_data = processor.extract_case_details(text_content)

    # Real XGBoost prediction
    try:
        prediction = run_xgb_prediction(
            claim_amount=int(case_data.get("claim_amount") or 100000),
            delay_days=int(case_data.get("delay_days") or 100),
            document_count=int(case_data.get("document_count") or 1),
            dispute_type=case_data.get("dispute_type") or dispute_types[0],
            jurisdiction=case_data.get("jurisdiction") or jurisdictions[0],
        )
    except Exception:
        prediction = {"probability": 50.0, "priority": "Medium", "priority_class": "medium",
                      "settle_min": "70,000", "settle_max": "85,000", "deep_analysis": [], "success": True,
                      "document_score": 0.25, "delay_days": 100, "claim_amount": "100,000"}

    draft = processor.draft_settlement(text_content, {**case_data, **prediction})

    return jsonify({
        "case_data": case_data,
        "prediction": prediction,
        "settlement_draft": draft,
        "text_content": text_content,
    })


def clean_number(val):
    """Remove non-numeric characters from string and return int."""
    if isinstance(val, (int, float)):
        return int(val)
    if not val:
        return 0
    # Remove currency symbols, commas, spaces
    clean = ''.join(c for c in str(val) if c.isdigit() or c == '.')
    try:
        return int(float(clean))
    except ValueError:
        return 0

@app.route("/api/extract-fields", methods=["POST"])
def api_extract_fields():
    """Upload a doc, run OCR, extract case fields for user review."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    uploaded = request.files["file"]
    if uploaded.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    try:
        file_bytes = uploaded.read()
        result = convert_document(file_bytes, uploaded.filename, True)
        text_content = result.document.export_to_markdown()
        print("text_content",text_content)

        #here we are passing those to llm
        processor = TextProcessor()
        fields = processor.extract_case_details(text_content)

        # Normalise — ensure the frontend always gets usable values
        dispute_type = fields.get("dispute_type", "").lower()
        # Fallback to 'others' if not in strict list (or check loose match)
        if dispute_type not in dispute_types:
             # Try to match if it's close or use others
             dispute_type = "others" if dispute_type not in dispute_types else dispute_type

        return jsonify({
            "success": True,
            "text_content": text_content,
            "fields": {
                "claim_amount": clean_number(fields.get("claim_amount")),
                "delay_days": clean_number(fields.get("delay_days")),
                "document_count": clean_number(fields.get("document_count")),
                "dispute_type": dispute_type or dispute_types[0],
                "jurisdiction": fields.get("jurisdiction") or jurisdictions[0],
            },
            "dispute_types": dispute_types,
            "jurisdictions": jurisdictions,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """Run XGBoost prediction on user-edited fields."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        claim_amount = int(data["claim_amount"])
        delay_days = int(data["delay_days"])
        document_count = int(data["document_count"])
        dt = data["dispute_type"]
        jur = data["jurisdiction"]

        result = run_xgb_prediction(claim_amount, delay_days, document_count, dt, jur)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# @app.route("/api/generate-draft", methods=["POST"])
# def api_generate_draft():
#     """Generate settlement draft via LLM + rule-based template."""
#     data = request.get_json()
#     if not data:
#         return jsonify({"error": "No data provided"}), 400

#     try:
#         text_content = data.get("text_content", "")
#         case_info = data.get("case_data", {})
#         prediction = data.get("prediction", {})

#         # Rule-based draft
#         rule_draft = generate_settlement_draft_text({**case_info, **prediction})

#         # LLM draft
#         processor = TextProcessor()
#         llm_draft = processor.draft_settlement(text_content, {**case_info, **prediction})

#         return jsonify({"success": True, "rule_draft": rule_draft, "llm_draft": llm_draft})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)}), 500
@app.route('/api/generate-draft', methods=['POST'])
def generate_draft():
    data = request.json

    engine = MSMESettlementEngine(
        rbi_bank_rate=0.085,  # configurable
    )

    final_offer = data.get("final_offer")

    # Compatibility: Handle both flat and nested structure
    raw_case = data.get("case_data", {})
    raw_pred = data.get("prediction", {})

    case_data = {
        "claim_amount": raw_case.get("claim_amount") or data.get("claim_amount"),
        "delay_days": raw_case.get("delay_days") or data.get("delay_days"),
        "agreed_payment_days": raw_case.get("agreed_payment_days") or data.get("agreed_payment_days"),
        "jurisdiction": raw_case.get("jurisdiction") or data.get("jurisdiction"),
        "case_id": raw_case.get("case_id") or raw_pred.get("case_id") or data.get("case_id", "N/A")
    }

    # Ensure we grab probability from nested object if present
    prob = raw_pred.get("probability")
    if prob is None:
        prob = data.get("probability", 0.7)

    prediction_data = {
        "probability": prob
    }

    result = engine.generate(
        case_data=case_data,
        prediction_data=prediction_data,
        final_offer=final_offer
    )

    return jsonify({
        "success": True,
        "rule_draft": result["full_text"],
        "structured_draft": result["structured_draft"],
        "settlement_amount": result["settlement_amount"],
        "statutory_entitlement": result["statutory_entitlement"],
        "interest_component": result["interest_component"],
        "annual_interest_rate": result["annual_interest_rate"],
        "concession_value": result["concession_value"]
    })
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat specifically about the provided document context."""
    data = request.json
    doc_text = data.get("context")
    user_query = data.get("message")
    
    processor = TextProcessor()
    response = processor.client.chat.completions.create(
        model="ai/granite-4.0-micro",
        messages=[
            {"role": "system", "content": f"Answer based ONLY on this document:\n{doc_text}"},
            {"role": "user", "content": user_query}
        ]
    )
    return jsonify({"response": response.choices[0].message.content})


@app.route("/api/export-pdf", methods=["POST"])
def export_pdf():
    """Export analysis report as PDF."""
    try:
        data = request.get_json()
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
            fontSize=24, textColor=colors.HexColor('#667eea'), spaceAfter=30,
            alignment=TA_CENTER, fontName='Helvetica-Bold')
        heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
            fontSize=14, textColor=colors.HexColor('#333333'), spaceAfter=12,
            spaceBefore=20, fontName='Helvetica-Bold')
        normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'],
            fontSize=10, textColor=colors.HexColor('#666666'), spaceAfter=6)

        elements.append(Paragraph("MSME Case Analysis Report", title_style))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", normal_style))
        elements.append(Spacer(1, 0.3*inch))

        # Case Details
        elements.append(Paragraph("Case Details", heading_style))
        case_table_data = [
            ['Claim Amount:', f"₹{data.get('claim_amount', 'N/A')}"],
            ['Payment Delay:', f"{data.get('delay_days', 'N/A')} days"],
            ['Documents:', f"{data.get('document_count', 'N/A')} documents"],
            ['Document Score:', f"{data.get('document_score', 'N/A')}"],
            ['Dispute Type:', data.get('dispute_type', 'N/A')],
            ['Jurisdiction:', data.get('jurisdiction', 'N/A')]
        ]
        t = Table(case_table_data, colWidths=[2.5*inch, 4*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.3*inch))

        # Assessment Results
        elements.append(Paragraph("AI Assessment Results", heading_style))
        results_data = [
            ['Settlement Probability:', f"{data.get('probability', 'N/A')}%"],
            ['Priority Level:', data.get('priority', 'N/A')],
            ['Settlement Range:', f"₹{data.get('settle_min', 'N/A')} - ₹{data.get('settle_max', 'N/A')}"]
        ]
        rt = Table(results_data, colWidths=[2.5*inch, 4*inch])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(rt)
        elements.append(Spacer(1, 0.3*inch))

        # Deep Analysis
        elements.append(Paragraph("Deep Analysis", heading_style))
        for item in data.get('deep_analysis', []):
            sym = '✓' if item['impact'] == 'positive' else '!' if item['impact'] == 'negative' else '○'
            elements.append(Paragraph(f"<b>{sym} {item['factor']}</b>", normal_style))
            desc_style = ParagraphStyle('Desc', parent=normal_style, leftIndent=20, spaceAfter=12)
            elements.append(Paragraph(item['description'], desc_style))

        elements.append(Spacer(1, 0.3*inch))
        disclaimer_style = ParagraphStyle('Disclaimer', parent=normal_style, fontSize=9,
            textColor=colors.HexColor('#0d47a1'), leftIndent=10, rightIndent=10,
            borderColor=colors.HexColor('#2196F3'), borderWidth=1, borderPadding=10,
            backColor=colors.HexColor('#e7f3ff'))
        elements.append(Paragraph(
            "⚠ This is an AI-generated decision support recommendation. The final outcome is subject to the review of the adjudicating officer.",
            disclaimer_style))

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=MSME_Case_Analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        return response
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route("/api/export-settlement-pdf", methods=["POST"])
def export_settlement_pdf():
    """Export settlement draft as PDF."""
    try:
        data = request.get_json()
        draft_text = generate_settlement_draft_text(data)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
            topMargin=0.75*inch, bottomMargin=0.75*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('SettlementTitle', parent=styles['Heading1'],
            fontSize=16, textColor=colors.HexColor('#1a1a1a'), spaceAfter=6,
            alignment=TA_CENTER, fontName='Helvetica-Bold')
        subtitle_style = ParagraphStyle('SettlementSubtitle', parent=styles['Normal'],
            fontSize=11, textColor=colors.HexColor('#555555'), spaceAfter=20,
            alignment=TA_CENTER, fontName='Helvetica')
        section_heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'],
            fontSize=13, textColor=colors.HexColor('#2c3e50'), spaceAfter=8,
            spaceBefore=15, fontName='Helvetica-Bold')
        body_style = ParagraphStyle('SettlementBody', parent=styles['Normal'],
            fontSize=10, textColor=colors.HexColor('#333333'), spaceAfter=8,
            leading=14, fontName='Helvetica')
        disclaimer_style = ParagraphStyle('SettlementDisclaimer', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#555555'), spaceAfter=6,
            leading=12, fontName='Helvetica-Oblique', leftIndent=10, rightIndent=10,
            borderColor=colors.HexColor('#cccccc'), borderWidth=1, borderPadding=10,
            backColor=colors.HexColor('#f9f9f9'))

        for line in draft_text.split('\n'):
            if not line.strip():
                elements.append(Spacer(1, 0.1*inch))
            elif line.startswith('ASSISTED SETTLEMENT DRAFT'):
                elements.append(Paragraph(line, title_style))
            elif line.startswith('(Generated by'):
                elements.append(Paragraph(line, subtitle_style))
            elif line.startswith('This draft is generated to assist'):
                elements.append(Paragraph(line, body_style))
            elif line.startswith('Final terms are subject'):
                elements.append(Paragraph(line, body_style))
                elements.append(Spacer(1, 0.2*inch))
            elif line.startswith('='):
                elements.append(Spacer(1, 0.15*inch))
            elif line.startswith('-'):
                pass
            elif line.strip().isupper() and len(line.strip()) > 5:
                elements.append(Paragraph(line.strip(), section_heading_style))
            elif line.startswith('This draft is generated as an AI'):
                elements.append(Paragraph(line, disclaimer_style))
            elif line.startswith('It does not constitute'):
                elements.append(Paragraph(line, disclaimer_style))
            elif line.startswith('All final decisions'):
                elements.append(Paragraph(line, disclaimer_style))
            elif line.startswith('by the designated authority'):
                elements.append(Paragraph(line, disclaimer_style))
            else:
                elements.append(Paragraph(line, body_style))

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        case_id = data.get('case_id', 'Draft')
        response.headers['Content-Disposition'] = f'attachment; filename=Settlement_Draft_{case_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        return response
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route("/api/export-ai-draft-pdf", methods=["POST"])
def export_ai_draft_pdf():
    """Export AI-generated settlement draft as PDF."""
    try:
        data = request.get_json()
        draft_text = data.get("draft_text", "")
        if not draft_text.strip():
            return jsonify({"success": False, "error": "No draft text provided"}), 400

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
            topMargin=0.75*inch, bottomMargin=0.75*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('AIDraftTitle', parent=styles['Heading1'],
            fontSize=18, textColor=colors.HexColor('#1a1a1a'), spaceAfter=6,
            alignment=TA_CENTER, fontName='Helvetica-Bold')
        subtitle_style = ParagraphStyle('AIDraftSubtitle', parent=styles['Normal'],
            fontSize=10, textColor=colors.HexColor('#555555'), spaceAfter=20,
            alignment=TA_CENTER, fontName='Helvetica')
        section_style = ParagraphStyle('AIDraftSection', parent=styles['Heading2'],
            fontSize=13, textColor=colors.HexColor('#2c3e50'), spaceAfter=8,
            spaceBefore=15, fontName='Helvetica-Bold')
        body_style = ParagraphStyle('AIDraftBody', parent=styles['Normal'],
            fontSize=10, textColor=colors.HexColor('#333333'), spaceAfter=6,
            leading=14, fontName='Helvetica')
        disclaimer_style = ParagraphStyle('AIDraftDisclaimer', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#0d47a1'), leftIndent=10,
            rightIndent=10, borderColor=colors.HexColor('#2196F3'),
            borderWidth=1, borderPadding=10, backColor=colors.HexColor('#e7f3ff'))

        elements.append(Paragraph("AI-Generated Settlement Draft", title_style))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", subtitle_style))
        elements.append(Spacer(1, 0.2*inch))

        # Parse the draft text into paragraphs
        for line in draft_text.split('\n'):
            stripped = line.strip()
            if not stripped:
                elements.append(Spacer(1, 0.08*inch))
            elif stripped.startswith('##'):
                elements.append(Paragraph(stripped.lstrip('#').strip(), section_style))
            elif stripped.startswith('#'):
                elements.append(Paragraph(stripped.lstrip('#').strip(), section_style))
            elif stripped.startswith('---') or stripped.startswith('==='):
                elements.append(Spacer(1, 0.1*inch))
            elif stripped.startswith('**') and stripped.endswith('**'):
                elements.append(Paragraph(f"<b>{stripped.strip('*')}</b>", body_style))
            else:
                # Escape XML special chars for ReportLab
                safe = stripped.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                elements.append(Paragraph(safe, body_style))

        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph(
            "⚠ This is an AI-generated settlement draft. It does not constitute legal advice. "
            "Final terms are subject to mutual consent and approval by the adjudicating authority.",
            disclaimer_style))

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = (
            f'attachment; filename=AI_Settlement_Draft_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
        return response
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/negotiation/start', methods=['POST'])
def start_negotiation():
    """Initialize multi-round negotiation"""
    try:
        data = request.json or {}
        
        # Safely convert to proper types – form values arrive as strings
        claim_raw = str(data.get("claim_amount", "0")).replace(",", "")
        delay_raw = str(data.get("delay_days", "0")).replace(",", "")
        
        case_data = {
            "claim_amount": int(float(claim_raw)) if claim_raw else 100000,
            "delay_days": int(float(delay_raw)) if delay_raw else 90,
            "document_count": int(data.get("document_count", 1)),
            "dispute_type": data.get("dispute_type", "others")
        }
        prediction = {
            "probability": float(data.get("probability", 70))
        }
        
        session_id = str(uuid.uuid4())[:8]
        result = negotiation_manager.create_session(session_id, case_data, prediction)
        result["session_id"] = session_id
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Negotiation start failed: {str(e)}"}), 500

@app.route('/api/negotiation/continue', methods=['POST'])
def continue_negotiation():
    """Process opponent counter-offer"""
    try:
        data = request.json or {}
        session_id = data.get("session_id")
        if not session_id:
            return jsonify({"error": "Missing session_id"}), 400
        
        opponent_offer = int(float(str(data.get("opponent_offer", 0)).replace(",", "")))
        if opponent_offer <= 0:
            return jsonify({"error": "Invalid opponent offer amount"}), 400
        
        result = negotiation_manager.continue_session(
            session_id,
            opponent_offer,
            data.get("message", "")
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Negotiation continue failed: {str(e)}"}), 500


@app.route('/api/transcribe-voice', methods=['POST'])
def transcribe_voice():
    """Fallback voice transcription endpoint"""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    # Placeholder – return a helpful message since server-side
    # transcription requires Whisper or similar model
    return jsonify({
        "text": "",
        "fallback": True,
        "message": "Server-side transcription not configured. Using browser Web Speech API."
    })
# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
