import json, sys
from collections import Counter
from pathlib import Path

with open(Path(__file__).parent / "graph.json") as f:
    g = json.load(f)

nodes = {n["id"]: n for n in g["nodes"]}
cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

if cmd == "node":
    nid = sys.argv[2]
    n = nodes.get(nid)
    if n:
        print(json.dumps(n, indent=2))
    else:
        print(f"not found: {nid}")

elif cmd == "type":
    t = sys.argv[2]
    for n in g["nodes"]:
        if n["type"] == t:
            print(f"  {n['id']}: {n['desc']}")

elif cmd == "edges-to":
    target = sys.argv[2]
    for n in g["nodes"]:
        for e in n.get("edges", []):
            if e["to"] == target:
                print(f"  {n['id']} --{e['rel']}--> {target}")

elif cmd == "edges-from":
    nid = sys.argv[2]
    n = nodes.get(nid)
    if n:
        for e in n.get("edges", []):
            print(f"  {nid} --{e['rel']}--> {e['to']}")

elif cmd == "types":
    c = Counter(n["type"] for n in g["nodes"])
    for t, count in c.most_common():
        print(f"  {t}: {count}")

elif cmd == "search":
    q = " ".join(sys.argv[2:]).lower()
    for n in g["nodes"]:
        if q in n["id"].lower() or q in n.get("desc", "").lower():
            print(f"  {n['id']} [{n['type']}]: {n['desc']}")

else:
    print("Usage: python query.py <command> [args]")
    print("  node <id>        Show node details")
    print("  type <type>      List nodes of a type")
    print("  edges-to <id>    Show incoming edges")
    print("  edges-from <id>  Show outgoing edges")
    print("  types            Count nodes by type")
    print("  search <query>   Search nodes by id or description")
