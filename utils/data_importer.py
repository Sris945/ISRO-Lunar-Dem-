import os
import shutil
import re
from pathlib import Path

def extract_date_from_name(root_dir_name: str) -> str:
    match = re.search(r'(\d{8})', root_dir_name)
    if not match:
        raise ValueError(f"Could not extract date from root_dir: {root_dir_name}")
    return match.group(1)

def copy_raw_and_geometry_files(base_dir: str, project: str, root_dir_name: str):
    """
    Copies:
    - .img → raw/img/
    - .xml → raw/xml/
    - .spm and .oat → geometry/
    """

    date_str = extract_date_from_name(root_dir_name)
    root_path = os.path.join(base_dir, root_dir_name)

    # Paths to source folders
    calibrated_path = os.path.join(root_path, "data", "calibrated", date_str)
    misc_path = os.path.join(root_path, "miscellaneous", "calibrated", date_str)

    # Destination folders
    raw_img_dst = os.path.join(base_dir, project, "raw", "img")
    raw_xml_dst = os.path.join(base_dir, project, "raw", "xml")
    geom_dst = os.path.join(base_dir, project, "geometry")

    # Ensure destination folders exist
    os.makedirs(raw_img_dst, exist_ok=True)
    os.makedirs(raw_xml_dst, exist_ok=True)
    os.makedirs(geom_dst, exist_ok=True)

    # Copy .img and .xml
    for file in os.listdir(calibrated_path):
        src = os.path.join(calibrated_path, file)

        if file.lower().endswith(".img"):
            dst = os.path.join(raw_img_dst, file)
            shutil.copy2(src, dst)
            print(f" Copied: {src} → {dst}")

        elif file.lower().endswith(".xml"):
            # Copy to raw_xml_dst
            dst1 = os.path.join(raw_xml_dst, file)
            shutil.copy2(src, dst1)
            print(f" Copied: {src} → {dst1}")

            # Also copy to raw_img_dst
            dst2 = os.path.join(raw_img_dst, file)
            shutil.copy2(src, dst2)
            print(f" Copied: {src} → {dst2}")

        else:
            continue

    # Copy .spm and .oat

    for ext in [".spm", ".oat"]:
        found = False
        for file in os.listdir(misc_path):
            if file.lower().endswith(ext):
                src = os.path.join(misc_path, file)
                dst = os.path.join(geom_dst, file)
                shutil.copy2(src, dst)
                print(f" Copied: {src} → {dst}")
                found = True
        if not found:
            print(f"  No {ext} file found in: {misc_path}")
