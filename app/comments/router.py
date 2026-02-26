from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from fastapi.responses import Response

from app.comments.schema import CommentUpsertRequest
from app.comments import controller
from app.core.database import get_db
from app.common import ApiResponse
from app.core.dependencies import CommentAuthorContext, CurrentUser, get_current_user, require_comment_author

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.post("", status_code=201, response_model=ApiResponse)
def create_comment(comment_data: CommentUpsertRequest, post_id: int = Path(..., ge=1, description="게시글 ID"), user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return controller.create_comment(post_id=post_id, user=user, data=comment_data, db=db)


@router.get("", status_code=200, response_model=ApiResponse)
def get_comments(post_id: int = Path(..., ge=1, description="게시글 ID"), page: int = Query(1, ge=1, description="페이지 번호"), size: int = Query(10, ge=1, le=100, description="페이지 크기"), db: Session = Depends(get_db)):
    return controller.get_comments(post_id=post_id, page=page, size=size, db=db)


@router.patch("/{comment_id}", status_code=200, response_model=ApiResponse)
def update_comment(comment_data: CommentUpsertRequest, author_ctx: CommentAuthorContext = Depends(require_comment_author), db: Session = Depends(get_db)):
    return controller.update_comment(post_id=author_ctx.post_id, comment_id=author_ctx.comment_id, data=comment_data, db=db)


@router.delete("/{comment_id}", status_code=204)
def withdraw_comment(author_ctx: CommentAuthorContext = Depends(require_comment_author), db: Session = Depends(get_db)):
    controller.withdraw_comment(post_id=author_ctx.post_id, comment_id=author_ctx.comment_id, db=db)
    return Response(status_code=204)

