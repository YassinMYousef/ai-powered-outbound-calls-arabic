"""Deprecated entry point — the mock dataset now lives in scripts/mock_data.json
and is loaded by scripts/load_mock_data.py. This shim keeps the old command
working:

    python scripts/seed_mock_data.py [--reset]
"""
import sys

from load_mock_data import main  # scripts/ is on sys.path when run as a script

if __name__ == "__main__":
    sys.exit(main())
