import rasterio
from rasterio.windows import Window
from datetime import datetime
import matplotlib.pyplot as plt
from pathlib import Path
import csv
import json

def crop_image(base_dir, original_tif_name, crop_coords, crop_name="test_image.tif"):
    """
    Crops a section of the original .tif image and updates metadata/provenance.

    Args:
        base_dir (str): The base working directory of the project.
        original_tif_name (str): File name (not path) of the original .tif inside level0.
        crop_coords (tuple): (xmin, ymin, xmax, ymax) in pixel space.
        crop_name (str): Output cropped image name (default: "test_image.tif")
    """
    # Resolve paths
    original_tif = Path(base_dir) / "processed/level0" / original_tif_name.replace(".img", ".tif")
    cropped_tif = Path(base_dir) / "processed/level0/crops" / crop_name
    visuals_dir = Path(base_dir) / "visuals"/"crops"/crop_name.replace(".tif", "_visuals")
    visuals_dir.mkdir(parents=True, exist_ok=True)
    cropped_png = visuals_dir.with_suffix(".png")

    original_metadata_csv = Path(base_dir) / "logs/metadata_catalog.csv"
    updated_metadata_csv = Path(base_dir) / "logs/metadata_catalog_cropped.csv"
    cropping_jsonl = Path(base_dir) / "logs/json/cropping_provenance.jsonl"
    metadata_prov_jsonl = Path(base_dir) / "logs/json/metadata_provenance_cropped.jsonl"

    # Ensure directories exist
    cropped_tif.parent.mkdir(parents=True, exist_ok=True)
    cropping_jsonl.parent.mkdir(parents=True, exist_ok=True)

    # Crop
    xmin, ymin, xmax, ymax = crop_coords
    width = xmax - xmin
    height = ymax - ymin
    window = Window(xmin, ymin, width, height)

    with rasterio.open(original_tif) as src:
        cropped_data = src.read(1, window=window)
        transform = src.window_transform(window)
        out_profile = src.profile.copy()
        out_profile.update({
            "height": height,
            "width": width,
            "transform": transform,
            "compress": "lzw",
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256
        })

        with rasterio.open(cropped_tif, "w", **out_profile) as dst:
            dst.write(cropped_data, 1)

    # Visualize
    plt.figure(figsize=(8, 6))
    plt.imshow(cropped_data, cmap="gray")
    plt.title("Cropped Image")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(cropped_png)
    plt.close()

    print(f"[\u2714] Cropped image saved: {cropped_tif}")

    # Log crop provenance
    crop_log = {
        "timestamp": datetime.now().isoformat(),
        "source_file": str(original_tif),
        "cropped_file": str(cropped_tif),
        "crop_window_pixels": {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
        "output_dimensions": {"width": width, "height": height},
        "block_size": [256, 256],
        "compression": "lzw"
    }
    with open(cropping_jsonl, "a") as jf:
        jf.write(json.dumps(crop_log) + "\n")

    # Update metadata
    found = False
    original_name = Path(original_tif).name
    cropped_name = cropped_tif.name

    with open(original_metadata_csv, newline='') as csvfile, open(updated_metadata_csv, 'w', newline='') as outcsv:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames + ["crop_source"] if "crop_source" not in reader.fieldnames else reader.fieldnames
        writer = csv.DictWriter(outcsv, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            writer.writerow(row)
            if row["file_name"] == original_name.replace(".tif", ".img"):
                new_row = row.copy()
                new_row["file_name"] = cropped_name
                new_row["ul_lat"] = "cropped"
                new_row["ul_lon"] = "cropped"
                new_row["crop_source"] = original_name
                writer.writerow(new_row)

                with open(metadata_prov_jsonl, "a") as jf:
                    new_row["cloned_at"] = datetime.now().isoformat()
                    json.dump(new_row, jf)
                    jf.write("\n")

                found = True

    if found:
        print(f"[\u2714] Metadata updated: {updated_metadata_csv}")
    else:
        print(f"[!] Original file '{original_name}' not found in metadata.")
