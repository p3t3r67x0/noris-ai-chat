"""Export the API contract without connecting to PostgreSQL or a model provider."""

import argparse
import json
from pathlib import Path

from noris_ai.core.config import EnvironmentSettings
from noris_ai.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    application = create_app(EnvironmentSettings(environment="test"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(application.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
