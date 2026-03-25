from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _is_local_editable_or_path_requirement(line: str) -> bool:
    # Examples:
    # - puppytalk-api @ file:///... (local project)
    # - -e file:///... (editable local)
    # - somepkg @ git+https://... (non-PyPI direct URL)
    s = line.strip()
    return (
        " @ file://" in s
        or s.startswith("-e ")
        or " @ git+" in s
        or " @ hg+" in s
        or " @ svn+" in s
        or " @ bzr+" in s
    )


def main() -> int:
    out_path = Path(".audit-requirements.txt")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    )
    lines: list[str] = []
    for raw in r.stdout.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if _is_local_editable_or_path_requirement(s):
            continue
        lines.append(s)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
