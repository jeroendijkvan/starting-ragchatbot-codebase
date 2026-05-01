import sys
import os

# Ensure backend/ is on the path so imports like `from vector_store import ...` resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
