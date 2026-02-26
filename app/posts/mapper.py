from app.posts.schema import AuthorInfo, FileInfo, PostResponse


def to_post_response(post) -> PostResponse:
    author = AuthorInfo.model_validate(post.user)
    files = [
        FileInfo(id=pi.id, file_url=pi.image.file_url if pi.image else None, image_id=pi.image_id)
        for pi in (post.post_images or [])
    ]
    return PostResponse(
        id=post.id,
        title=post.title,
        content=post.content,
        view_count=post.view_count or 0,
        like_count=post.like_count or 0,
        comment_count=post.comment_count or 0,
        author=author,
        files=files,
        created_at=post.created_at,
    )
