"""Two-stage lung tumor segmentation - single-node inference entry point (example).

One AI node, one container run, two internal nnUNet stages:
    Stage 1: original image -> binary lung mask, used only to locate the ROI.
    Stage 2: ROI cropped around the lungs -> lung tumor mask, restored back to
             the input's full geometry.

This file packages the entire two-stage process as a SINGLE AI node: cropping
and restoring happen inside run_inference() using plain SimpleITK, not platform
workflow nodes. That is why it is NOT a generic template — the crop margin is
fixed at CROP_MARGIN_MM below instead of being a user-adjustable roi_crop
parameter in the UI. If you need to tune the margin per case without rebuilding
the image, split the two stages into two AI nodes and let the platform's
roi_crop / mask_restore do the work; see examples/workflow_nnunet.

This mirrors templates/standalone/docker/predict.py exactly: only the USER EDIT
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
# Replace with your own dataset/trainer folder names; keep them in sync with the
# weights you place under docker/nnUNet_results/ (see that folder's README).
STAGE1_MODEL = {
    "path":       "/workspace/nnUNet_results/Dataset001_MyOrganCoarse/nnUNetTrainer__nnUNetPlans__3d_fullres",
    "folds":      ("0",),
    "checkpoint": "checkpoint_final.pth",
}
STAGE2_MODEL = {
    "path":       "/workspace/nnUNet_results/Dataset002_MyLesionFine/nnUNetTrainer__nnUNetPlans__3d_fullres",
    "folds":      ("0",),
    "checkpoint": "checkpoint_best.pth",
}

# ROI margin around the stage-1 mask, in mm (x, y, z). Standalone mode has no
# roi_crop UI control, so the margin is fixed here; tune it for the task at
# hand and rebuild the image.
CROP_MARGIN_MM = (10.0, 10.0, 10.0)


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


def crop_by_mask(image: sitk.Image, mask: sitk.Image, margin_mm) -> tuple:
    """Crop image to a margin-padded bounding box around mask's nonzero region.

    Same bbox-crop behavior as the platform's built-in roi_crop node, just run
    locally instead of as a separate workflow node.
    """
    mask_arr = sitk.GetArrayFromImage(mask)
    nonzero = np.nonzero(mask_arr)
    if len(nonzero[0]) == 0:
        raise RuntimeError("stage-1 lung mask is empty; cannot crop ROI for stage 2")

    z_min, z_max = int(nonzero[0].min()), int(nonzero[0].max())
    y_min, y_max = int(nonzero[1].min()), int(nonzero[1].max())
    x_min, x_max = int(nonzero[2].min()), int(nonzero[2].max())

    pt_min = mask.TransformIndexToPhysicalPoint((x_min, y_min, z_min))
    pt_max = mask.TransformIndexToPhysicalPoint((x_max, y_max, z_max))
    idx_min = image.TransformPhysicalPointToIndex(pt_min)
    idx_max = image.TransformPhysicalPointToIndex(pt_max)

    spacing = image.GetSpacing()
    size = image.GetSize()
    margin_px = [max(0, int(round(margin_mm[i] / spacing[i]))) for i in range(3)]

    bbox = {
        "x_start": max(0,       idx_min[0] - margin_px[0]),
        "x_end":   min(size[0], idx_max[0] + margin_px[0]),
        "y_start": max(0,       idx_min[1] - margin_px[1]),
        "y_end":   min(size[1], idx_max[1] + margin_px[1]),
        "z_start": max(0,       idx_min[2] - margin_px[2]),
        "z_end":   min(size[2], idx_max[2] + margin_px[2]),
    }
    cropped = image[
        bbox["x_start"]:bbox["x_end"],
        bbox["y_start"]:bbox["y_end"],
        bbox["z_start"]:bbox["z_end"],
    ]
    return bbox, cropped


def restore_mask(cropped_mask: sitk.Image, bbox: dict, ref_image: sitk.Image) -> sitk.Image:
    """Place a cropped-space mask back into ref_image's full geometry."""
    ref_cropped = ref_image[
        bbox["x_start"]:bbox["x_end"],
        bbox["y_start"]:bbox["y_end"],
        bbox["z_start"]:bbox["z_end"],
    ]
    aligned = sitk.Resample(
        cropped_mask, ref_cropped, sitk.Transform(),
        sitk.sitkNearestNeighbor, 0, cropped_mask.GetPixelID(),
    )
    aligned_arr = sitk.GetArrayFromImage(aligned).astype(np.uint8)

    full = np.zeros(sitk.GetArrayFromImage(ref_image).shape, dtype=np.uint8)
    full[
        bbox["z_start"]:bbox["z_end"],
        bbox["y_start"]:bbox["y_end"],
        bbox["x_start"]:bbox["x_end"],
    ] = aligned_arr

    restored = sitk.GetImageFromArray(full)
    restored.CopyInformation(ref_image)
    return restored


# =============================================================================
# USER EDIT AREA — same signature as templates/standalone/docker/predict.py
# =============================================================================
def run_inference(node_id: str, input_path: Path, output_dir: Path,
                  params: dict) -> dict:
    """Coarse lung localization -> crop ROI -> fine tumor segmentation -> restore.

    Single AI node; node_id is ignored (only one node in this plugin). Both
    stages read the same use_mirroring value; how much it changes the result
    depends on how each checkpoint was trained.
    """
    use_mirroring = bool(params.get("use_mirroring", True))
    print(f"PROGRESS:1:inference params use_mirroring={use_mirroring}")

    original = sitk.ReadImage(str(input_path))

    print("PROGRESS:5:Stage1 loading lung model...")
    stage1_predictor = build_predictor(STAGE1_MODEL, use_mirroring=use_mirroring)
    workdir1 = prepare_workdir(output_dir, "Stage1")
    nnunet_in1 = workdir1 / "in" / "case_0000.nii.gz"
    # nnUNet resamples internally per plans.json; just copy the original image.
    shutil.copy2(input_path, nnunet_in1)

    print("PROGRESS:20:Stage1 running inference...")
    raw_lung_path = run_nnunet(stage1_predictor, nnunet_in1, workdir1 / "out")
    raw_lung_mask = sitk.ReadImage(str(raw_lung_path))

    print("PROGRESS:35:Stage1 aligning to input space and binarizing...")
    lung_mask = sitk.Resample(
        raw_lung_mask, original, sitk.Transform(),
        sitk.sitkNearestNeighbor, 0, raw_lung_mask.GetPixelID(),
    )
    lung_arr = sitk.GetArrayFromImage(lung_mask)
    lung_arr[lung_arr > 0] = 1  # only the ROI extent matters downstream
    lung_mask = sitk.GetImageFromArray(lung_arr.astype(np.uint8))
    lung_mask.CopyInformation(original)

    print("PROGRESS:40:Cropping ROI around the lungs...")
    bbox, cropped = crop_by_mask(original, lung_mask, CROP_MARGIN_MM)

    print("PROGRESS:50:Stage2 loading tumor model...")
    stage2_predictor = build_predictor(STAGE2_MODEL, use_mirroring=use_mirroring)
    workdir2 = prepare_workdir(output_dir, "Stage2")
    nnunet_in2 = workdir2 / "in" / "case_0000.nii.gz"
    sitk.WriteImage(cropped, str(nnunet_in2))

    print("PROGRESS:70:Stage2 running inference...")
    raw_tumor_path = run_nnunet(stage2_predictor, nnunet_in2, workdir2 / "out")
    tumor_mask_cropped = sitk.ReadImage(str(raw_tumor_path))

    print("PROGRESS:90:Restoring tumor mask to input space...")
    tumor_mask = restore_mask(tumor_mask_cropped, bbox, original)
    sitk.WriteImage(tumor_mask, str(output_dir / MASK_NAME))
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
