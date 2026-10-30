"""Print the OpenAPI schema (the API contract) as JSON, without starting a server.

The frontend generates its TypeScript types from this file, and CI checks that the committed
copy (frontend/src/api/openapi.json) matches the backend — so the two can never drift apart.

Usage: uv run python -m mgpa_backend.export_openapi > ../frontend/src/api/openapi.json
"""

import json

from mgpa_backend.main import app


def main() -> None:
    print(json.dumps(app.openapi(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
