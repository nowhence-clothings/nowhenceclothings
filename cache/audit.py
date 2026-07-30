from pathlib import Path
import sys


def usage():
    print("usage: audit.py <pattern> [root]", file=sys.stderr)
    raise SystemExit(2)


if len(sys.argv) < 2:
    usage()

pattern = sys.argv[1]
root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")

for path in sorted(root.rglob("*")):
    if not path.is_file():
        continue
    if path.suffix not in {".html", ".py", ".js", ".css"}:
        continue
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        continue
    for idx, line in enumerate(lines, 1):
        if pattern in line:
            print(f"{path}:{idx}:{line.strip()}")
