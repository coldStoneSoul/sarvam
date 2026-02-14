from typing import List
from dataclasses import dataclass, field

@dataclass
class AppConfig:
    SECRET_KEY: str = "dev"
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
