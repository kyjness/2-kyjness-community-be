# app/comments/comments_controller.py
from fastapi import HTTPException
from app.comments.comments_model import CommentsModel
from app.posts.posts_model import PostsModel
from app.auth.auth_model import AuthModel

"""댓글 관련 비즈니스 로직 처리 (함수형 컨트롤러)."""


# 헬퍼 함수: 반복되는 코드 제거
def _raise_error(status_code: int, error_code: str) -> None:
    """에러 응답 생성 헬퍼 함수."""
    raise HTTPException(status_code=status_code, detail={"code": error_code, "data": None})


def _success_response(code: str, data=None):
    """성공 응답 생성 헬퍼 함수."""
    return {"code": code, "data": data}


def create_comment(post_id: int, user_id: int, content: str):
    """댓글 작성 처리."""
    # 게시글 존재 확인
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 댓글 생성
    comment = CommentsModel.create_comment(post_id, user_id, content)

    # 게시글의 댓글 수 증가
    PostsModel.increment_comment_count(post_id)

    return _success_response("COMMENT_UPLOADED", {"commentId": comment["commentId"]})


def get_comments(post_id: int, page: int = 1, size: int = 20):
    """댓글 목록 조회 처리."""
    # 게시글 존재 확인
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # Query parameter는 Route에서 이미 ge=1로 검증됨
    comments = CommentsModel.get_comments_by_post_id(post_id, page, size)

    # 작성자 정보 추가
    result = []
    for comment in comments:
        author = AuthModel.find_user_by_id(comment["authorId"])
        if author:
            result.append(
                {
                    "commentId": comment["commentId"],
                    "content": comment["content"],
                    "postId": post_id,
                    "author": {
                        "userId": author["userId"],
                        "nickname": author["nickname"],
                        "profileImageUrl": author.get("profileImageUrl", author.get("profileImage", "")),
                    },
                    "createdAt": comment["createdAt"],
                }
            )

    return _success_response("COMMENTS_RETRIEVED", result)


def update_comment(post_id: int, comment_id: int, user_id: int, content: str):
    """댓글 수정 처리."""
    # 게시글 존재 확인
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 댓글 존재 확인
    comment = CommentsModel.find_comment_by_id(comment_id)
    if not comment:
        _raise_error(404, "COMMENT_NOT_FOUND")

    # 댓글이 해당 게시글에 속하는지 확인
    if comment["postId"] != post_id:
        _raise_error(400, "INVALID_POSTID_FORMAT")

    # 작성자 확인
    if comment["authorId"] != user_id:
        _raise_error(403, "FORBIDDEN")

    # 댓글 수정
    CommentsModel.update_comment(comment_id, content)

    return _success_response("COMMENT_UPDATED")


def delete_comment(post_id: int, comment_id: int, user_id: int):
    """댓글 삭제 처리."""
    # 게시글 존재 확인
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 댓글 존재 확인
    comment = CommentsModel.find_comment_by_id(comment_id)
    if not comment:
        _raise_error(404, "COMMENT_NOT_FOUND")

    # 댓글이 해당 게시글에 속하는지 확인
    if comment["postId"] != post_id:
        _raise_error(400, "INVALID_POSTID_FORMAT")

    # 작성자 확인
    if comment["authorId"] != user_id:
        _raise_error(403, "FORBIDDEN")

    # 댓글 삭제
    CommentsModel.delete_comment(comment_id)

    # 게시글의 댓글 수 감소
    PostsModel.decrement_comment_count(post_id)

    return None
