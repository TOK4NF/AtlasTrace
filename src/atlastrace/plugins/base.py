from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    summary: str
    safety: str
    outputs: str
    optional_dependencies: str = ""

