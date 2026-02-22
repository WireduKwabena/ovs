"""OCR service helpers for document text extraction."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import cv2
import numpy as np

try:
    import easyocr
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    easyocr = None

try:
    import pytesseract
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pytesseract = None

try:
    from PyPDF2 import PdfReader
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    PdfReader = None

try:
    from pdf2image import convert_from_path
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    convert_from_path = None

from .structured_extractor import StructuredExtractor
from ai_ml_services.utils.pdf import pdf2image_kwargs

logger = logging.getLogger(__name__)


ImageInput = Union[str, Path, np.ndarray]


class OCRService:
    """Unified OCR service for image and PDF documents."""

    def __init__(
        self,
        language: str = "en",
        prefer_easyocr: bool = False,
        max_pdf_pages: int = 5,
    ):
        self.language = language
        self.prefer_easyocr = prefer_easyocr
        self.max_pdf_pages = max_pdf_pages
        self.extractor = StructuredExtractor(language=language)
        self.easyocr_reader = self._build_easyocr_reader()

    def _build_easyocr_reader(self):
        if not self.prefer_easyocr or easyocr is None:
            return None
        try:
            return easyocr.Reader([self.language], gpu=False)
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Failed to initialize EasyOCR reader: %s", exc)
            return None

    @staticmethod
    def _ensure_image(image_or_path: ImageInput) -> np.ndarray:
        if isinstance(image_or_path, np.ndarray):
            return image_or_path

        image = cv2.imread(str(image_or_path))
        if image is None:
            raise ValueError(f"Could not read image: {image_or_path}")
        return image

    @staticmethod
    def _estimate_confidence(text: str) -> float:
        if not text:
            return 0.0
        chars = len(text.strip())
        if chars == 0:
            return 0.0
        alpha_num = sum(ch.isalnum() for ch in text)
        ratio = alpha_num / max(chars, 1)
        confidence = min(100.0, (chars / 8.0) * ratio)
        return round(confidence, 2)

    def extract_text_tesseract(self, image_or_path: ImageInput) -> str:
        if pytesseract is None:
            raise RuntimeError("pytesseract is not installed.")

        image = self._ensure_image(image_or_path)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return pytesseract.image_to_string(rgb)

    def extract_text_easyocr(self, image_or_path: ImageInput) -> str:
        if self.easyocr_reader is None:
            raise RuntimeError("EasyOCR reader is not available.")

        image = self._ensure_image(image_or_path)
        results = self.easyocr_reader.readtext(image, detail=0)
        return " ".join(results)

    def extract_text(self, file_path: Union[str, Path]) -> str:
        file_path = Path(file_path)
        if file_path.suffix.lower() == ".pdf":
            return self.extract_from_pdf(str(file_path)).get("text", "")

        if self.prefer_easyocr and self.easyocr_reader is not None:
            try:
                return self.extract_text_easyocr(file_path)
            except Exception as exc:
                logger.warning("EasyOCR failed for %s: %s", file_path, exc)

        try:
            return self.extract_text_tesseract(file_path)
        except Exception as exc:
            logger.warning("Tesseract OCR failed for %s: %s", file_path, exc)
            return ""

    def extract_structured_data(self, file_path: str, document_type: str) -> Dict[str, Any]:
        text = self.extract_text(file_path)
        structured = self.extractor.extract(text, document_type=document_type)
        confidence = max(
            float(structured.get("confidence", 0.0)),
            self._estimate_confidence(text),
        )

        return {
            "text": text,
            "document_type": document_type,
            "confidence": round(confidence, 2),
            "entities": structured.get("entities", {}),
            "fields": structured.get("fields", {}),
            "dates": structured.get("dates", []),
            "structured_data": structured,
        }

    def _extract_pdf_text_native(self, file_path: Path) -> str:
        if PdfReader is None:
            return ""
        try:
            reader = PdfReader(str(file_path))
            pages = reader.pages[: self.max_pdf_pages]
            text_chunks = [(page.extract_text() or "") for page in pages]
            return "\n".join(chunk for chunk in text_chunks if chunk)
        except Exception as exc:
            logger.warning("Native PDF text extraction failed for %s: %s", file_path, exc)
            return ""

    def _extract_pdf_text_via_ocr(self, file_path: Path) -> str:
        if convert_from_path is None or pytesseract is None:
            return ""

        try:
            images = convert_from_path(
                str(file_path),
                first_page=1,
                last_page=self.max_pdf_pages,
                **pdf2image_kwargs(),
            )
        except Exception as exc:
            logger.warning("PDF rasterization failed for %s: %s", file_path, exc)
            return ""

        chunks = []
        for image in images:
            np_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            try:
                chunks.append(self.extract_text_tesseract(np_img))
            except Exception as exc:
                logger.warning("OCR failed for a PDF page in %s: %s", file_path, exc)
        return "\n".join(chunk for chunk in chunks if chunk)

    def extract_from_pdf(self, file_path: str) -> Dict[str, Any]:
        pdf_path = Path(file_path)
        native_text = self._extract_pdf_text_native(pdf_path)
        ocr_text = self._extract_pdf_text_via_ocr(pdf_path) if len(native_text.strip()) < 20 else ""

        text = native_text if len(native_text.strip()) >= len(ocr_text.strip()) else ocr_text
        structured = self.extractor.extract(text, document_type="unknown")
        confidence = max(
            float(structured.get("confidence", 0.0)),
            self._estimate_confidence(text),
        )

        return {
            "text": text,
            "document_type": "unknown",
            "confidence": round(confidence, 2),
            "entities": structured.get("entities", {}),
            "fields": structured.get("fields", {}),
            "dates": structured.get("dates", []),
            "structured_data": structured,
        }
