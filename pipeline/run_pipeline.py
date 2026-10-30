#!/usr/bin/env python3
"""Run the blog pipeline: python run_pipeline.py run --pick "clinic-a=Teeth whitening" --dry-run"""

import sys

from dental_pipeline.cli import main

if __name__ == "__main__":
    sys.exit(main())
