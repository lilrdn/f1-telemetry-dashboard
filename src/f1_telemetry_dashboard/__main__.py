from __future__ import annotations

from .app import create_app
from .config import load_settings


def main() -> None:
    settings = load_settings()
    app = create_app()
    print("🚀 Запуск F1 Telemetry Dashboard…")
    print(f"🌐 http://127.0.0.1:{settings.port}")
    app.run(host="127.0.0.1", port=settings.port, debug=False)


if __name__ == "__main__":
    main()

