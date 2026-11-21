"""PyInstaller bootstrap, kept outside the package to preserve absolute imports."""

from league_draft.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
