# file: minnaert_correction.py

import os
import csv
import json
import bisect
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

# ------------------------------------------------------
# Helper Functions to Parse Angle Data
# ------------------------------------------------------
def parse_spm(spm_txt: Path):
    times, elevs = [], []
    with open(spm_txt, 'r') as f:
        for line in f:
            if not line.startswith("ORBTATTD"):
                continue
            try:
                year = 2000 + int(str(int(line[14:22].strip()))[-4:])
                month = int(line[22:26].strip())
                day = int(line[26:30].strip())
                hour = int(line[30:34].strip())
                minute = int(line[34:38].strip())
                second = int(line[38:42].strip())
                dt = datetime(year, month, day, hour, minute, second)
                sun_el = float(line.strip().split()[-1])
                times.append(dt)
                elevs.append(sun_el)
            except:
                continue
    return times, elevs

def parse_oat(oat_txt: Path):
    times, emis = [], []
    with open(oat_txt, 'r') as f:
        for line in f:
            if not line.startswith("ORBTATTD"):
                continue
            try:
                year = 2000 + int(str(int(line[14:22].strip()))[-4:])
                month = int(line[22:26].strip())
                day = int(line[26:30].strip())
                hour = int(line[30:34].strip())
                minute = int(line[34:38].strip())
                second = int(line[38:42].strip())
                dt = datetime(year, month, day, hour, minute, second)
                emis_angle = float(line[233:242].strip())
                times.append(dt)
                emis.append(emis_angle)
            except:
                continue
    return times, emis

def fallback_angles(xml_path: Path, default_emission=10.0):
    if not xml_path.exists():
        return 45.0, default_emission
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'isda': 'http://www.isro.gov.in/isda'}
        selev_el = root.find(".//isda:sun_elevation", ns)
        inc_el = root.find(".//isda:solar_incidence", ns)
        if inc_el is not None:
            incidence = float(inc_el.text)
        elif selev_el is not None:
            incidence = 90.0 - float(selev_el.text)
        else:
            incidence = 45.0
        return incidence, default_emission
    except:
        return 45.0, default_emission

def interp_angle(image_time, times, values):
    idx = bisect.bisect_left(times, image_time)
    if idx == 0:
        return values[0]
    if idx >= len(times):
        return values[-1]
    t0, t1 = times[idx - 1], times[idx]
    v0, v1 = values[idx - 1], values[idx]
    frac = (image_time - t0).total_seconds() / (t1 - t0).total_seconds()
    return v0 + frac * (v1 - v0)

# ------------------------------------------------------
# Minnaert Correction with Logging + Visualization
# ------------------------------------------------------
class MinnaertCorrector:
    def __init__(self, base_dir, metadata_csv, oat_file, spm_file, dark_current, gain, k_exponent):
        self.base = Path(base_dir)
        self.level0 = self.base / "processed" / "level0" / "crops"
        self.level1 = self.base / "processed" / "level1" 
        self.level1.mkdir(parents=True, exist_ok=True)

        self.log_txt = self.base / "logs" / "minnaert_correction.log"
        self.log_csv = self.base / "logs" / "radiometric_qc.csv"
        self.log_jsonl = self.base / "logs" / "radiometric_provenance.jsonl"
        self.bar_png = self.base / "visuals" / "correction" / "radiometric_qc_bar.png"
        self.hist_png = self.base / "visuals" / "correction" / "radiometric_qc_histogram.png"
        self.bar_png.parent.mkdir(parents=True, exist_ok=True)
        self.meta = {}
        with open(metadata_csv, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stem = Path(row["file_name"]).stem
                t = datetime.strptime(row["start_time"][:19], "%Y-%m-%dT%H:%M:%S")
                self.meta[stem] = t

        self.oat_times, self.emis_vals = parse_oat(Path(oat_file)) if Path(oat_file).exists() else ([], [])
        self.spm_times, self.sunel_vals = parse_spm(Path(spm_file)) if Path(spm_file).exists() else ([], [])

        self.dark = dark_current
        self.gain = gain
        self.k = k_exponent

        self.logs = open(self.log_txt, "w")

    def log(self, msg):
        line = f"[{datetime.now().isoformat()}] {msg}"
        print(line)
        self.logs.write(line + "\n")

    def process_one(self, tif_path):
        stem = tif_path.stem
        img_time = self.meta.get(stem)
        if img_time is None:
            raise KeyError(f"No start_time for {stem}")

        # Angle calculation
        if self.spm_times and self.oat_times:
            try:
                sun_el = interp_angle(img_time, self.spm_times, self.sunel_vals)
                incidence = 90.0 - sun_el
                emission = interp_angle(img_time, self.oat_times, self.emis_vals)
            except:
                incidence, emission = fallback_angles(self.level0 / f"{stem}.xml")
        else:
            incidence, emission = fallback_angles(self.level0 / f"{stem}.xml")

        angles_json_path = self.base / "logs/angles" / f"{stem}_sun_angles.json"
        angles_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(angles_json_path, 'w') as jf:
            json.dump({
                "image_file": tif_path.name,
                "original_stem": stem,
                "timestamp": img_time.isoformat(),
                "incidence_angle_deg": incidence,
                "emission_angle_deg": emission,
                "sun_elevation_deg": 90 - incidence,
                "angle_source": "interpolated_from_spm_oat" if self.spm_times and self.oat_times else "fallback_from_xml"
            }, jf, indent=4)

        mu0 = max(np.cos(np.deg2rad(incidence)), 1e-6)
        mu = max(np.cos(np.deg2rad(emission)), 1e-6)

        with rasterio.open(str(tif_path)) as src:
            prof = src.profile.copy()
            dn = src.read(1).astype(np.float32)

        arr = (dn - self.dark) * self.gain
        arr = np.clip(arr, 0, None)
        arr_if = arr * (mu0 ** (-self.k)) * (mu ** (self.k - 1))

        out = self.level1 / f"{stem}_if.tif"
        prof.update(dtype=rasterio.float32, compress="lzw")
        with rasterio.open(str(out), "w", **prof) as dst:
            dst.write(arr_if, 1)

        stats = {
            "file": out.name,
            "incidence": incidence,
            "emission": emission,
            "min": float(np.min(arr_if)),
            "max": float(np.max(arr_if)),
            "mean": float(np.mean(arr_if)),
            "std": float(np.std(arr_if)),
            "timestamp": datetime.now().isoformat()
        }

        self.log(f"Processed: {out.name}")
        self.log(f"Incidence: {incidence:.2f} Emission: {emission:.2f}")
        self.log(f"Min: {stats['min']:.4f}, Max: {stats['max']:.4f}, Mean: {stats['mean']:.4f}, Std: {stats['std']:.4f}")

        return stats

    def run(self):
        all_stats = []
        with open(self.log_csv, 'w', newline='') as csvfile, open(self.log_jsonl, 'w') as jsonfile:
            writer = csv.DictWriter(csvfile, fieldnames=['file', 'min', 'max', 'mean', 'std'])
            writer.writeheader()

            for tif in sorted(self.level0.glob("*.tif")):
                try:
                    s = self.process_one(tif)
                    writer.writerow({k: s[k] for k in ['file','min','max','mean','std']})
                    json.dump(s, jsonfile); jsonfile.write("\n")
                    all_stats.append(s)
                except Exception as e:
                    self.log(f"Error: {tif.name} — {e}")

        self.plot_stats(all_stats)
        self.logs.close()

    def plot_stats(self, stats):
        files = [s['file'] for s in stats]
        means = [s['mean'] for s in stats]
        colors = ['green' if 0.05 <= m <= 0.20 else 'red' for m in means]

        plt.figure(figsize=(10, 4))
        plt.bar(files, means, color=colors)
        plt.axhspan(0.05, 0.20, color='yellow', alpha=0.3, label='Target 0.05–0.20')
        plt.xticks(rotation=90, fontsize=6)
        plt.ylabel('Mean I/F')
        plt.title('Per-Image Mean I/F QC')
        plt.legend()
        plt.tight_layout()
        self.bar_png.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(self.bar_png, dpi=150)
        plt.close()

        plt.figure(figsize=(6, 4))
        plt.hist(means, bins=20, color='blue', edgecolor='black')
        plt.axvline(0.05, color='red', linestyle='--')
        plt.axvline(0.20, color='red', linestyle='--')
        plt.xlabel('Mean I/F')
        plt.ylabel('Count')
        plt.title('Distribution of Mean I/F')
        plt.tight_layout()
        plt.savefig(self.hist_png, dpi=150)
        plt.close()

# === CONFIG ===
def run_minnaert_correction(base_dir, process_mode, original_file,config):
    """
    Runs Minnaert correction based on selected processing mode.

    Args:
        base_dir (str): Root project path.
        process_mode (str): "original", "crop", or "both"
        original_file (str): .img filename (used to derive .oat/.spm)
    """
    correction_config = config["minnaert"]
    is_crop = process_mode == "crop"
    is_both = process_mode == "both"

    # Decide metadata CSV based on crop mode
    metadata_csv = os.path.join(base_dir, "logs", 
        "metadata_catalog_cropped.csv" if is_crop else "metadata_catalog.csv"
    )

    # OAT/SPM filenames derived from the original .img name
    base_img_stem = Path(original_file).stem
    oat_file = os.path.join(base_dir, "geometry", f"{base_img_stem}.oat")
    spm_file = os.path.join(base_dir, "geometry", f"{base_img_stem}.spm")

    corrector = MinnaertCorrector(
        base_dir=base_dir,
        metadata_csv=metadata_csv,
        oat_file=oat_file,
        spm_file=spm_file,
        dark_current=correction_config["dark_current"],
        gain=correction_config ["gain"],
        k_exponent=correction_config["k_exponent"]
    )

    print(" Running Minnaert correction...")

    corrector.run()