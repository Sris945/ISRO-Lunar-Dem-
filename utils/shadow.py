from pathlib import Path
from datetime import datetime
import csv
import numpy as np
import matplotlib.pyplot as plt
import rasterio
from scipy.ndimage import binary_opening, binary_closing, generate_binary_structure
import pandas as pd

# Constants

def log(message, log_path):
    ts = datetime.now().isoformat()
    line = f"[{ts}] {message}"
    print(line)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_sun_elevation(metadata_csv):
    sun_el = {}
    with open(metadata_csv, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stem = Path(row['file_name']).stem
            sun_el[stem] = float(row['sun_elevation'])
    return sun_el

def plot_shadow_coverage_bar(coverage_csv, output_path):
    df = pd.read_csv(coverage_csv)
    df['shadow_coverage_pct'] = df['shadow_coverage_pct'].astype(float)
    plt.figure(figsize=(10, 4))
    plt.bar(df['tile'], df['shadow_coverage_pct'], color='darkblue')
    plt.axhline(50, color='red', linestyle='--', label='50% threshold')
    plt.xticks(rotation=90, fontsize=6)
    plt.ylabel("Shadow Coverage (%)")
    plt.title("Per-Tile Shadow Coverage")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

def run_shadow_detection(base_dir,config):
    base_dir = Path(base_dir)
    level1_dir = base_dir / "processed" / "level1"
    shadow_dir = level1_dir / "shadow_masks"
    shadow_dir.mkdir(parents=True, exist_ok=True)

    visual_dir = base_dir / "visuals" / "shadow_detection"
    visual_dir.mkdir(parents=True, exist_ok=True)
    log_file = base_dir / "logs" / "shadow_detection.log"
    coverage_csv = base_dir / "logs" / "shadow_coverage.csv"
    coverage_bar_png = base_dir / "logs" / "shadow_coverage_bar.png"
    metadata_csv = base_dir / "logs" / "metadata_catalog.csv"

    SUN_EL_THRESHOLD = config["shadow"]["sun_el_threshold"]
    ABS_IF_THRESHOLD = config["shadow"]["abs_if_threshold"]
    THRESHOLD_FACTOR = config["shadow"]["threshold_factor"]
    MIN_IF_VALID = config["shadow"]["min_if_valid"]
    MORPH_ITERS = config["shadow"]["morph_iters"]
    STRUCT = generate_binary_structure(2, 2)
    
    log(f"Starting shadow detection with parameters: "
        f"SUN_EL_THRESHOLD={SUN_EL_THRESHOLD}, ABS_IF_THRESHOLD={ABS_IF_THRESHOLD}, "
        f"THRESHOLD_FACTOR={THRESHOLD_FACTOR}, MIN_IF_VALID={MIN_IF_VALID}, "
        f"MORPH_ITERS={MORPH_ITERS}", log_file)
    
    sun_elevations = load_sun_elevation(metadata_csv)
    coverage_log = []

    for tif in sorted(level1_dir.glob("*_albnorm.tif")):
        stem = tif.stem.replace("_albnorm", "")
        with rasterio.open(tif) as src:
            arr = src.read(1).astype(np.float32)
            profile = src.profile

        sun_el = sun_elevations.get(stem, 45.0)
        if sun_el < SUN_EL_THRESHOLD:
            mask = np.ones_like(arr, dtype=bool)
            reason = f"Sun low ({sun_el:.1f}°)"
        else:
            valid = arr >= MIN_IF_VALID
            mean_if = float(arr[valid].mean()) if valid.any() else 0.0
            rel_thr = THRESHOLD_FACTOR * mean_if
            mask = (arr < ABS_IF_THRESHOLD) | (arr < rel_thr)
            reason = f"mean_IF={mean_if:.3f}, rel_thr={rel_thr:.3f}"

        mask = binary_opening(mask, structure=STRUCT, iterations=MORPH_ITERS)
        mask = binary_closing(mask, structure=STRUCT, iterations=MORPH_ITERS)

        # Save mask
        out_profile = profile.copy()
        out_profile.update(dtype=rasterio.uint8, count=1, compress="lzw")
        out_mask = shadow_dir / f"{stem}_shadowmask.tif"
        with rasterio.open(out_mask, "w", **out_profile) as dst:
            dst.write(mask.astype(np.uint8), 1)

        # Save overlay
        overlay_path = visual_dir / f"{stem}_shadow_overlay.png"
        plt.figure(figsize=(8, 4))
        plt.subplot(1, 2, 1)
        plt.imshow(arr, cmap='gray', vmin=0, vmax=np.percentile(arr, 99))
        plt.title("Albedo-Norm I/F")
        plt.axis("off")

        plt.subplot(1, 2, 2)
        plt.imshow(arr, cmap='gray', vmin=0, vmax=np.percentile(arr, 99))
        plt.imshow(mask, cmap='Reds', alpha=0.4)
        plt.title(f"Shadow Mask\n{reason}")
        plt.axis("off")

        plt.tight_layout()
        plt.savefig(overlay_path, dpi=150)
        plt.close()

        # Log coverage
        shadow_pct = 100.0 * mask.sum() / mask.size
        coverage_log.append((stem, f"{shadow_pct:.2f}", reason))
        log(f"[OK] {stem}: {reason}, shadow={shadow_pct:.2f}%", log_file)

    # Save CSV + Bar plot
    with open(coverage_csv, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["tile", "shadow_coverage_pct", "method"])
        writer.writerows(coverage_log)

    log(f" Shadow coverage CSV saved to: {coverage_csv}", log_file)
    plot_shadow_coverage_bar(coverage_csv, coverage_bar_png)
    log(f" Shadow bar chart saved to: {coverage_bar_png}", log_file)
