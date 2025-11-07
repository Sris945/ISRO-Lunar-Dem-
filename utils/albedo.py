import os
import csv
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from scipy.ndimage import gaussian_filter, sobel

def normalize_and_visualize(input_tif, output_tif, base_dir, sigma=15):
    # Get input stem for consistent filenames
    stem = Path(input_tif).stem.replace("_if", "")

    # Paths
    visual_dir = Path(base_dir) / "visuals" / "albedo"
    log_csv_path = Path(base_dir) / "logs" / "albedo_qc.csv"
    log_txt_path = Path(base_dir) / "logs" / "albedo_normalization.log"
    visual_dir.mkdir(parents=True, exist_ok=True)
    log_csv_path.parent.mkdir(parents=True, exist_ok=True)
    log_txt_path.parent.mkdir(parents=True, exist_ok=True)

    # Logger
    def log(msg):
        ts = datetime.now().isoformat()
        line = f"[{ts}] {msg}"
        print(line)
        with open(log_txt_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    log(f"Opening I/F input: {input_tif}")
    log(f"Sigma (Gaussian smoothing scale): {sigma}")

    with rasterio.open(input_tif) as src:
        profile = src.profile
        arr = src.read(1).astype(np.float32)

    arr = np.nan_to_num(arr, nan=0.0)
    arr[arr < 0] = 0

    log("Performing Gaussian smoothing...")
    albedo_trend = gaussian_filter(arr, sigma=sigma)
    albedo_trend[albedo_trend < 1e-6] = 1e-6

    arr_norm = arr / albedo_trend
    arr_norm *= 0.1 / np.mean(arr_norm)

    # Save normalized output
    profile.update(dtype=rasterio.float32, compress="lzw", tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(output_tif, "w", **profile) as dst:
        dst.write(arr_norm.astype(np.float32), 1)

    log(f"Saved albedo-normalized I/F to: {output_tif}")

    # ---------- VISUALIZATIONS ----------
    hist_path = visual_dir / f"{stem}_histogram_comparison.png"
    grad_path = visual_dir / f"{stem}_gradient_map.png"
    profile_path = visual_dir / f"{stem}_brightness_profile.png"
    panel_path = visual_dir / f"{stem}_compare_visual.png"

    # Histogram
    log("Generating histogram comparison...")
    plt.figure(figsize=(10, 4))
    plt.hist(arr.ravel(), bins=100, alpha=0.6, label='Before (Minnaert I/F)', color='blue')
    plt.hist(arr_norm.ravel(), bins=100, alpha=0.6, label='After Albedo Normalization', color='orange')
    plt.xlabel("I/F Value")
    plt.ylabel("Pixel Count")
    plt.title("Histogram Comparison")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(hist_path)
    plt.close()
    log(f"Saved: {hist_path}")

    # Gradient map
    log("Generating gradient map...")
    grad = np.hypot(sobel(arr_norm, axis=0), sobel(arr_norm, axis=1))
    plt.imshow(grad, cmap='inferno')
    plt.colorbar(label='Gradient Magnitude')
    plt.title("Gradient Map After Albedo Normalization")
    plt.tight_layout()
    plt.savefig(grad_path)
    plt.close()
    log(f"Saved: {grad_path}")

    # Brightness profile
    log("Generating brightness profile...")
    row = arr.shape[0] // 2
    plt.figure(figsize=(10, 4))
    plt.plot(arr[row, :], label='Before', color='blue')
    plt.plot(arr_norm[row, :], label='After', color='orange')
    plt.title(f"Brightness Profile (Row {row})")
    plt.xlabel("Column")
    plt.ylabel("I/F Value")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(profile_path)
    plt.close()
    log(f"Saved: {profile_path}")

    # Before/After comparison
    log("Generating before/after visual panel...")
    fig, axs = plt.subplots(1, 2, figsize=(12, 6))
    axs[0].imshow(arr, cmap='gray')
    axs[0].set_title("Before Albedo Normalization")
    axs[1].imshow(arr_norm, cmap='gray')
    axs[1].set_title("After Albedo Normalization")
    for ax in axs:
        ax.axis('off')
    plt.tight_layout()
    plt.savefig(panel_path)
    plt.close()
    log(f"Saved: {panel_path}")

    # ---------- QC STATISTICS ----------
    min_val = float(np.min(arr_norm))
    max_val = float(np.max(arr_norm))
    mean_val = float(np.mean(arr_norm))
    std_val = float(np.std(arr_norm))
    log(f"Stats -> min: {min_val:.6f}, max: {max_val:.6f}, mean: {mean_val:.6f}, std: {std_val:.6f}")

    with open(log_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["file", "min", "max", "mean", "std"])
        writer.writeheader()
        writer.writerow({
            "file": Path(output_tif).name,
            "min": min_val,
            "max": max_val,
            "mean": mean_val,
            "std": std_val
        })
    log(f"QC CSV written to: {log_csv_path}")

#main

def run_albedo_correction(base_dir, image_stem,config):
    sigma = config["albedo"]["sigma"]
    input_if = Path(base_dir) / "processed" / "level1" / f"{image_stem}_if.tif"
    output_if = Path(base_dir) / "processed" / "level1" / f"{image_stem}_albnorm.tif"
    normalize_and_visualize(str(input_if), str(output_if), str(base_dir),sigma=sigma)
