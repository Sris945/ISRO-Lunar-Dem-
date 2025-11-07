# file: metadata_extractor.py

import xml.etree.ElementTree as ET
import csv
import json
from pathlib import Path
from datetime import datetime

class metadata_extractor:
    def __init__(self, base_dir: str = "TMC2_Project"):
        self.base = Path(base_dir)
        self.xml_dir = self.base / "raw/xml"
        self.out_csv = self.base / "logs/metadata_catalog.csv"
        self.log_file = self.base / "logs/metadata_extraction.log"
        self.provenance_path = self.base / "config/metadata_provenance.jsonl"
        self.namespaces = {
            'pds': 'http://pds.nasa.gov/pds4/pds/v1',
            'isda': 'https://isda.issdc.gov.in/pds4/isda/v1'
        }

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.provenance_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = open(self.log_file, 'w')

    def _log(self, msg):
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] {msg}"
        print(line)
        self.log.write(line + "\n")

    def extract_metadata(self, xml_path: Path) -> dict:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        meta = {}

        try:
            meta["file_name"] = root.findtext(".//pds:file_name", namespaces=self.namespaces)
            meta["md5"] = root.findtext(".//pds:md5_checksum", namespaces=self.namespaces)
            meta["start_time"] = root.findtext(".//pds:start_date_time", namespaces=self.namespaces)
            meta["stop_time"] = root.findtext(".//pds:stop_date_time", namespaces=self.namespaces)
            meta["pixel_resolution"] = root.findtext(".//isda:pixel_resolution", namespaces=self.namespaces)
            meta["sun_azimuth"] = root.findtext(".//isda:sun_azimuth", namespaces=self.namespaces)
            meta["sun_elevation"] = root.findtext(".//isda:sun_elevation", namespaces=self.namespaces)
            meta["roll"] = root.findtext(".//isda:roll", namespaces=self.namespaces)
            meta["pitch"] = root.findtext(".//isda:pitch", namespaces=self.namespaces)
            meta["yaw"] = root.findtext(".//isda:yaw", namespaces=self.namespaces)
            meta["ul_lat"] = root.findtext(".//isda:Refined_Corner_Coordinates/isda:upper_left_latitude", namespaces=self.namespaces)
            meta["ul_lon"] = root.findtext(".//isda:Refined_Corner_Coordinates/isda:upper_left_longitude", namespaces=self.namespaces)

        except Exception as e:
            raise RuntimeError(f"XML parse failed: {e}")

        return meta

    def save_provenance(self, meta_dict):
        meta_dict["extracted_at"] = datetime.now().isoformat()
        with open(self.provenance_path, 'a') as f:
            json.dump(meta_dict, f)
            f.write("\n")

    def run(self):
        xml_files = sorted(self.xml_dir.glob("*.xml"))
        total, success, failed = len(xml_files), 0, 0

        self._log(f" Found {total} XML files to extract.")
        with open(self.out_csv, 'w', newline='') as csvfile:
            writer = None
            for xml_file in xml_files:
                try:
                    meta = self.extract_metadata(xml_file)
                    if writer is None:
                        writer = csv.DictWriter(csvfile, fieldnames=meta.keys())
                        writer.writeheader()
                    writer.writerow(meta)
                    self.save_provenance(meta)
                    self._log(f" Extracted: {xml_file.name}")
                    success += 1
                except Exception as e:
                    self._log(f" Failed: {xml_file.name} — {e}")
                    self.save_provenance({
                        "file_name": xml_file.name,
                        "status": "failed",
                        "error": str(e),
                        "extracted_at": datetime.now().isoformat()
                    })
                    failed += 1

        self.log.write("\n--- SUMMARY ---\n")
        self.log.write(f"Total XML files: {total}\n")
        self.log.write(f" Successful: {success}\n")
        self.log.write(f" Failed: {failed}\n")
        self.log.close()
        print(f"\n Metadata CSV saved to: {self.out_csv}")
        print(f" Log saved to: {self.log_file}")
        print(f" Provenance saved to: {self.provenance_path}")


# Run this script
def run_metadata_extraction(project_dir: str):
    from utils.meta_extc import metadata_extractor
    extractor = metadata_extractor(project_dir)
    extractor.run()
