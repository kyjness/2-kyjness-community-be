# PuppyTalk API 패키지. api, common, core, db / 도메인: auth, users, posts, comments, media, likes.
# sys.modules 주입: app.admin, app.auth 등은 app.domain.*를 가리키도록 함 (import 호환용).

import sys

from .domain import admin, auth, comments, dogs, likes, media, posts, reports, users

sys.modules["app.auth"] = auth
sys.modules["app.users"] = users
sys.modules["app.posts"] = posts
sys.modules["app.comments"] = comments
sys.modules["app.media"] = media
sys.modules["app.likes"] = likes
sys.modules["app.dogs"] = dogs
sys.modules["app.reports"] = reports
sys.modules["app.admin"] = admin
