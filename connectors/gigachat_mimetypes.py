"""
MIME-type mapping для GigaChat API
"""
GIGACHAT_SUPPORTED_MIMETYPES = {
    # Documents
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    
    # Archives
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".7z": "application/x-7z-compressed",
    ".rar": "application/x-rar-compressed",
    
    # Images
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    
    # Audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    
    # Video
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    
    # Code/Markup
    ".py": "text/plain",
    ".java": "text/plain",
    ".cpp": "text/plain",
    ".c": "text/plain",
    ".go": "text/plain",
    ".rs": "text/plain",
    ".js": "text/plain",
    ".ts": "text/plain",
    ".json": "application/json",
    ".xml": "application/xml",
    ".html": "text/html",
    ".css": "text/css",
    ".sql": "text/plain",
    ".sh": "text/plain",
    ".yaml": "text/plain",
    ".yml": "text/plain",
    ".toml": "text/plain",
    ".ini": "text/plain",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
}

def get_mimetype_for_file(filename: str) -> str:
    """
    Определить MIME-type файла по расширению.
    
    Args:
        filename: Имя файла с расширением
        
    Returns:
        MIME-type строка
    """
    import os
    ext = os.path.splitext(filename)[1].lower()
    return GIGACHAT_SUPPORTED_MIMETYPES.get(ext, "text/plain")  # Default to text/plain
