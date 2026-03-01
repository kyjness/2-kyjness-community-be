# PuppyTalk API 패키지. api, common, core, db / 도메인: auth, users, posts, comments, media.

import sys

from .domain import auth, users, posts, comments, media

sys.modules["app.auth"] = auth
sys.modules["app.users"] = users
sys.modules["app.posts"] = posts
sys.modules["app.comments"] = comments
sys.modules["app.media"] = media
