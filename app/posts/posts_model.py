from typing import Optional, Dict, List
from datetime import datetime

class PostsModel:
    """인메모리 JSON 저장소를 사용한 Posts 모델"""

    # 인메모리 데이터 저장소
    _posts: Dict[int, dict] = {}
    _post_id_counter: int = 1
    _file_id_counter: int = 1

    #게시글 생성, 자동으로 postId와 fileId 할당
    @classmethod
    def create_post(cls, user_id: int, title: str, content: str, file_url: str = "") -> dict:
        post_id = cls._post_id_counter
        cls._post_id_counter += 1

        file_info = None
        if file_url:
            file_id = cls._file_id_counter
            cls._file_id_counter += 1
            file_info = {
                "fileId": file_id,
                "fileUrl": file_url
            }

        post = {
            "postId": post_id,
            "title": title,
            "content": content,
            "hits": 0,
            "likeCount": 0,
            "commentCount": 0,
            "authorId": user_id,
            "file": file_info,
            "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        cls._posts[post_id] = post
        return post

    #게시글 조회
    @classmethod
    def find_post_by_id(cls, post_id: int) -> Optional[dict]:
        return cls._posts.get(post_id)

    #페이징을 지원하는 목록 조회
    @classmethod
    def get_all_posts(cls, page: int = 1, size: int = 20) -> List[dict]:
        all_posts = sorted(cls._posts.values(), key=lambda x: x["postId"], reverse=True)

        start_idx = (page - 1) * size
        end_idx = start_idx + size

        return all_posts[start_idx:end_idx]

    #게시글 수정
    @classmethod
    def update_post(cls, post_id: int, title: Optional[str] = None,
                    content: Optional[str] = None, file_url: Optional[str] = None) -> bool:
        post = cls._posts.get(post_id)
        if not post:
            return False

        if title is not None:
            post["title"] = title
        if content is not None:
            post["content"] = content
        if file_url is not None:
            if file_url:
                if post["file"]:
                    post["file"]["fileUrl"] = file_url
                else:
                    file_id = cls._file_id_counter
                    cls._file_id_counter += 1
                    post["file"] = {
                        "fileId": file_id,
                        "fileUrl": file_url
                    }
            else:
                post["file"] = None

        return True

    #게시글 삭제
    @classmethod
    def delete_post(cls, post_id: int) -> bool:
        if post_id in cls._posts:
            del cls._posts[post_id]
            return True
        return False

    #조회수 증가
    @classmethod
    def increment_hits(cls, post_id: int) -> bool:
        post = cls._posts.get(post_id)
        if post:
            post["hits"] += 1
            return True
        return False

    #좋아요 수 증가
    @classmethod
    def increment_like_count(cls, post_id: int) -> bool:
        post = cls._posts.get(post_id)
        if post:
            post["likeCount"] += 1
            return True
        return False

    #좋아요수 감소
    @classmethod
    def decrement_like_count(cls, post_id: int) -> bool:
        post = cls._posts.get(post_id)
        if post:
            post["likeCount"] = max(0, post["likeCount"] - 1)
            return True
        return False

    #댓글수 증가
    @classmethod
    def increment_comment_count(cls, post_id: int) -> bool:
        post = cls._posts.get(post_id)
        if post:
            post["commentCount"] += 1
            return True
        return False

    #댓글수 감소
    @classmethod
    def decrement_comment_count(cls, post_id: int) -> bool:
        post = cls._posts.get(post_id)
        if post:
            post["commentCount"] = max(0, post["commentCount"] - 1)
            return True
        return False

    #게시글 작성자 ID 조회
    @classmethod
    def get_post_author_id(cls, post_id: int) -> Optional[int]:
        post = cls._posts.get(post_id)
        return post["authorId"] if post else None

    #모든 데이터 초기화(테스트용)
    @classmethod
    def clear_all_data(cls):
        cls._posts.clear()
        cls._post_id_counter = 1
        cls._file_id_counter = 1