# utils/directory_setup.py
from pathlib import Path
from datetime import datetime

def setup_project_structure(base_dir, project):
    folders = [
        "raw/xml",
        "raw/img",
        "browse",
        "geometry",
        "miscellaneous",
        "processed/level0",
        "processed/level1",
        "processed/level1/shadow_masks",
        "processed/level2",
        "logs/json",
        "logs/angles",
        "visuals",
        "config",
        "output_package"
    ]

    base_path = Path(base_dir) / project
    log_path = base_path / "logs" / "phase1_structure.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as logf:
        logf.write(f"[{datetime.now()}] Directory Structure Created\n\n")
        for folder in folders:
            path = base_path / folder
            path.mkdir(parents=True, exist_ok=True)
            logf.write(f"{datetime.now()}: Created {path}\n")
            print(f" Created: {path}")
