import sys

from crypto_investigator.cli import app

if len(sys.argv) == 1:
    from crypto_investigator.ui import launch_ui

    raise SystemExit(launch_ui())
app()

