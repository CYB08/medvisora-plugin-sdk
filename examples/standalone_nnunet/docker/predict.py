"""nnUNet single-node segmentation - inference entry point (example).

One AI node, one pass: input image -> nnUNet segmentation mask, aligned to the
input geometry. Which structures the mask represents depends entirely on the
model you place in nnUNet_results/ and the label mapping in
manifest.nodes[*].outputs — this script only runs the model and writes the raw
mask; it has no idea (and does not need to) what it is segmenting.

This mirrors templates/standalone/docker/predict.py exactly: only the USER EDIT
AREA is filled in; main() (which decodes --extra-params into params{}) is the
unchanged platform I/O contract. Reuse this file as-is for any other nnUNet
single-node segmentation task — swap the weights in nnUNet_results/, update
NNUNET_MODEL below if the dataset/trainer name differs, and adjust
plugin/manifest.json's outputs mapping.
"""

import argparse
import json
import shutil
from pathlib import Path

import torch
from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

# The platform reads this file by default for segmentation masks.
MASK_NAME = "pred.nii.gz"

# ==================== model config (paths inside the image) ====================
# Replace with your own dataset/trainer folder name; keep it in sync with the
# weights you place under docker/nnUNet_results/ (see that folder's README).
NNUNET_MODEL = {
    "path":       "/workspace/nnUNet_results/Dataset001_MyOrgans/nnUNetTrainer__nnUNetPlans__3d_fullres",
    "folds":      ("0",),
    "checkpoint": "checkpoint_final.pth",
}


def build_predictor(model_cfg, use_mirroring: bool):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    predictor = nnUNetPredictor(
        tile_step_size=0.5,
        use_gaussian=True,
        use_mirroring=use_mirroring,
        perform_everything_on_device=True,
        device=device,
        verbose=False,
        verbose_preprocessing=False,
        allow_tqdm=True,
    )
    predictor.initialize_from_trained_model_folder(
        model_cfg["path"],
        use_folds=model_cfg["folds"],
        checkpoint_name=model_cfg["checkpoint"],
    )
    return predictor


def run_nnunet(predictor, image_path, out_dir):
    """nnUNet expects input named *_0000.nii.gz and outputs a same-named nii.gz."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Pass a folder path; nnUNet finds *_0000.nii.gz inside and writes to out_dir.
    predictor.predict_from_files(
        str(image_path.parent),
        str(out_dir),
        save_probabilities=False,
        overwrite=True,
        num_processes_preprocessing=2,
        num_processes_segmentation_export=2,
    )
    return out_dir / "case.nii.gz"


def prepare_workdir(output_dir: Path, name: str) -> Path:
    workdir = Path(output_dir) / f"_{name}"
    (workdir / "in").mkdir(parents=True, exist_ok=True)
    (workdir / "out").mkdir(parents=True, exist_ok=True)
    return workdir


# =============================================================================
# USER EDIT AREA — same signature as templates/standalone/docker/predict.py
# =============================================================================
def run_inference(node_id: str, input_path: Path, output_dir: Path,
                  params: dict) -> dict:
    """Input image -> nnUNet segmentation mask, written to output_dir / MASK_NAME.

    nnUNet resamples internally and restores to the input space, keeping the
    model's raw label values; semantic names are assigned by the platform via
    manifest.nodes[*].outputs.
    """
    # The platform always injects use_mirroring; the fallback only applies when
    # the script is launched manually without --extra-params.
    use_mirroring = bool(params.get("use_mirroring", True))
    print(f"PROGRESS:1:inference params use_mirroring={use_mirroring}")

    print("PROGRESS:5:Loading nnUNet model...")
    predictor = build_predictor(NNUNET_MODEL, use_mirroring=use_mirroring)

    workdir = prepare_workdir(output_dir, "NNUNetSeg")
    nnunet_in = workdir / "in" / "case_0000.nii.gz"
    shutil.copy2(input_path, nnunet_in)

    print("PROGRESS:40:Running inference...")
    raw_mask_path = run_nnunet(predictor, nnunet_in, workdir / "out")
    shutil.copy2(raw_mask_path, output_dir / MASK_NAME)
    print("PROGRESS:100:Done")

    return {"segmentation": {}}
# =============================================================================
# END USER EDIT AREA
# =============================================================================


# ----------------------------------------------------------------------------
# Platform I/O contract. Identical in every plugin — do NOT change.
# ----------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-id", default="")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    # All tunable parameters (built-in + manifest.nodes[*].params) arrive as one
    # JSON object, already typed. Adding a new one later never touches this file.
    parser.add_argument("--extra-params", default="{}")
    # parse_known_args tolerates future built-in flags too.
    args, _ = parser.parse_known_args()

    params = json.loads(args.extra_params or "{}")

    output_path = Path(args.output)
    result = run_inference(args.node_id, Path(args.input), output_path.parent, params)

    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
