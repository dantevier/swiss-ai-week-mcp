import json
import os
from pathlib import Path

import yaml


def load_config(path):
    return yaml.safe_load(os.path.expandvars(Path(path).read_text(encoding="utf-8")))


def load_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
