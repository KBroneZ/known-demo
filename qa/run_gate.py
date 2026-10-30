#!/usr/bin/env python3
"""Run the QA gate: python run_gate.py fixtures/posts/clean --offline"""

import sys

from qa_gate.cli import main

if __name__ == "__main__":
    sys.exit(main())
