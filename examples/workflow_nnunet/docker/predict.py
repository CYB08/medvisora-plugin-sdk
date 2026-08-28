"""nnUNet two-stage segmentation - workflow inference entry point (example).

Two AI nodes sharing one image; the platform injects --node-id to route:
    stage_coarse : image (optionally resampled by the platform's `resample`
                   node) -> coarse mask, used only by the platform's
                   `roi_crop` node to locate the ROI for stage 2.
    stage_fine   : ROI image (cropped by `roi_crop`) -> fine segmentation
                   mask, later restored to the original space by the
                   platform's `mask_restore` node.

Unlike examples/standalone_lung_tumor_nnunet (the same coarse-to-fine pattern
packaged as a single AI node, with cropping/restoring done manually inside the
container), this file delegates resampling, cropping and restoring entirely to
platform workflow nodes -- predict.py only ever does "image -> mask" for
whichever stage --node-id selects, exactly like a single-stage nnUNet run.
That is what makes it reusable for any coarse-to-fine nnUNet task: swap the
weights in STAGE_MODELS, adjust plugin/manifest.json's default_workflow to fit
your organ (resample spacing, crop margins, node titles, outputs mapping),
and this file needs no further changes.

This mirrors templates/workflow/docker/predict.py exactly: only the USER EDIT
AREA is filled in; main() (which decodes --extra-params into params{}) is the
unchanged platform I/O contract.
"""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import SimpleITK as sitk
import torch
from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

# The platform reads this file by default for segmentation masks.
MASK_NAME = "pred.nii.gz"

# ==================== model config (paths inside the image) ====================
# Replace with your own dataset/trainer folder names; keep them in sync with
# the weights you place under docker/nnUNet_results/ (see that folder's README).
# Keys MUST match manifest.nodes[*].id.
STAGE_MODELS = {
    "stage_coarse": {
        "path":       "/workspace/nnUNet_results/Dataset001_MyTaskCoarse/nnUNetTrainer__nnUNetPlans__3d_fullres",
        "folds":      ("0",),
        "checkpoint": "checkpoint_best.pth",
        # The coarse stage only needs to locate the ROI for roi_crop, so its
        # (possibly multi-label) raw output is merged into one binary mask.
        # Set to False if a stage's output should pass through unchanged.
        "binarize":   True,
    },
    "stage_fine": {
        "path":       "/workspace/nnUNet_results/Dataset002_MyTaskFine/nnUNetTrainer__nnUNetPlans__3d_fullres",
        "folds":      ("0",),
        "checkpoint": "checkpoint_best.pth",
        "binarize":   False,
    },
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
# USER EDIT AREA — one stage function shared by both nodes, routed on node_id
# =============================================================================
def run_stage(stage_id: str, input_path: Path, output_dir: Path,
              params: dict) -> dict:
    """Run one nnUNet stage: image -> mask written to output_dir / MASK_NAME.

    Both stages share this function because the only difference between them
    is which weights to load and whether to binarize the output (see
    STAGE_MODELS). The platform's resample/roi_crop/mask_restore nodes handle
    aligning stage_coarse's mask to stage_fine's crop and restoring
    stage_fine's mask to the original space, so this stays plain "image in,
    mask out" no matter which stage --node-id selects.
    """
    model_cfg = STAGE_MODELS[stage_id]
    use_mirroring = bool(params.get("use_mirroring", True))
    print(f"PROGRESS:1:{stage_id} params use_mirroring={use_mirroring}")

    print(f"PROGRESS:5:{stage_id} loading model...")
    predictor = build_predictor(model_cfg, use_mirroring=use_mirroring)

    workdir = prepare_workdir(output_dir, stage_id)
    nnunet_in = workdir / "in" / "case_0000.nii.gz"
    shutil.copy2(input_path, nnunet_in)

    print(f"PROGRESS:40:{stage_id} running inference...")
    raw_mask_path = run_nnunet(predictor, nnunet_in, workdir / "out")

    if model_cfg["binarize"]:
        print(f"PROGRESS:90:{stage_id} binarizing...")
        raw_mask = sitk.ReadImage(str(raw_mask_path))
        arr = sitk.GetArrayFromImage(raw_mask)
        arr[arr > 0] = 1
        binary = sitk.GetImageFromArray(arr.astype(np.uint8))
        binary.CopyInformation(raw_mask)
        sitk.WriteImage(binary, str(output_dir / MASK_NAME))
    else:
        shutil.copy2(raw_mask_path, output_dir / MASK_NAME)
    print(f"PROGRESS:100:{stage_id} done")

    return {"segmentation": {}}


def run_inference(node_id: str, input_path: Path, output_dir: Path,
                  params: dict) -> dict:
    """Route to the stage selected by --node-id and return its output.json payload."""
    if node_id not in STAGE_MODELS:
        raise SystemExit(f"unknown --node-id {node_id!r}; expected {list(STAGE_MODELS)}")
    return run_stage(node_id, input_path, output_dir, params)
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
