from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Query
from typing import Optional
from pydantic import ValidationError
from app.schemas.posts import PostCreateRequest, PostUpdateRequest
from app.controllers.posts_controller import PostsController
#from app.controllers.auth_controller import AuthController

router = APIRouter(prefix="/posts", tags=["posts"])

# #게시글 작성
# @router.post("")
# async def create_post(
#         request: PostCreateRequest,
#         authorization: Optional[str] = Header(None)
# ):
#     try:
#         # 인증 확인
#         user_id = AuthController.verify_token(authorization)
#
#         return PostsController.create_post(
#             user_id=user_id,
#             title=request.title,
#             content=request.content,
#             file_url=request.fileUrl
#         )
#     except HTTPException:
#         raise
#     except ValidationError as e:
#         error_msg = str(e.errors()[0]["msg"])
#         if "INVALID_TITLE_FORMAT" in error_msg or "title" in str(e).lower():
#             raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
#         elif "INVALID_CONTENT_FORMAT" in error_msg or "content" in str(e).lower():
#             raise HTTPException(status_code=400, detail={"code": "INVALID_CONTENT_FORMAT", "data": None})
#         elif "INVALID_FILEURL" in error_msg:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_FILEURL", "data": None})
#         else:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST_BODY", "data": None})
#     except ValueError as e:
#         error_msg = str(e)
#         if "INVALID_TITLE_FORMAT" in error_msg:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
#         elif "INVALID_CONTENT_FORMAT" in error_msg:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_CONTENT_FORMAT", "data": None})
#         elif "INVALID_FILEURL" in error_msg:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_FILEURL", "data": None})
#         else:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST_BODY", "data": None})
#     except Exception as e:
#         raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})

#게시글 이미지 업로드
@router.post("/{post_id}/image")
async def upload_post_image(
        post_id: int,
        postFile: UploadFile = File(...)
):
    try:
        # post_id 형식 검증
        if post_id < 1:
            raise HTTPException(status_code=400, detail={"code": "INVALID_POSTID_FORMAT", "data": None})

        return await PostsController.upload_post_image(post_id, postFile)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})

#게시글 목록 조회
@router.get("")
async def get_posts(
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1)
):
    try:
        return PostsController.get_posts(page, size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})

#게시글 상세 조회
@router.get("/{post_id}")
async def get_post(post_id: int):
    try:
        # post_id 형식 검증
        if post_id < 1:
            raise HTTPException(status_code=400, detail={"code": "INVALID_POSTID_FORMAT", "data": None})

        return PostsController.get_post(post_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})

#게시글 수정
# @router.patch("/{post_id}")
# async def update_post(
#         post_id: int,
#         request: PostUpdateRequest,
#         authorization: Optional[str] = Header(None)
# ):
#     try:
#         # post_id 형식 검증
#         if post_id < 1:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_POSTID_FORMAT", "data": None})
#
#         # 인증 확인
#         user_id = AuthController.verify_token(authorization)
#
#         return PostsController.update_post(
#             user_id=user_id,
#             post_id=post_id,
#             title=request.title,
#             content=request.content,
#             file_url=request.fileUrl
#         )
#     except HTTPException:
#         raise
#     except ValidationError as e:
#         error_msg = str(e.errors()[0]["msg"])
#         if "INVALID_TITLE_FORMAT" in error_msg or "title" in str(e).lower():
#             raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
#         elif "INVALID_CONTENT_FORMAT" in error_msg or "content" in str(e).lower():
#             raise HTTPException(status_code=400, detail={"code": "INVALID_CONTENT_FORMAT", "data": None})
#         elif "INVALID_FILEURL" in error_msg:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_FILEURL", "data": None})
#         else:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST_BODY", "data": None})
#     except ValueError as e:
#         error_msg = str(e)
#         if "INVALID_TITLE_FORMAT" in error_msg:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
#         elif "INVALID_CONTENT_FORMAT" in error_msg:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_CONTENT_FORMAT", "data": None})
#         elif "INVALID_FILEURL" in error_msg:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_FILEURL", "data": None})
#         else:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST_BODY", "data": None})
#     except Exception as e:
#         raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})

#게시글 삭제
# @router.delete("/{post_id}")
# async def delete_post(
#         post_id: int,
#         authorization: Optional[str] = Header(None)
# ):
#     try:
#         # post_id 형식 검증
#         if post_id < 1:
#             raise HTTPException(status_code=400, detail={"code": "INVALID_POSTID_FORMAT", "data": None})
#
#         # 인증 확인
#         user_id = AuthController.verify_token(authorization)
#
#         return PostsController.delete_post(user_id, post_id)
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})