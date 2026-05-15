import base64
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field
from llm.tools.registry import llm_tool

logger = logging.getLogger(__name__)


class PPTScreenshotInput(BaseModel):
    pptx_path: str = Field(..., description="Path to the .pptx file")
    slide_number: int = Field(..., ge=1, description="1-based slide number to capture")
    width_px: int = Field(1280, ge=640, le=3840, description="Output image width in pixels")


def _libreoffice_available() -> bool:
    return shutil.which("soffice") is not None or shutil.which("libreoffice") is not None


def _soffice_cmd() -> str:
    if shutil.which("soffice"):
        return "soffice"
    if shutil.which("libreoffice"):
        return "libreoffice"
    raise RuntimeError("LibreOffice not found")


def _convert_slide_to_png(pptx_path: str, slide_number: int, width_px: int) -> str:
    """Convert a single PPT slide to PNG and return base64 data URL.

    Uses LibreOffice headless to export the PPTX to PDF, then pdf2image
    to render the requested slide as PNG. Falls back to a placeholder
    if dependencies are missing.
    """
    if not _libreoffice_available():
        logger.warning("LibreOffice not available; returning placeholder image")
        return _placeholder_image(slide_number)

    path = Path(pptx_path)
    if not path.exists():
        logger.warning("PPTX file not found: %s", pptx_path)
        raise FileNotFoundError(f"PPTX not found: {pptx_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cmd = [
            _soffice_cmd(),
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(tmp_path),
            str(path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        except subprocess.CalledProcessError as e:
            logger.warning("LibreOffice conversion failed: %s", e)
            return _placeholder_image(slide_number)
        except subprocess.TimeoutExpired as e:
            logger.warning("LibreOffice conversion timed out: %s", e)
            return _placeholder_image(slide_number)

        pdf_file = tmp_path / f"{path.stem}.pdf"
        if not pdf_file.exists():
            logger.warning("PDF output not found after LibreOffice conversion")
            return _placeholder_image(slide_number)

        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(str(pdf_file), dpi=width_px // 10)
            if slide_number > len(pages):
                raise ValueError(f"Slide {slide_number} exceeds total {len(pages)}")
            img = pages[slide_number - 1]
            png_path = tmp_path / "slide.png"
            img.save(str(png_path), "PNG")
            b64 = base64.b64encode(png_path.read_bytes()).decode()
            return f"data:image/png;base64,{b64}"
        except ImportError:
            logger.warning("pdf2image not installed; returning placeholder image")
            return _placeholder_image(slide_number)


def _placeholder_image(_slide_number: int) -> str:
    """Return a transparent 1x1 PNG as a fallback when rendering is unavailable."""
    minimal_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\xfc\xcf\xc0\x50\x0f\x00\x04A\x01\xa1\x3a\xf0\xfc\xcc\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    b64 = base64.b64encode(minimal_png).decode()
    return f"data:image/png;base64,{b64}"


@llm_tool(
    name="ppt_screenshot",
    roles=["editor"],
    description=(
        "Capture a screenshot of a specific slide in the uploaded PPT "
        "and return it as a base64 PNG image. Useful for visual analysis."
    ),
)
def ppt_screenshot_tool(params: PPTScreenshotInput) -> dict:
    try:
        image_data = render_slide(params.pptx_path, params.slide_number, params.width_px)
        is_placeholder = image_data == _placeholder_image(params.slide_number)
        return {
            "slide_number": params.slide_number,
            "width_px": params.width_px,
            "image_data": image_data,
            "is_placeholder": is_placeholder,
        }
    except Exception as e:
        logger.warning("ppt_screenshot_tool failed for %s slide %s: %s", params.pptx_path, params.slide_number, e)
        return {
            "slide_number": params.slide_number,
            "width_px": params.width_px,
            "image_data": _placeholder_image(params.slide_number),
            "is_placeholder": True,
            "error": str(e),
        }


def render_slide(pptx_path: str, slide_number: int, width_px: int = 1280) -> str:
    """Standalone helper for nodes to call directly. Returns base64 data URL."""
    return _convert_slide_to_png(pptx_path, slide_number, width_px)
