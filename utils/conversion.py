# file: pds4_to_tiff_converter.py

from osgeo import gdal
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import rasterio
import json
from datetime import datetime

class PDS4toTIFFConverter:
    def __init__(self, input_dir, output_dir_full, output_dir_vis, log_path, provenance_path,visual_dir):
        self.input_dir = Path(input_dir)
        self.output_dir_full = Path(output_dir_full)
        self.output_dir_vis = Path(output_dir_vis)
        self.log_path = Path(log_path)
        self.provenance_path = Path(provenance_path)
        self.visual_dir = Path(visual_dir)

        self.output_dir_full.mkdir(exist_ok=True, parents=True)
        self.output_dir_vis.mkdir(exist_ok=True, parents=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.provenance_path.parent.mkdir(parents=True, exist_ok=True)
        self.visual_dir.mkdir(exist_ok=True, parents=True)
        self.log_file = open(self.log_path, 'w')

    def log(self, message):
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] {message}"
        print(line)
        self.log_file.write(line + "\n")

    def save_provenance(self, provenance_dict):
        with open(self.provenance_path, 'a') as f:
            json.dump(provenance_dict, f)
            f.write("\n")

    def convert_all(self):
        img_files = list(self.input_dir.glob("*.img"))
        if not img_files:
            self.log(" No .img files found.")
            return

        for img_file in img_files:
            base_name = img_file.stem
            full_tiff = self.output_dir_full / f"{base_name}.tif"
            vis_tiff = self.output_dir_vis / f"{base_name}_vis.tif"
            self.convert_single(img_file, full_tiff, vis_tiff)

        self.log(" All files processed.")
        self.log_file.close()

    def convert_single(self, img_path, full_tiff, vis_tiff):
        self.log(f" Converting: {img_path.name}")
        xml_path = img_path.with_suffix('.xml')
        ds = gdal.Open(str(xml_path))

        if ds is None:
            self.log(f" GDAL failed to open {xml_path.name}")
            return

        try:
            # Full-resolution GeoTIFF (for DEM)
            gdal.Translate(str(full_tiff), ds, format='GTiff',
                creationOptions=["COMPRESS=LZW", "TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256"])

            # Downsampled version (5%) for visualization
            gdal.Translate(str(vis_tiff), ds, format='GTiff',
                widthPct=5, heightPct=5, creationOptions=["COMPRESS=LZW"])

            self.log(f" Visual saved: {vis_tiff.name}")

            self.visualize_tiff(vis_tiff)

            # Provenance
            provenance = {
                "input_file": str(img_path.name),
                "input_xml": str(xml_path.name),
                "output_full": str(full_tiff.name),
                "output_vis": str(vis_tiff.name),
                "compression": "LZW",
                "tiled": True,
                "tile_size": [256, 256],
                "gdal_version": gdal.VersionInfo("--version"),
                "conversion_time": datetime.now().isoformat(),
                "status": "success"
            }
            self.save_provenance(provenance)

        except Exception as e:
            self.log(f" Error converting {img_path.name}: {e}")
            self.save_provenance({
                "input_file": str(img_path.name),
                "error": str(e),
                "status": "failed",
                "conversion_time": datetime.now().isoformat()
            })

    def visualize_tiff(self, tiff_path):
        try:
            with rasterio.open(tiff_path) as src:
                image = src.read(1)
                vmin, vmax = np.percentile(image, [2, 98])
        
                plt.figure(figsize=(10, 5), dpi=140)
                plt.title(f"Preview: {tiff_path.name}")
                plt.imshow(image, cmap='gray', vmin=vmin, vmax=vmax)
                plt.axis("off")
                plt.tight_layout()
                plt.savefig(self.visual_dir / f"{tiff_path.stem}_preview.png", dpi=150)
                plt.show()

                plt.figure(figsize=(6, 3), dpi=140)
                plt.hist(image.ravel(), bins=256, color='black', histtype='step')
                plt.title("Histogram")
                plt.xlabel("Value")
                plt.ylabel("Frequency")
                plt.tight_layout()
                plt.savefig(self.visual_dir / f"{tiff_path.stem}_histogram.png", dpi=150)
                plt.show()

                self.log(f" Dimensions: {src.width} x {src.height}")
                self.log(f" Data type: {image.dtype}")
                self.log(f" Pixel range: min={image.min()} max={image.max()}")

        except Exception as e:
            self.log(f" Visualization failed: {e}")


def run_conversion(basedir):
    from utils.conversion import PDS4toTIFFConverter
    import os

    input_dir = os.path.join(basedir, "raw", "img")
    output_dir_full = os.path.join(basedir, "processed", "level0")
    output_dir_vis = os.path.join(basedir, "processed", "level0_vis")
    log_path = os.path.join(basedir, "logs", "conversion.log")
    provenance_path = os.path.join(basedir, "config", "conversion_provenance.jsonl")
    visual_dir = os.path.join(basedir, "visuals", "conversion")
    converter = PDS4toTIFFConverter(
        input_dir,
        output_dir_full,
        output_dir_vis,
        log_path,
        provenance_path,
        visual_dir
    )

    converter.convert_all()