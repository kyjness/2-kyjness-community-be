# Base.metadata 등록을 위한 모델 로딩 전용 모듈.
# 주의: 프로젝트의 app.__init__ alias 체계와 일관성을 위해 app.<domain>.model 경로를 사용한다.

from app.chat.model import ChatMessage, ChatRoom  # noqa: F401
from app.comments.model import Comment, CommentLike  # noqa: F401
from app.dogs.model import DogProfile  # noqa: F401
from app.likes.model import PostLike  # noqa: F401
from app.media.model import Image  # noqa: F401
from app.notifications.model import Notification  # noqa: F401
from app.posts.model import Category, Hashtag, Post, PostImage  # noqa: F401
from app.reports.model import Report  # noqa: F401
from app.users.model import User, UserBlock  # noqa: F401
