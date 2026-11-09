"""Loads the YAML lexicon / time-word config files. Pure data in, pure dicts out -
no business logic here so config stays swappable without touching code.
"""
from __future__ import annotations
import pathlib
import yaml

CONFIG_DIR = pathlib.Path(__file__).resolve().parent.parent / "config"


def _load(name: str) -> dict:
    path = CONFIG_DIR / name
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_lexicon() -> dict:
    return _load("lexicon.yaml")


def load_time_words() -> dict:
    return _load("time_words.yaml")
