import pytest
from app.common.exceptions import InvalidRequestException
from app.domain.posts.repository import (
    PostsModel,
    tokenize_search_query,
    validate_search_query,
)


def test_tokenize_search_query_splits_whitespace():
    assert tokenize_search_query("불닭  레시피") == ["불닭", "레시피"]


def test_validate_search_query_rejects_short_token():
    with pytest.raises(InvalidRequestException):
        validate_search_query("불")
    with pytest.raises(InvalidRequestException):
        validate_search_query("ab")
    with pytest.raises(InvalidRequestException):
        validate_search_query("1")
    assert validate_search_query("불닭") == "불닭"
    assert validate_search_query("abc") == "abc"
    assert validate_search_query("12") == "12"
    assert validate_search_query("2024") == "2024"


def test_validate_search_query_hashtag_bypasses_min_len():
    assert validate_search_query("#ab") == "#ab"


def test_validate_search_query_empty_returns_none():
    assert validate_search_query(None) is None
    assert validate_search_query("   ") is None


def test_posts_model_exposes_post_is_visible():
    assert hasattr(PostsModel, "post_is_visible")
    assert callable(PostsModel.post_is_visible)
