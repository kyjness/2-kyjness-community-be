# 업로드 요청 선검증. Content-Length로 대용량 요청 조기 거부(DoS 방지).
from fastapi import Request

from app.common.exceptions import PayloadTooLargeException
from app.core.config import settings

# multipart 경계·폼 필드 등 오버헤드. 실제 파일만 MAX_FILE_SIZE 제한.
UPLOAD_BODY_OVERHEAD = 512 * 1024  # 512KB


def check_upload_content_length(request: Request) -> None:
    raw = request.headers.get("content-length")
    if not raw:
        return
    try:
        length = int(raw)
    except ValueError:
        return
    limit = settings.MAX_FILE_SIZE + UPLOAD_BODY_OVERHEAD
    if length > limit:
        raise PayloadTooLargeException(message="요청 본문이 허용 크기를 초과합니다.")
