import pytest
import os
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

# Remove the setup_test_env fixture since we'll handle environment variables
# in individual tests for better isolation 