"""
Enhanced OCR processor with swappable engines and page-level tracking.
Implements P1 requirements: Tesseract/EasyOCR support, confidence scoring, page metadata.

Merged from SIH back-end (Phase 1):
  - Full OpenCV preprocessing pipeline (300-DPI upscale, Otsu binarisation, deskew,
    morphological noise removal, SHARPEN)
  - PSM-6 Tesseract flag for structured documents / forms
  - Same pipeline applied to EasyOCREngine for consistency
  - Graceful fallback to basic PIL preprocessing when OpenCV is unavailable
"""

import os
import logging
from typing import List, Tuple, Dict, Any, Optional
from abc import ABC, abstractmethod
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class OCREngine(ABC):
    """Abstract base class for OCR engines — swappable implementation."""

    @abstractmethod
    def extract_text(self, image: Image.Image) -> Tuple[str, float]:
        """
        Extract text from an image.

        Returns:
            Tuple of (extracted_text, confidence_score 0-1)
        """
        pass

    @abstractmethod
    def extract_text_with_boxes(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        Extract text with bounding boxes and word-level confidence.

        Returns:
            List of dicts: {text, confidence, bbox: (x, y, w, h)}
        """
        pass


# ---------------------------------------------------------------------------
# Shared preprocessing mixin
# ---------------------------------------------------------------------------

class _PreprocessMixin:
    """
    OpenCV-based image preprocessing shared by Tesseract and EasyOCR.

    Pipeline:
      1. Resolution upscaling to ≥1500px width (≈300 DPI equivalent)
      2. Grayscale conversion
      3. Gaussian blur for noise reduction
      4. Otsu's binarisation (handles varying lighting automatically)
      5. Deskewing via minAreaRect
      6. Morphological close to remove residual noise
      7. PIL SHARPEN as final touch

    Falls back to basic PIL contrast+sharpen if OpenCV is not installed.
    """

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        try:
            from PIL import ImageFilter
            import cv2
            import numpy as np

            img_array = np.array(image)

            # 1. Resolution upscaling
            if len(img_array.shape) == 2:
                height, width = img_array.shape
            else:
                height, width = img_array.shape[0], img_array.shape[1]

            if width < 1000:
                scale_factor = 1500 / width
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                img_array = cv2.resize(
                    img_array, (new_width, new_height), interpolation=cv2.INTER_CUBIC
                )
                logger.debug(
                    f"Upscaled image from {width}x{height} to {new_width}x{new_height}"
                )

            # 2. Grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # 3. Gaussian denoise
            denoised = cv2.GaussianBlur(gray, (5, 5), 0)

            # 4. Otsu binarisation
            _, binary = cv2.threshold(
                denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            # 5. Deskew
            coords = np.column_stack(np.where(binary > 0))
            if len(coords) > 0:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = 90 + angle
                elif angle > 45:
                    angle = angle - 90
                if abs(angle) > 0.5:
                    (h, w) = binary.shape[:2]
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, angle, 1.0)
                    binary = cv2.warpAffine(
                        binary, M, (w, h),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
                    logger.debug(f"Deskewed image by {angle:.2f} degrees")

            # 6. Morphological close
            kernel = np.ones((2, 2), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

            # 7. PIL sharpen
            image = Image.fromarray(binary)
            image = image.filter(ImageFilter.SHARPEN)

            logger.debug(
                "Enhanced preprocessing completed: upscale + Otsu + deskew + denoise"
            )
            return image

        except Exception as e:
            logger.warning(
                f"Enhanced preprocessing failed ({e}), using basic preprocessing"
            )
            try:
                from PIL import ImageEnhance, ImageFilter

                if image.mode != "L":
                    image = image.convert("L")
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(2.0)
                image = image.filter(ImageFilter.SHARPEN)
                return image
            except Exception:
                logger.error("All preprocessing failed — using original image")
                return image


# ---------------------------------------------------------------------------
# Tesseract
# ---------------------------------------------------------------------------

class TesseractOCR(_PreprocessMixin, OCREngine):
    """Tesseract OCR engine with enhanced OpenCV preprocessing."""

    def __init__(
        self,
        language: str = "eng",
        tesseract_cmd: Optional[str] = None,
    ):
        try:
            import pytesseract

            self.pytesseract = pytesseract
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            self.language = language
            logger.info(f"Initialized TesseractOCR (language={language})")
        except ImportError:
            raise ImportError(
                "pytesseract not installed. Run: pip install pytesseract"
            )

    def extract_text(self, image: Image.Image) -> Tuple[str, float]:
        """
        Extract text with average confidence (0-1 normalised).

        Reconstructs line and paragraph breaks from Tesseract's word-level
        layout data (block/par/line numbers) instead of flattening the whole
        page into a single space-joined string. This matters a great deal
        for downstream regex-based field extraction (titles, "Label: Value"
        lines, etc.), which relies on real line boundaries.
        """
        try:
            image = self._preprocess_image(image)
            # PSM 6 — assume single uniform block of text (ideal for forms/documents)
            data = self.pytesseract.image_to_data(
                image,
                lang=self.language,
                config="--psm 6",
                output_type=self.pytesseract.Output.DICT,
            )

            confidences = []
            lines: Dict[Tuple[int, int, int], List[str]] = {}
            line_order: List[Tuple[int, int, int]] = []

            n = len(data["text"])
            for i in range(n):
                conf = data["conf"][i]
                if conf <= 0:
                    continue
                word = data["text"][i].strip()
                if not word:
                    continue
                confidences.append(conf)

                line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                if line_key not in lines:
                    lines[line_key] = []
                    line_order.append(line_key)
                lines[line_key].append(word)

            # Rebuild text with real line/paragraph breaks so downstream
            # regex extraction (titles, "Label: Value" lines) can work on
            # OCR'd images the same way it works on native PDF/DOCX text.
            text_lines = []
            last_par_key = None
            for line_key in line_order:
                par_key = (line_key[0], line_key[1])
                if last_par_key is not None and par_key != last_par_key:
                    text_lines.append("")  # blank line between paragraphs
                text_lines.append(" ".join(lines[line_key]))
                last_par_key = par_key

            full_text = "\n".join(text_lines)
            avg_confidence = (
                sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            )
            return full_text, avg_confidence

        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return "", 0.0

    def extract_text_with_boxes(self, image: Image.Image) -> List[Dict[str, Any]]:
        """Extract text with bounding boxes."""
        try:
            data = self.pytesseract.image_to_data(
                image,
                lang=self.language,
                output_type=self.pytesseract.Output.DICT,
            )
            results = []
            for i in range(len(data["text"])):
                conf = data["conf"][i]
                if conf > 0:
                    text = data["text"][i].strip()
                    if text:
                        results.append(
                            {
                                "text": text,
                                "confidence": conf / 100.0,
                                "bbox": (
                                    data["left"][i],
                                    data["top"][i],
                                    data["width"][i],
                                    data["height"][i],
                                ),
                            }
                        )
            return results
        except Exception as e:
            logger.error(f"Tesseract box extraction failed: {e}")
            return []


# ---------------------------------------------------------------------------
# EasyOCR
# ---------------------------------------------------------------------------

class EasyOCREngine(_PreprocessMixin, OCREngine):
    """EasyOCR engine with the same enhanced OpenCV preprocessing pipeline."""

    def __init__(self, languages: List[str] = None, gpu: bool = False):
        try:
            import easyocr

            self.languages = languages or ["en"]
            self.gpu = gpu
            logger.info(f"Initializing EasyOCR (languages={self.languages})")
            self.reader = easyocr.Reader(self.languages, gpu=self.gpu)
            logger.info("EasyOCR initialized successfully")
        except ImportError:
            raise ImportError("easyocr not installed. Run: pip install easyocr")

    def extract_text(self, image: Image.Image) -> Tuple[str, float]:
        try:
            image = self._preprocess_image(image)
            image_np = np.array(image)
            results = self.reader.readtext(image_np)
            if not results:
                return "", 0.0

            # Reconstruct line breaks from bbox vertical position, since
            # EasyOCR returns flat (bbox, text, confidence) tuples with no
            # inherent line grouping. Sort top-to-bottom then left-to-right,
            # and start a new line whenever the vertical gap between
            # consecutive words is larger than roughly half a text height.
            items = []
            for bbox, text, conf in results:
                y_coords = [p[1] for p in bbox]
                x_coords = [p[0] for p in bbox]
                items.append({
                    "text": text,
                    "conf": conf,
                    "top": min(y_coords),
                    "left": min(x_coords),
                    "height": max(y_coords) - min(y_coords),
                })
            items.sort(key=lambda it: (it["top"], it["left"]))

            lines = []
            current_line = [items[0]]
            for it in items[1:]:
                prev = current_line[-1]
                threshold = max(prev["height"], it["height"]) * 0.6 or 10
                if abs(it["top"] - prev["top"]) > threshold:
                    lines.append(current_line)
                    current_line = [it]
                else:
                    current_line.append(it)
            lines.append(current_line)

            text_lines = []
            confidences = []
            for line in lines:
                line.sort(key=lambda it: it["left"])
                text_lines.append(" ".join(it["text"] for it in line))
                confidences.extend(it["conf"] for it in line)

            full_text = "\n".join(text_lines)
            avg_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.0
            )
            return full_text, avg_confidence
        except Exception as e:
            logger.error(f"EasyOCR failed: {e}")
            return "", 0.0

    def extract_text_with_boxes(self, image: Image.Image) -> List[Dict[str, Any]]:
        try:
            image_np = np.array(image)
            results = self.reader.readtext(image_np)
            extracted = []
            for bbox, text, conf in results:
                x_coords = [point[0] for point in bbox]
                y_coords = [point[1] for point in bbox]
                x = min(x_coords)
                y = min(y_coords)
                w = max(x_coords) - x
                h = max(y_coords) - y
                extracted.append(
                    {"text": text, "confidence": conf, "bbox": (x, y, w, h)}
                )
            return extracted
        except Exception as e:
            logger.error(f"EasyOCR box extraction failed: {e}")
            return []


# ---------------------------------------------------------------------------
# OCRProcessor
# ---------------------------------------------------------------------------

class OCRProcessor:
    """
    Main OCR processor with swappable engines.
    Implements P1 requirement: modular OCR with page tracking.
    """

    def __init__(self, engine: Optional[OCREngine] = None):
        if engine is None:
            # Wire the configured Tesseract binary path / language through --
            # without this, TESSERACT_CMD in the environment/.env is silently
            # ignored and OCR only works if tesseract happens to be on PATH.
            tesseract_cmd = None
            language = "eng"
            try:
                from core.config import settings
                tesseract_cmd = settings.tesseract_cmd
                language = settings.ocr_language or "eng"
            except Exception:
                pass  # core.config unavailable (e.g. standalone script usage) -- use defaults

            try:
                self.engine = TesseractOCR(language=language, tesseract_cmd=tesseract_cmd)
            except ImportError:
                logger.warning("Tesseract not available — falling back to EasyOCR")
                self.engine = EasyOCREngine()
        else:
            self.engine = engine

        self._fallback: Optional[OCREngine] = None
        self._fallback_initialized = False

    def _fallback_engine(self) -> Optional[OCREngine]:
        """Lazily build a secondary engine to retry with if the primary
        engine fails or returns unusably little text (e.g. Tesseract
        binary missing/misconfigured, or a low-quality scan)."""
        if not self._fallback_initialized:
            self._fallback_initialized = True
            try:
                if isinstance(self.engine, TesseractOCR):
                    self._fallback = EasyOCREngine()
                elif isinstance(self.engine, EasyOCREngine):
                    self._fallback = TesseractOCR()
            except Exception as e:
                logger.debug(f"No fallback OCR engine available: {e}")
                self._fallback = None
        return self._fallback

    def extract_from_image(
        self, image: Image.Image, page_number: int = 1
    ) -> Dict[str, Any]:
        """Extract text from a single image with metadata.

        Automatically retries with a secondary OCR engine when the primary
        engine returns empty text or very low confidence, so a missing/
        misconfigured Tesseract install (or a hard-to-read scan) doesn't
        silently produce a blank result.
        """
        text, confidence = self.engine.extract_text(image)

        if not text.strip() or confidence < 0.35:
            fallback = self._fallback_engine()
            if fallback is not None:
                logger.info(
                    f"Primary OCR engine produced weak result (confidence={confidence:.2f}); "
                    f"retrying with {type(fallback).__name__}"
                )
                fb_text, fb_confidence = fallback.extract_text(image)
                if fb_text.strip() and (not text.strip() or fb_confidence > confidence):
                    text, confidence = fb_text, fb_confidence

        return {
            "text": text,
            "confidence": confidence,
            "page_number": page_number,
            "word_count": len(text.split()),
            "char_count": len(text),
        }

    def extract_from_images(
        self, images: List[Image.Image]
    ) -> List[Dict[str, Any]]:
        """Extract text from multiple images (pages)."""
        results = []
        for page_num, image in enumerate(images, start=1):
            logger.info(f"Processing page {page_num}/{len(images)}")
            results.append(self.extract_from_image(image, page_number=page_num))
        return results

    def extract_with_boxes(
        self, image: Image.Image, page_number: int = 1
    ) -> Dict[str, Any]:
        """Extract text with bounding boxes for detailed analysis."""
        boxes = self.engine.extract_text_with_boxes(image)
        full_text = " ".join([b["text"] for b in boxes])
        avg_confidence = (
            sum(b["confidence"] for b in boxes) / len(boxes) if boxes else 0.0
        )
        return {
            "text": full_text,
            "confidence": avg_confidence,
            "page_number": page_number,
            "boxes": boxes,
            "box_count": len(boxes),
        }


# ---------------------------------------------------------------------------
# Public helpers (backward-compatible)
# ---------------------------------------------------------------------------

def extract_text_from_image(image: Image.Image) -> Tuple[str, float]:
    """
    Legacy helper — backward-compatible entry point.

    Args:
        image: PIL Image object

    Returns:
        Tuple of (text, confidence 0-1)
    """
    processor = OCRProcessor()
    result = processor.extract_from_image(image)
    return result["text"], result["confidence"]


def create_ocr_processor(engine_type: str = "tesseract", **kwargs) -> OCRProcessor:
    """
    Factory function to create an OCRProcessor with the specified engine.

    Args:
        engine_type: 'tesseract' or 'easyocr'
        **kwargs: Engine-specific keyword arguments

    Returns:
        Configured OCRProcessor
    """
    if engine_type.lower() == "tesseract":
        engine = TesseractOCR(**kwargs)
    elif engine_type.lower() == "easyocr":
        engine = EasyOCREngine(**kwargs)
    else:
        raise ValueError(f"Unknown OCR engine type: {engine_type}")
    return OCRProcessor(engine=engine)
