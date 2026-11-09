"""Keep tokenizer data local to this project; inference works offline."""
import os
from pathlib import Path

os.environ.setdefault("PYTHAINLP_DATA", str(Path(__file__).resolve().parent.parent / ".local" / "pythainlp"))
os.environ.setdefault("PYTHAINLP_OFFLINE", "1")
