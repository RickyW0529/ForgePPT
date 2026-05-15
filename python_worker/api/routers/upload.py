import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from services.parser import parse_pptx

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload")
async def upload_pptx(file: UploadFile = File(...)):
    """Upload and parse a PPTX file.

    Returns the parsed PPTState JSON representation.
    """
    if not file.filename or not file.filename.endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Only .pptx files are supported")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds 50MB limit")

    try:
        upload_dir = Path("/tmp/forgeppt_uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"{file.filename}"
        file_path.write_bytes(contents)

        ppt_state = parse_pptx(file_path)
        # Attach the persistent source file path to PPTState
        ppt_state.source_file = str(file_path)

        return {
            "success": True,
            "data": ppt_state.model_dump(),
            "request_id": file_path.stem,
        }
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Parse error: {e}")
