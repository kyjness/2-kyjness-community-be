# OpenAPI 스키마의 components.schemas 내 property 키를 camelCase로 변환.
# 실제 응답(serialize_by_alias)과 스펙을 일치시켜 프론트 codegen 시 변환 스크립트 불필요하게 함.

from typing import Any


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0].lower() + "".join(w.capitalize() for w in parts[1:])


def _convert_schema_object(obj: Any) -> Any:
    """스키마 객체 내 'properties' 키를 camelCase로 변환. $ref는 유지."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_convert_schema_object(item) for item in obj]
    if not isinstance(obj, dict):
        return obj
    if "$ref" in obj:
        return obj
    out: dict[str, Any] = {}
    for k, v in obj.items():
        if k == "properties" and isinstance(v, dict):
            out[k] = {to_camel(key): _convert_schema_object(val) for key, val in v.items()}
        elif k == "items" and isinstance(v, dict):
            out[k] = _convert_schema_object(v)
        elif k == "allOf" and isinstance(v, list):
            out[k] = [_convert_schema_object(x) for x in v]
        elif k == "oneOf" and isinstance(v, list):
            out[k] = [_convert_schema_object(x) for x in v]
        elif k == "anyOf" and isinstance(v, list):
            out[k] = [_convert_schema_object(x) for x in v]
        else:
            out[k] = _convert_schema_object(v)
    return out


def openapi_schema_to_camel(schema: dict[str, Any]) -> dict[str, Any]:
    """components.schemas 내 각 스키마의 properties 키를 camelCase로 변환한 새 스펙 반환."""
    result = dict(schema)
    components = result.get("components") or {}
    schemas = components.get("schemas") or {}
    if schemas:
        converted = {name: _convert_schema_object(s) for name, s in schemas.items()}
        result["components"] = {**components, "schemas": converted}
    return result
