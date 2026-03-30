import json, re, sys
from pathlib import Path

root = Path(__file__).parent
graph = root / "graph.json"
viewer = root / "index.html"

data = json.loads(graph.read_text(encoding="utf-8"))
compact = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

html = viewer.read_text(encoding="utf-8")
updated = re.sub(
    r"const GRAPH_DATA = \{.+?\};",
    f"const GRAPH_DATA = {compact};",
    html,
    count=1,
    flags=re.DOTALL,
)

if not re.search(r"const GRAPH_DATA = \{", html):
    print("ERROR: could not find GRAPH_DATA constant in index.html", file=sys.stderr)
    sys.exit(1)

viewer.write_text(updated, encoding="utf-8")
print(f"Synced {len(data['nodes'])} nodes into index.html")
