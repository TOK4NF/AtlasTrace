from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    home_dir: Path
    db_path: Path
    case_root: Path
    user_agent: str = "AtlasTrace/0.1"

    @classmethod
    def from_env(cls) -> "Settings":
        home_override = os.getenv("ATLASTRACE_HOME")
        home_dir = (
            Path(home_override).expanduser().resolve()
            if home_override
            else (Path.cwd() / ".atlastrace").resolve()
        )
        return cls(
            home_dir=home_dir,
            db_path=home_dir / "atlastrace.sqlite3",
            case_root=home_dir / "cases",
        )

    def ensure_home(self) -> None:
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.case_root.mkdir(parents=True, exist_ok=True)

