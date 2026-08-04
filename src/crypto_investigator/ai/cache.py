from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time


class AICache:
    def __init__(self, directory: Path, ttl_seconds: int = 86400):
        self.directory = directory
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key(*, provider, model, prompt_version, input_hash, language, sections, temperature, schema_version):
        value = json.dumps(
            {
                "provider": provider, "model": model, "prompt_version": prompt_version,
                "input_hash": input_hash, "language": language, "sections": sections,
                "temperature": temperature, "schema_version": schema_version,
            },
            sort_keys=True,
        )
        return sha256(value.encode()).hexdigest()

    def get(self, key):
        path = self.directory / f"{key}.json"
        try:
            if time.time() - path.stat().st_mtime > self.ttl_seconds:
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

    def put(self, key, value):
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / f"{key}.json"
        handle, raw_path = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False)
            os.replace(raw_path, destination)
        finally:
            if os.path.exists(raw_path):
                os.unlink(raw_path)
        return destination
