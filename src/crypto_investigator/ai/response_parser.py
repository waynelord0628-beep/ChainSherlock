import json
from typing import Any

from crypto_investigator.ai.errors import AIParseError, AISchemaError
from crypto_investigator.ai.redaction import redact_text


class ResponseParser:
    def __init__(self):
        self.warnings: list[str] = []
        self.diagnostics: dict[str, Any] = {}

    def parse(self, text: str) -> dict[str, Any]:
        self.warnings = []
        self.diagnostics = {}
        if not isinstance(text, str):
            raise AIParseError(
                "AI response content must be text",
                safe_details={"parser_diagnostics": {"content_type": type(text).__name__}},
            )
        candidate = text.removeprefix("\ufeff").strip()
        self.diagnostics = {
            "content_starts_with": candidate[:1],
            "content_ends_with": candidate[-1:] if candidate else "",
            "content_length": len(candidate),
        }
        if candidate.startswith("```") and candidate.endswith("```"):
            first_newline = candidate.find("\n")
            if first_newline > 0:
                candidate = candidate[first_newline + 1:-3].strip()
                self.warnings.append("fenced_json_unwrapped")
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError as error:
            diagnostics = {
                **self.diagnostics,
                "json_error_line": error.lineno,
                "json_error_column": error.colno,
                "json_error_message": redact_text(error.msg, 200),
            }
            raise AIParseError(
                "AI response contains invalid JSON",
                safe_details={
                    "parser_diagnostics": diagnostics,
                    "parser_warnings": tuple(self.warnings),
                },
            ) from error
        if not isinstance(value, dict):
            raise AISchemaError("AI response root must be an object")
        return value
