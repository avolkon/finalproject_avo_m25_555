#!/usr/bin/env python3
"""Entry point CLI."""

from valutatrade_hub.cli.interface import main as cli_main  # ← УБРАЛ .

def main() -> None:
    """Запуск CLI."""
    cli_main()

if __name__ == "__main__":
    main()

    