"""`python -m doctool` starts the local server (see DOCTOOL_* variables in docs/README)."""

import uvicorn

from doctool.config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run("doctool.main:app_factory", factory=True, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
