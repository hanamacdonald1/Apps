"""Native desktop entry point; no browser server is started."""
import os
import sys

if __name__ == '__main__':
    from hana_ai.desktop_ui import main
    raise SystemExit(main())
