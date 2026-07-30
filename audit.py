from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def usage():
    print("usage: audit.py <pattern> [root] [context]", file=sys.stderr)
    raise SystemExit(2)


if len(sys.argv) < 2:
    usage()

pattern = sys.argv[1]
root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
context = int(sys.argv[3]) if len(sys.argv) > 3 else 0

paths = [root] if root.is_file() else sorted(root.rglob("*"))

for path in paths:
    if not path.is_file():
        continue
    if path.suffix not in {".html", ".py", ".js", ".css"}:
        continue
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        continue
    for idx, line in enumerate(lines, 1):
        if pattern not in line:
            continue
        if context <= 0:
            print(f"{path}:{idx}:{line.strip()}")
            continue
        start = max(0, idx - 1 - context)
        end = min(len(lines), idx + context)
        print(f"--- {path}:{idx} ---")
        for i in range(start, end):
            marker = ">" if i == idx - 1 else " "
            print(f"{marker} {i + 1}: {lines[i]}")
