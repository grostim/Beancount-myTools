#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime, timedelta

# Paths
WORKSPACE = "/home/sorg/.openclaw/workspace/gripesous_home"
FILTERS_PATH = os.path.join(WORKSPACE, "rules/paperless_filters.json")
IMPORT_DIR = os.path.join(WORKSPACE, "Beancount-Perso/A_Importer")

def run_ppls(args):
    cmd = ["ppls"] + args + ["--json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return []
    try:
        return json.loads(res.stdout)
    except:
        return []

def main():
    if not os.path.exists(IMPORT_DIR):
        os.makedirs(IMPORT_DIR)

    if not os.path.exists(FILTERS_PATH):
        print(f"Error: {FILTERS_PATH} not found.")
        return

    with open(FILTERS_PATH, "r") as f:
        filters = json.load(f)

    # Use 24h ago as requested
    added_after = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    unique_doc_ids = set()
    all_filters = filters.get("obligatory", []) + filters.get("optional", [])
    
    for f in all_filters:
        args_str = f["args"]
        extra_args = args_str.split()
        query_args = ["documents", "list", "--added-after", added_after] + extra_args
        docs = run_ppls(query_args)
        for doc in docs:
            unique_doc_ids.add(str(doc["id"]))

    if unique_doc_ids:
        ids_list = list(unique_doc_ids)
        # Download batch
        # If one ID, ppls requires --output, if multiple, it likes --output-dir
        if len(ids_list) == 1:
            # Get title for filename
            doc_info = run_ppls(["documents", "show", ids_list[0]])
            title = doc_info.get("title", f"document_{ids_list[0]}").replace("/", "_")
            dest = os.path.join(IMPORT_DIR, f"{title}.pdf")
            subprocess.run(["ppls", "documents", "download", ids_list[0], "--output", dest])
        else:
            subprocess.run(["ppls", "documents", "download"] + ids_list + ["--output-dir", IMPORT_DIR])
        
        print(f"💰 {len(ids_list)} nouveaux documents Paperless ont été récupérés.")
    else:
        # No documents found in last 24h
        pass

if __name__ == "__main__":
    main()
