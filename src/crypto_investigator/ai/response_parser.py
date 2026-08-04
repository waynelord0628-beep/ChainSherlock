import json
import re
from typing import Any

from crypto_investigator.ai.errors import AIParseError, AISchemaError


class ResponseParser:
    def parse(self, text: str) -> dict[str, Any]:
        candidate = text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL | re.IGNORECASE)
        if fenced:
            candidate = fenced.group(1)
        if not candidate.startswith("{") or not candidate.endswith("}"):
            raise AIParseError("AI response must contain JSON only")
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, ValueError) as error:
            raise AIParseError("AI response contains invalid JSON") from error
        if not isinstance(value, dict):
            raise AISchemaError("AI response root must be an object")
        return value
