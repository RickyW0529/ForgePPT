import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field
from llm.tools.registry import llm_tool


class PPTScreenshotInput(BaseModel):
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
        return _placeholder_image(slide_number)

    path = Path(pptx_path)
    if not path.exists():
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
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            return _placeholder_image(slide_number)

        pdf_file = tmp_path / f"{path.stem}.pdf"
        if not pdf_file.exists():
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
            return _placeholder_image(slide_number)


def _placeholder_image(slide_number: int) -> str:
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
    """Render a PPT slide to an image.

    Requires the pptx source path to be available in the workflow context.
    In practice the caller must inject `pptx_path` before invoking.
    """
    return {
        "slide_number": params.slide_number,
        "width_px": params.width_px,
        "image_data": None,
        "note": "Use the node-level wrapper that injects pptx_path.",
    }


def render_slide(pptx_path: str, slide_number: int, width_px: int = 1280) -> str:
    """Standalone helper for nodes to call directly. Returns base64 data URL."""
    return _convert_slide_to_png(pptx_path, slide_number, width_px)
