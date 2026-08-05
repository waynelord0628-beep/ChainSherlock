from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


CJK_FONT = "\u6a19\u6977\u9ad4"
LATIN_FONT = "Times New Roman"
TABLE_LATIN_FONT = "Consolas"


class ScriptRole(StrEnum):
    CJK = "cjk"
    LATIN = "latin"
    NUMERIC = "numeric"
    TABLE_TECH = "table_tech"
    NEWLINE = "newline"


@dataclass(frozen=True, slots=True)
class ScriptRun:
    text: str
    role: ScriptRole


_TOKEN = re.compile(
    r"(?:0x[0-9A-Fa-f]{16,}|[13bc][A-Za-z0-9]{20,}|T[A-Za-z0-9]{20,}|"
    r"[A-Z][A-Z0-9_-]{1,}-\d{2,}|[A-Fa-f0-9]{32,})"
    r"|(?:\d+(?:[,.]\d+)*(?:%|E[+-]?\d+)?)"
    r"|(?:[A-Za-z]+(?:[._/-][A-Za-z]+)*)"
    r"|(?:[\u3400-\u9fff\uf900-\ufaff]+)"
    r"|(?:\r\n|\r|\n)"
    r"|(?:.)",
    re.DOTALL,
)


def mixed_script_runs(value: object, *, table: bool = False) -> tuple[ScriptRun, ...]:
    text = str(value)
    result: list[ScriptRun] = []
    previous = ScriptRole.TABLE_TECH if table else ScriptRole.LATIN
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        if token in {"\r", "\n", "\r\n"}:
            role = ScriptRole.NEWLINE
        elif re.fullmatch(
            r"(?:0x[0-9A-Fa-f]{16,}|[13bc][A-Za-z0-9]{20,}|"
            r"T[A-Za-z0-9]{20,}|[A-Z][A-Z0-9_-]{1,}-\d{2,}|"
            r"[A-Fa-f0-9]{32,})",
            token,
        ):
            role = ScriptRole.TABLE_TECH if table else ScriptRole.LATIN
        elif re.fullmatch(r"\d+(?:[,.]\d+)*(?:%|E[+-]?\d+)?", token):
            role = ScriptRole.NUMERIC
        elif re.fullmatch(r"[A-Za-z]+(?:[._/-][A-Za-z]+)*", token):
            role = ScriptRole.TABLE_TECH if table else ScriptRole.LATIN
        elif re.search(r"[\u3400-\u9fff\uf900-\ufaff]", token):
            role = ScriptRole.CJK
        elif token in (
            "\uff0c\u3002\uff1b\uff1a\u3001\uff08\uff09\u300c\u300d"
            "\u300e\u300f\u300a\u300b\u3008\u3009\uff1f\uff01\u3010\u3011"
        ):
            role = ScriptRole.CJK
        else:
            role = previous
        if role is not ScriptRole.NEWLINE:
            previous = role
        if result and result[-1].role is role:
            result[-1] = ScriptRun(result[-1].text + token, role)
        else:
            result.append(ScriptRun(token, role))
    return tuple(result)


def font_family(role: ScriptRole, *, table: bool = False) -> str:
    if role is ScriptRole.CJK:
        return CJK_FONT
    if role is ScriptRole.TABLE_TECH or (table and role is ScriptRole.LATIN):
        return TABLE_LATIN_FONT
    return LATIN_FONT
