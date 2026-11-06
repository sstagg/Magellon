"""A composite filter over a session's images, compiled to SQL.

The filter is the one the images tab builds: conditions on a field
("resolution <= 4", "magnification != 59000", "name contains ex") in groups
joined with AND or OR, and a group can be negated with NOT. Groups can nest.

Only the fields and operators below are accepted, and values are always bound
parameters, so a filter can't inject SQL. The SQL refers to the image table
as ``i``. Every condition is true or false, never NULL, so NOT behaves: an
image without a value isn't equal to anything and matches nothing else, except
"≠" and "does not contain".

Reusable by anything that selects images: the images list, counts, exports.

The CTF resolution is read from the stored CTF result ("CTF Meta Data" in
image_meta_data), so nothing is added to the database for it.
"""
from __future__ import annotations

import itertools
import math
from typing import Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

def resolution_sql(dialect: str) -> str:
    """The image's CTF 50% resolution (Å) from its stored CTF result, or NULL.

    The result is [{"key": "CTF", "value": ...}], the value JSON text (or an
    object); an evaluation that failed has no resolution, and text that isn't
    valid JSON (NaN) gives NULL instead of an error."""
    if dialect == "sqlite":  # the tests' database
        return ("(SELECT json_extract(json_extract(m.data_json, '$[0].value'), '$.resolution_50_percent') "
                "FROM image_meta_data m WHERE m.image_id = i.oid AND m.name = 'CTF Meta Data' LIMIT 1)")
    return ("(SELECT CAST(JSON_UNQUOTE(JSON_EXTRACT("
            "CASE WHEN JSON_TYPE(jt.v) <> 'STRING' THEN jt.v "
            "WHEN JSON_VALID(JSON_UNQUOTE(jt.v)) THEN CAST(JSON_UNQUOTE(jt.v) AS JSON) END, "
            "'$.resolution_50_percent')) AS DOUBLE) "
            "FROM image_meta_data m, JSON_TABLE(m.data_json, '$[*]' COLUMNS ("
            "k VARCHAR(64) PATH '$.key', v JSON PATH '$.value')) jt "
            "WHERE m.image_id = i.oid AND m.name = 'CTF Meta Data' AND jt.k = 'CTF' LIMIT 1)")


# Children of an image in the same session.
CHILDREN_COUNT = ("(SELECT COUNT(*) FROM image c "
                  "WHERE c.parent_id = i.oid AND c.session_id = i.session_id)")

# field -> (SQL value as the page shows it, numeric). Defocus is shown in μm,
# pixel size in Å per binned pixel, so that's what conditions compare against.
FIELDS: Dict[str, Tuple[str, bool]] = {
    "name": ("i.name", False),
    "mag": ("i.magnification", True),
    "defocus": ("ROUND(i.defocus * 1000000, 2)", True),
    "pixelSize": ("ROUND(i.pixel_size * i.binning_x * 10000000000, 3)", True),
    "resolution": ("ROUND({resolution}, 2)", True),
    "children": (CHILDREN_COUNT, True),
}

FilterField = Literal["name", "mag", "defocus", "pixelSize", "resolution", "children"]
FilterOperator = Literal["eq", "ne", "lt", "le", "gt", "ge", "contains", "notContains",
                         "startsWith", "empty", "notEmpty"]

_NUMERIC_ONLY = {"lt": "<", "le": "<=", "gt": ">", "ge": ">="}
_TEXT_ONLY = {"contains", "notContains", "startsWith"}
MAX_RULES = 100
MAX_DEPTH = 5


class FilterRule(BaseModel):
    kind: Literal["rule"]
    id: Optional[str] = None
    field: FilterField
    operator: FilterOperator
    value: str = Field("", max_length=200)


class FilterGroup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["group"]
    id: Optional[str] = None
    combinator: Literal["and", "or"] = "and"
    negate: bool = Field(False, alias="not")
    rules: List[Union[FilterRule, "FilterGroup"]] = Field(default_factory=list)


FilterGroup.model_rebuild()


class FilterError(ValueError):
    """The filter can't be used: too large, or an operator that doesn't fit its field."""


def parse_filter(text: Optional[str]) -> Optional[FilterGroup]:
    """The filter from its JSON, or None for no filter. Raises FilterError if it's invalid."""
    if not text:
        return None
    try:
        return FilterGroup.model_validate_json(text)
    except ValueError as e:
        raise FilterError(f"Invalid filter: {e}") from e


def _like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def field_sql(field: str, dialect: str) -> str:
    return FIELDS[field][0].replace("{resolution}", resolution_sql(dialect))


def compile_filter(group: Optional[FilterGroup], dialect: str = "mysql",
                   prefix: str = "flt") -> Optional[Tuple[str, dict]]:
    """(SQL condition, parameters) for the filter, or None when it has no finished condition.

    Unfinished conditions (no value, or a number that isn't one) are left out,
    as are groups left empty, the same as the filter dialog does."""
    if group is None:
        return None
    params: dict = {}
    names = (f"{prefix}{n}" for n in itertools.count())
    rule_count = 0

    def rule_sql(rule: FilterRule) -> Optional[str]:
        expr, numeric = field_sql(rule.field, dialect), FIELDS[rule.field][1]
        op = rule.operator
        if numeric and op in _TEXT_ONLY or not numeric and op in _NUMERIC_ONLY:
            raise FilterError(f"'{op}' doesn't apply to {rule.field}")
        if op == "empty":
            return f"({expr} IS NULL)" if numeric else f"({expr} IS NULL OR {expr} = '')"
        if op == "notEmpty":
            return f"({expr} IS NOT NULL)" if numeric else f"({expr} IS NOT NULL AND {expr} <> '')"
        text = rule.value.strip()
        if not text:
            return None
        name = next(names)
        if numeric:
            try:
                number = float(text)
            except ValueError:
                return None
            if not math.isfinite(number):
                return None
            params[name] = number
            if op == "eq":
                return f"({expr} IS NOT NULL AND {expr} = :{name})"
            if op == "ne":
                return f"({expr} IS NULL OR {expr} <> :{name})"
            return f"({expr} IS NOT NULL AND {expr} {_NUMERIC_ONLY[op]} :{name})"
        lowered = f"LOWER({expr})"
        text = text.lower()
        if op == "eq":
            params[name] = text
            return f"({expr} IS NOT NULL AND {lowered} = :{name})"
        if op == "ne":
            params[name] = text
            return f"({expr} IS NULL OR {lowered} <> :{name})"
        params[name] = f"{_like(text)}%" if op == "startsWith" else f"%{_like(text)}%"
        if op == "notContains":
            return f"({expr} IS NULL OR {lowered} NOT LIKE :{name} ESCAPE '!')"
        return f"({expr} IS NOT NULL AND {lowered} LIKE :{name} ESCAPE '!')"

    def group_sql(node: FilterGroup, depth: int) -> Optional[str]:
        nonlocal rule_count
        if depth > MAX_DEPTH:
            raise FilterError(f"Groups can be nested {MAX_DEPTH} deep at most")
        parts = []
        for child in node.rules:
            if isinstance(child, FilterRule):
                rule_count += 1
                if rule_count > MAX_RULES:
                    raise FilterError(f"A filter can have {MAX_RULES} conditions at most")
                sql = rule_sql(child)
            else:
                sql = group_sql(child, depth + 1)
            if sql:
                parts.append(sql)
        if not parts:
            return None
        joined = "(" + (" AND " if node.combinator == "and" else " OR ").join(parts) + ")"
        return f"(NOT {joined})" if node.negate else joined

    sql = group_sql(group, 0)
    return (sql, params) if sql else None


# Sorting: "related" (images with a parent or children first, then by name) or a field.
SORT_FIELDS: Dict[str, str] = {
    "name": "i.name",
    "mag": "i.magnification",
    "defocus": "i.defocus",
    "pixelSize": "i.pixel_size * i.binning_x",
    "resolution": "{resolution}",
    "children": CHILDREN_COUNT,
}
SortField = Literal["related", "name", "mag", "defocus", "pixelSize", "resolution", "children"]


def order_by(sort: str, descending: bool, all_levels: bool, dialect: str = "mysql") -> str:
    """ORDER BY for a sort, empty values last either way, ties broken by name."""
    direction = "DESC" if descending else "ASC"
    if sort == "related":
        related = "EXISTS (SELECT 1 FROM image c WHERE c.parent_id = i.oid AND c.session_id = i.session_id)"
        if all_levels:
            related = f"({related} OR i.parent_id IS NOT NULL)"
        return f"{related} DESC, i.name {direction}, i.oid"
    expr = SORT_FIELDS[sort].replace("{resolution}", resolution_sql(dialect))
    return f"({expr}) IS NULL, {expr} {direction}, i.name, i.oid"
