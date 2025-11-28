#!/usr/bin/env python3
import json
from pathlib import Path
import argparse

def next_available_id(used: set):
    for i in range(1000, 10000):
        s = f"{i:04d}"
        if s not in used:
            return s
    raise RuntimeError("No available 4-digit IDs remaining.")

def process(file_path: Path, in_place=True, output=None, make_backup=True):
    path = file_path
    if make_backup:
        backup_path = path.with_suffix(path.suffix + ".backup")
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    data = json.loads(path.read_text(encoding="utf-8"))
    existing_ids = set()
    for item in data:
        item_id = str(item.get("id", "")).strip()
        if item_id:
            existing_ids.add(item_id)

    used = set(existing_ids)
    new_assignments = []
    for item in data:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            nid = next_available_id(used)
            item["id"] = nid
            new_assignments.append({"id": nid, "title": item.get("title", "")})
            used.add(nid)

    out_path = path if in_place or output is None else Path(output)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Materials with ID (after): {sum(1 for it in data if str(it.get('id','')).strip())} / {len(data)}")
    print(f"New IDs assigned: {len(new_assignments)}")
    if new_assignments:
        print("Assigned IDs:")
        for a in new_assignments:
            print(f"  {a['id']}  —  {a['title']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill empty 'id' fields with unique 4-digit IDs in a JSON collection (array of objects).")
    parser.add_argument("file", help="Path to JSON file (array of objects).")
    parser.add_argument("-o", "--output", help="Optional output file. If omitted, updates the input file in-place.", default=None)
    parser.add_argument("--no-backup", action="store_true", help="Do not create a .backup file before writing.")
    args = parser.parse_args()

    process(Path(args.file), in_place=(args.output is None), output=args.output, make_backup=(not args.no_backup))
