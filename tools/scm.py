#!/usr/bin/env python
import sys
from pathlib import Path

# Add the project root directory (e.g., scm-env/) to the Python path
# This allows importing the 'scm' package
project_root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root_dir))

# Import and run the main CLI function from the scm package
from scm.cli.scm_cli import main

if __name__ == "__main__":
    main() 