# app/likes/likes_controller.py
from fastapi import HTTPException
from app.likes.likes_model import LikesModel
from app.posts.posts_model import PostsModel

"""좋아요 관련 비즈니스 로직 처리 (함수형 컨트롤러)."""


# 헬퍼 함수: 반복되는 코드 제거
def _raise_error(status_code: int, error_code: str) -> None:
    """에러 응답 생성 헬퍼 함수."""
    raise HTTPException(status_code=status_code, detail={"code": error_code, "data": None})


def _success_response(code: str, data=None):
    """성공 응답 생성 헬퍼 함수."""
    return {"code": code, "data": data}


def create_like(post_id: int, user_id: int):
    """좋아요 추가 처리."""
    # 게시글 존재 확인
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 중복 좋아요 체크
    if LikesModel.has_liked(post_id, user_id):
        _raise_error(400, "ALREADY_LIKED")

    # 좋아요 생성
    like = LikesModel.create_like(post_id, user_id)
    if not like:
        _raise_error(400, "ALREADY_LIKED")

    # 게시글의 좋아요 수 증가
    PostsModel.increment_like_count(post_id)

    # 업데이트된 좋아요 수 조회
    updated_post = PostsModel.find_post_by_id(post_id)
    like_count = updated_post["likeCount"] if updated_post else 0

    return _success_response("POSTLIKE_UPLOADED", {"likeCount": like_count})


def delete_like(post_id: int, user_id: int):
    """좋아요 취소 처리."""
    # 게시글 존재 확인
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 좋아요 존재 확인
    if not LikesModel.has_liked(post_id, user_id):
        _raise_error(404, "LIKE_NOT_FOUND")

    # 좋아요 삭제
    LikesModel.delete_like(post_id, user_id)

    # 게시글의 좋아요 수 감소
    PostsModel.decrement_like_count(post_id)

    return None
