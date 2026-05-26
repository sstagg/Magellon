from __future__ import annotations

import json
import os
from typing import Any

from core.exceptions import ValidationError


class MagellonSessionJsonStrategy:
    """Load and validate a Magellon export manifest from session.json."""

    def load(self, source_dir: str) -> dict[str, Any]:
        json_path = os.path.join(source_dir, "session.json")
        if not os.path.exists(json_path):
            raise ValidationError("Invalid archive structure: session.json not found")

        with open(json_path, "r") as f:
            session_data = json.load(f)

        if not session_data.get("msession"):
            raise ValidationError("Invalid archive structure: msession not found in session.json")
        if "images" not in session_data:
            raise ValidationError("Invalid archive structure: images not found in session.json")
        return session_data
