import argparse
import os
import logging
from pathlib import Path
import json
from utils.dir_setup import setup_project_structure
from utils.data_importer import copy_raw_and_geometry_files
from utils.meta_extc import metadata_extractor
from utils.conversion import run_conversion
from utils.albedo import run_albedo_correction
from utils.shadow import run_shadow_detection
from utils.correction import run_minnaert_correction
from utils.package_phase1 import package_phase1_outputs as package_phase1
from utils.cropper import crop_image

def load_config():
    config_path = Path("config/config.json")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        return json.load(f)

def run_pipeline(args):
    base_dir = args.base_dir
    project = args.project
    root_dir_name = args.root_dir
    process_mode = args.process_mode
    original_tif = args.original_tif_name
    project_path = os.path.join(base_dir, project)

    # Setup logging
    log_dir = os.path.join(project_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_dir, "pipeline.log"),
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logging.info("Starting Phase 1 Pipeline")
    config = load_config()

    try:
        logging.info("Step 1: Setting up project structure")
        setup_project_structure(base_dir, project)

        logging.info("Step 2: Copying raw and geometry files")
        copy_raw_and_geometry_files(base_dir, project, root_dir_name)

        logging.info("Step 3: Extracting metadata")
        extractor = metadata_extractor(project_path)
        extractor.run()

        logging.info("Step 4: Converting .img files to .tif")
        run_conversion(project_path)

        if process_mode in ["crop", "both"]:
            logging.info("Step 5: Cropping image")
            crop_coords = tuple(map(int, args.crop_coords.split(",")))
            crop_image(project_path, original_tif, crop_coords, crop_name=args.crop_name)

        logging.info("Step 6: Running Minnaert correction")
        run_minnaert_correction(project_path, process_mode, original_tif, config)

        logging.info("Step 7: Running Albedo Normalization")
        image_stems = []
        if process_mode in ["original", "both"]:
            image_stems.append(Path(original_tif).stem.replace(".img", ""))
        if process_mode in ["crop", "both"]:
            image_stems.append(Path(args.crop_name).stem.replace(".tif", ""))
        for stem in image_stems:
            run_albedo_correction(project_path, stem, config)

        logging.info("Step 8: Shadow detection")
        run_shadow_detection(project_path, config)

        logging.info("Step 9: Packaging Phase 1 outputs")
        package_phase1(project_path, image_stems)

        logging.info(" Pipeline completed successfully")

        # Optional: Auto open folder
        try:
            import platform
            if platform.system() == "Windows":
                os.startfile(project_path)
            elif platform.system() == "Darwin":
                os.system(f"open {project_path}")
            elif platform.system() == "Linux":
                os.system(f"xdg-open {project_path}")
        except Exception as e:
            logging.warning(f"Auto-open failed: {e}")

    except Exception as e:
        logging.exception(f"Pipeline failed: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TMC-2 Phase 1 Processing Pipeline")
    parser.add_argument("--base_dir", required=True, help="Base directory for projects")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--root_dir", required=True, help="Original root dir name to copy data from")
    parser.add_argument("--process_mode", choices=["original", "crop", "both"], default="original",
                        help="Choose processing path: only original, only crop, or both")
    parser.add_argument("--original_tif_name", default="",
                        help="Name of the .tif file in level0 to crop (used in crop/both modes)")
    parser.add_argument("--crop_coords", default="",
                        help="Crop coordinates: xmin,ymin,xmax,ymax (used in crop/both modes)")
    parser.add_argument("--crop_name", default="cropped_image.tif",
                        help="Output cropped .tif filename (optional)")
    args = parser.parse_args()

    run_pipeline(args)
