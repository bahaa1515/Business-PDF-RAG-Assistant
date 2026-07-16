"""Safe upload handling for business document formats."""
import os
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import List


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm", ".csv", ".xlsx"}
ZIP_EXTENSION = ".zip"
UPLOAD_EXTENSIONS = ALLOWED_EXTENSIONS | {ZIP_EXTENSION}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
MAX_ZIP_SIZE_BYTES = 100 * 1024 * 1024
MAX_ZIP_ENTRIES = 50
MAX_ZIP_EXTRACTED_BYTES = 150 * 1024 * 1024
TEXT_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".csv"}
ZIP_SIGNATURE = b"PK\x03\x04"


@dataclass(frozen=True)
class AcceptedUpload:
    filename: str
    content: bytes


@dataclass(frozen=True)
class RejectedUpload:
    filename: str
    reason: str


def extension_for(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def is_pdf(filename: str) -> bool:
    """Backward-compatible PDF extension check."""
    return extension_for(filename) == ".pdf"


def is_valid_file_size(file_size: int) -> bool:
    return file_size <= MAX_FILE_SIZE_BYTES


def get_upload_path(filename: str) -> str:
    upload_dir = Path(__file__).parent.parent.parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return str(upload_dir / filename)


def normalize_upload_filename(filename: str) -> str:
    safe = Path(filename or "").name.strip()
    if not safe:
        raise ValueError("Filename is required")
    return safe


def validate_document_content(filename: str, file_content: bytes) -> str:
    """Validate allowlisted document content and return its normalized extension."""
    safe_name = normalize_upload_filename(filename)
    extension = extension_for(safe_name)
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension or 'none'}")
    if not is_valid_file_size(len(file_content)):
        raise ValueError(f"File size exceeds {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f}MB limit")
    if extension == ".pdf" and not file_content.lstrip().startswith(b"%PDF-"):
        raise ValueError("Uploaded content is not a valid PDF")
    if extension == ".docx":
        _validate_office_zip(file_content, "word/document.xml", "DOCX")
    elif extension == ".xlsx":
        _validate_office_zip(file_content, "xl/workbook.xml", "XLSX")
    elif extension in TEXT_EXTENSIONS:
        _decode_text(file_content)
    return extension


def save_upload_file(file_content: bytes, filename: str) -> tuple[str, str]:
    """Save an uploaded business document under a UUID filename."""
    safe_name = normalize_upload_filename(filename)
    extension = validate_document_content(safe_name, file_content)
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    file_path = get_upload_path(stored_filename)
    with open(file_path, "wb") as file:
        file.write(file_content)
    return file_path, stored_filename


def expand_upload(filename: str, file_content: bytes) -> tuple[List[AcceptedUpload], List[RejectedUpload]]:
    """Return safe files to store from a direct upload or ZIP archive."""
    safe_name = normalize_upload_filename(filename)
    extension = extension_for(safe_name)
    if extension != ZIP_EXTENSION:
        try:
            validate_document_content(safe_name, file_content)
            return [AcceptedUpload(safe_name, file_content)], []
        except ValueError as exc:
            return [], [RejectedUpload(safe_name, str(exc))]
    return _expand_zip(safe_name, file_content)


def delete_upload_file(file_path: str) -> bool:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as exc:
        print(f"Error deleting file {file_path}: {exc}")
        return False


def _expand_zip(filename: str, file_content: bytes) -> tuple[List[AcceptedUpload], List[RejectedUpload]]:
    if len(file_content) > MAX_ZIP_SIZE_BYTES:
        return [], [RejectedUpload(filename, "ZIP size exceeds 100MB limit")]
    if not file_content.startswith(ZIP_SIGNATURE):
        return [], [RejectedUpload(filename, "Uploaded content is not a valid ZIP archive")]

    accepted: List[AcceptedUpload] = []
    rejected: List[RejectedUpload] = []
    try:
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(file_content)) as archive:
            entries = [info for info in archive.infolist() if not info.is_dir()]
            if len(entries) > MAX_ZIP_ENTRIES:
                return [], [RejectedUpload(filename, f"ZIP contains more than {MAX_ZIP_ENTRIES} files")]
            total_size = sum(info.file_size for info in entries)
            if total_size > MAX_ZIP_EXTRACTED_BYTES:
                return [], [RejectedUpload(filename, "ZIP extracted size exceeds 150MB limit")]
            for info in entries:
                entry_name = info.filename
                unsafe_reason = _unsafe_zip_entry_reason(info)
                if unsafe_reason:
                    rejected.append(RejectedUpload(entry_name, unsafe_reason))
                    continue
                extension = extension_for(entry_name)
                if extension == ZIP_EXTENSION:
                    rejected.append(RejectedUpload(entry_name, "Nested ZIP archives are not allowed"))
                    continue
                if extension not in ALLOWED_EXTENSIONS:
                    rejected.append(RejectedUpload(entry_name, f"Unsupported file type: {extension or 'none'}"))
                    continue
                if info.file_size > MAX_FILE_SIZE_BYTES:
                    rejected.append(RejectedUpload(entry_name, "File size exceeds 50MB limit"))
                    continue
                try:
                    content = archive.read(info)
                    validate_document_content(entry_name, content)
                    accepted.append(AcceptedUpload(PurePosixPath(entry_name).name, content))
                except Exception as exc:
                    rejected.append(RejectedUpload(entry_name, str(exc)))
    except zipfile.BadZipFile:
        return [], [RejectedUpload(filename, "Uploaded content is not a valid ZIP archive")]
    return accepted, rejected


def _unsafe_zip_entry_reason(info: zipfile.ZipInfo) -> str | None:
    name = info.filename.replace("\\", "/")
    parts = PurePosixPath(name).parts
    if not parts or name.startswith("/") or ".." in parts:
        return "Unsafe ZIP path"
    if any(":" in part for part in parts):
        return "Unsafe ZIP path"
    if info.flag_bits & 0x1:
        return "Encrypted ZIP entries are not allowed"
    if any(part.startswith(".") or part == "__MACOSX" for part in parts):
        return "Hidden or system files are not indexed"
    return None


def _validate_office_zip(content: bytes, required_member: str, label: str) -> None:
    from io import BytesIO

    if not content.startswith(ZIP_SIGNATURE):
        raise ValueError(f"Uploaded content is not a valid {label} file")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or required_member not in names:
                raise ValueError(f"Uploaded content is not a valid {label} file")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Uploaded content is not a valid {label} file") from exc


def _decode_text(content: bytes) -> str:
    if b"\x00" in content[:4096]:
        raise ValueError("Uploaded text content appears to be binary")
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            control_chars = [
                char for char in text[:4096]
                if ord(char) < 32 and char not in "\r\n\t"
            ]
            if text and len(control_chars) / max(len(text[:4096]), 1) > 0.05:
                raise ValueError("Uploaded text content appears to be binary")
            return text
        except UnicodeDecodeError:
            continue
    raise ValueError("Uploaded text content could not be decoded")
