import os
import json
import yaml
import uuid
from io import BytesIO
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, field

from flask import Flask, request, jsonify, render_template, send_file, abort
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
)
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from textprocessor import TextProcessor

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
print("starting Flask app setup tests...")
@dataclass
class AppConfig:
    SUPPORTED_EXTENSIONS: List[str] = field(default_factory=lambda: [
        "pdf", "docx", "html", "htm", "pptx",
        "png", "jpg", "jpeg", "asciidoc", "md",
    ])
    OUTPUT_FORMATS: List[str] = field(default_factory=lambda: ["markdown", "json", "yaml"])
    MAX_PAGES: int = 100
    MAX_FILE_SIZE: int = 20_971_520  # 20 MB
    UPLOAD_FOLDER: str = "uploads"
    RESULT_FOLDER: str = "results"


config = AppConfig()

# ---------------------------------------------------------------------------
# Flask setup
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_FILE_SIZE * 10  # allow batch uploads

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.RESULT_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# Docling converter (singleton-ish)
# ---------------------------------------------------------------------------

_converters: Dict[bool, DocumentConverter] = {}


def get_converter(use_ocr: bool = True) -> DocumentConverter:
    if use_ocr not in _converters:
        pipeline_options = PdfPipelineOptions(
            do_ocr=use_ocr,
            do_table_structure=False,
        )
        _converters[use_ocr] = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.ASCIIDOC,
                InputFormat.MD,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=PyPdfiumDocumentBackend,
                    pipeline_options=pipeline_options,
                ),
                InputFormat.DOCX: WordFormatOption(pipeline_cls=SimplePipeline),
                InputFormat.HTML: WordFormatOption(),
                InputFormat.PPTX: WordFormatOption(),
            },
        )
    return _converters[use_ocr]


def convert_document(file_bytes: bytes, filename: str, use_ocr: bool = True):
    converter = get_converter(use_ocr)
    buf = BytesIO(file_bytes)
    source = DocumentStream(name=filename, stream=buf)
    result = converter.convert(
        source,
        max_num_pages=config.MAX_PAGES,
        max_file_size=config.MAX_FILE_SIZE,
    )
    return result


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
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
@app.route("/api/ping", methods=["GET"])
def api_ping():
    return jsonify({"success": True, "message": "pong"})

@app.route("/schema", methods=["GET"])
def scheme():
    return render_template('scheme.html')
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
    # 1. Extract Features
    case_data = processor.extract_case_details(text_content)
    
    # 2. Mock XGBoost Call (Replace with your model.predict)
    # prediction = my_xgboost_model.predict(case_data)
    prediction_outcome = {"predicted_win_rate": "74%", "risk_level": "Low"}
    
    # 3. Draft Settlement
    draft = processor.draft_settlement(text_content, {**case_data, **prediction_outcome})
    
    return jsonify({
        "case_data": case_data,
        "prediction": prediction_outcome,
        "settlement_draft": draft,
        "text_content": text_content
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
# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
