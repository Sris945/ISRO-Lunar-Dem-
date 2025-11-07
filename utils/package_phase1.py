# utils/packager.py

import shutil
import json
from pathlib import Path

def package_phase1_outputs(project_path, image_stems):
    output_dir = Path(project_path) / "output_package"
    output_dir.mkdir(exist_ok=True)

    level1 = Path(project_path) / "processed" / "level1"
    logs = Path(project_path) / "logs"
    config = Path(project_path) / "config"

    for stem in image_stems:
        #copy metadata file
        metadata_file = logs / "metadata_catalog.csv"
        if metadata_file.exists():
            shutil.copy(metadata_file, output_dir / "metadata_catalog.csv")

        # Copy albedo normalized image
        alb_tif = level1 / f"{stem}_albnorm.tif"
        if alb_tif.exists():
            shutil.copy(alb_tif, output_dir / f"{stem}_albnorm.tif")

        # Copy shadow mask
        mask_tif = level1 / "shadow_masks" / f"{stem}_shadowmask.tif"
        if mask_tif.exists():
            shutil.copy(mask_tif, output_dir / f"{stem}_shadowmask.tif")

        # Copy corrected image (assumed output of Minnaert)
        corr_tif = level1 / f"{stem}_if.tif"
        if corr_tif.exists():
            shutil.copy(corr_tif, output_dir / f"{stem}_corrected_image.tif")

    # Copy provenance log
    prov_log = config / "conversion_provenance.jsonl"
    if prov_log.exists():
        shutil.copy(prov_log, output_dir / "conversion_provenance.jsonl")

    # Extract solar angles to a JSON file
    metadata_csv = logs / "metadata_catalog.csv"
    sun_data = {}
    if metadata_csv.exists():
        with open(metadata_csv, 'r') as f:
            headers = f.readline().strip().split(",")
            for line in f:
                values = line.strip().split(",")
                row = dict(zip(headers, values))
                sun_data[Path(row['file_name']).stem] = {
                    "sun_azimuth": float(row.get("sun_azimuth", 0)),
                    "sun_elevation": float(row.get("sun_elevation", 0))
                }
        with open(output_dir / "sun_angles.json", "w") as f:
            json.dump(sun_data, f, indent=4)

    print(f" Output package created at: {output_dir}")
