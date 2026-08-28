"""Lung segmentation + nodule detection - workflow inference entry point (example).

One image, two AI nodes of different categories; the platform injects
--node-id to pick the node:
    stage_seg    (ai_segment): original image -> nnUNet lung mask -> pred.nii.gz
    stage_detect (ai_detect):  lung-filtered ROI -> RetinaNet -> detection.nodules

ROI filtering between the two nodes is a platform node (roi_crop, filter mode);
this script only does pure model inference for whichever node --node-id picks.

This mirrors templates/workflow/docker/predict.py exactly: main() (which
decodes --extra-params into params{}) is the unchanged platform I/O contract;
only the USER EDIT AREA is filled in. Unlike examples/workflow_nnunet (a
generic coarse-to-fine nnUNet template reusable for any organ), this file is
task-specific: the two nodes return different payload shapes (a mask vs. a
target list) and use two different frameworks (nnUNet + MONAI RetinaNet), so
run_inference branches on node_id instead of sharing one stage function.
"""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import SimpleITK as sitk
import torch
from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

from monai.apps.detection.networks.retinanet_detector import RetinaNetDetector
from monai.apps.detection.utils.anchor_utils import AnchorGeneratorWithAnchorShape
from monai.apps.detection.transforms.dictionary import (
    ClipBoxToImaged,
    AffineBoxToWorldCoordinated,
    ConvertBoxModed,
)
from monai.transforms import (
    Compose,
    LoadImaged,
    EnsureChannelFirstd,
    EnsureTyped,
    Orientationd,
    Spacingd,
    ScaleIntensityRanged,
)

# The platform reads this file by default for the segmentation node's mask.
MASK_NAME = "pred.nii.gz"

# ==================== model config (paths inside the image) ====================
# Replace with your own weights; keep these in sync with what you place under
# docker/nnUNet_results/ and docker/model/ (see those folders' READMEs).
SEG_MODEL = {
    "path":       "/workspace/nnUNet_results/Dataset001_MyLungSeg/nnUNetTrainer__nnUNetPlans__3d_fullres",
    "folds":      ("0",),
    "checkpoint": "checkpoint_final.pth",
}
# Detection defaults below follow MONAI's public LUNA16 RetinaNet configuration;
# match them to whatever your own detector was trained with.
DET_MODEL = {
    "path":               "/workspace/model/detector.pt",
    "spacing":            [0.703125, 0.703125, 1.25],
    "score_thresh":       0.05,
    "nms_thresh":         0.22,
    "detections_per_img": 300,
    "feature_map_scales": [1, 2, 4],
    "base_anchor_shapes": [[6, 8, 4], [8, 6, 5], [10, 10, 6]],
    "infer_patch_size":   [512, 512, 192],
}


def prepare_workdir(output_dir: Path, name: str) -> Path:
    workdir = Path(output_dir) / f"_{name}"
    (workdir / "in").mkdir(parents=True, exist_ok=True)
    (workdir / "out").mkdir(parents=True, exist_ok=True)
    return workdir


# ==================== stage_seg (ai_segment) ====================
def build_seg_predictor(use_mirroring: bool) -> nnUNetPredictor:
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
        SEG_MODEL["path"],
        use_folds=SEG_MODEL["folds"],
        checkpoint_name=SEG_MODEL["checkpoint"],
    )
    return predictor


def run_nnunet(predictor, image_path, out_dir):
    """nnUNet expects input named *_0000.nii.gz and outputs a same-named nii.gz."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    predictor.predict_from_files(
        str(image_path.parent),
        str(out_dir),
        save_probabilities=False,
        overwrite=True,
        num_processes_preprocessing=2,
        num_processes_segmentation_export=2,
    )
    return out_dir / "case.nii.gz"


def run_stage_seg(input_path: Path, output_dir: Path, params: dict) -> dict:
    """Original image -> binary lung mask, written to output_dir / MASK_NAME."""
    use_mirroring = bool(params.get("use_mirroring", True))
    print(f"PROGRESS:1:stage_seg params use_mirroring={use_mirroring}")

    print("PROGRESS:5:Loading lung segmentation model...")
    predictor = build_seg_predictor(use_mirroring=use_mirroring)

    workdir = prepare_workdir(output_dir, "LungSeg")
    nnunet_in = workdir / "in" / "case_0000.nii.gz"
    shutil.copy2(input_path, nnunet_in)

    print("PROGRESS:40:Running inference...")
    raw_mask_path = run_nnunet(predictor, nnunet_in, workdir / "out")
    raw_mask = sitk.ReadImage(str(raw_mask_path))

    print("PROGRESS:80:Aligning to input space and binarizing...")
    original = sitk.ReadImage(str(input_path))
    full_mask = sitk.Resample(
        raw_mask, original, sitk.Transform(),
        sitk.sitkNearestNeighbor, 0, raw_mask.GetPixelID(),
    )
    arr = sitk.GetArrayFromImage(full_mask)
    arr[arr > 0] = 1  # only the ROI extent matters downstream
    binary = sitk.GetImageFromArray(arr.astype(np.uint8))
    binary.CopyInformation(full_mask)
    sitk.WriteImage(binary, str(output_dir / MASK_NAME))
    print("PROGRESS:100:stage_seg done")

    return {"segmentation": {}}


# ==================== stage_detect (ai_detect) ====================
def build_det_predictor(score_thresh: float):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    anchor_generator = AnchorGeneratorWithAnchorShape(
        feature_map_scales=DET_MODEL["feature_map_scales"],
        base_anchor_shapes=DET_MODEL["base_anchor_shapes"],
    )
    net = torch.jit.load(DET_MODEL["path"]).to(device)
    detector = RetinaNetDetector(
        network=net, anchor_generator=anchor_generator, debug=False,
    )
    detector.set_box_selector_parameters(
        score_thresh=score_thresh,
        topk_candidates_per_level=1000,
        nms_thresh=DET_MODEL["nms_thresh"],
        detections_per_img=DET_MODEL["detections_per_img"],
    )
    detector.set_sliding_window_inferer(
        roi_size=DET_MODEL["infer_patch_size"],
        overlap=0.25, sw_batch_size=1, mode="gaussian", device="cpu",
    )
    detector.eval()
    return detector, device


def _det_transforms():
    return Compose([
        LoadImaged(keys=["image"], image_only=False,
                   meta_key_postfix="meta_dict",
                   reader="ITKReader", affine_lps_to_ras=True),
        EnsureChannelFirstd(keys=["image"]),
        EnsureTyped(keys=["image"], dtype=torch.float32),
        Orientationd(keys=["image"], axcodes="RAS"),
        Spacingd(keys=["image"], pixdim=DET_MODEL["spacing"], padding_mode="border"),
        ScaleIntensityRanged(keys=["image"], a_min=-1024, a_max=300,
                             b_min=0.0, b_max=1.0, clip=True),
        EnsureTyped(keys=["image"], dtype=torch.float16),
    ])


def _format_nodules(world_boxes: np.ndarray, scores: np.ndarray) -> list:
    """Boxes in world coordinates -> the platform's detection contract.

    center_mm and size_mm are required; confidence is optional and uses a 0-100
    scale. Additional keys may be appended for a plugin's own bookkeeping; the
    platform passes them through without interpreting them.
    """
    out = []
    for i in np.argsort(-scores):
        cx, cy, cz, w, h, d = [float(v) for v in world_boxes[i]]
        out.append({
            "center_mm":  {"x": cx, "y": cy, "z": cz},
            "size_mm":    {"width": w, "height": h, "depth": d},
            "confidence": round(float(scores[i]) * 100, 1),
        })
    return out


def run_stage_detect(input_path: Path, params: dict) -> dict:
    """Lung-filtered ROI image -> RetinaNet detection -> detection.nodules (world coords)."""
    score_thresh = float(params.get("score_thresh", DET_MODEL["score_thresh"]))
    print(f"PROGRESS:5:stage_detect loading model (thresh={score_thresh})...")
    detector, device = build_det_predictor(score_thresh=score_thresh)

    print("PROGRESS:25:Preprocessing...")
    data = _det_transforms()({"image": str(input_path)})
    image_tensor = data["image"]
    meta = data["image_meta_dict"]

    print("PROGRESS:50:Running inference...")
    with torch.no_grad():
        image_input = image_tensor.unsqueeze(0).to(device)
        use_inferer = image_input.numel() > int(np.prod(DET_MODEL["infer_patch_size"]))
        if torch.cuda.is_available():
            with torch.autocast("cuda"):
                outputs = detector([image_input[0]], use_inferer=use_inferer)
        else:
            outputs = detector([image_input[0]], use_inferer=use_inferer)

    boxes  = outputs[0][detector.target_box_key].cpu().numpy()
    scores = outputs[0][detector.pred_score_key].cpu().numpy()
    labels = outputs[0][detector.target_label_key].cpu().numpy()
    print(f"PROGRESS:80:Postprocessing (candidates {len(boxes)})...")

    if len(boxes) == 0:
        nodules = []
    else:
        post = Compose([
            ClipBoxToImaged(box_keys="box",
                            label_keys=["label", "label_scores"],
                            box_ref_image_keys="image", remove_empty=True),
            AffineBoxToWorldCoordinated(box_keys="box",
                                        box_ref_image_keys="image",
                                        affine_lps_to_ras=True),
            ConvertBoxModed(box_keys="box",
                            src_mode="xyzxyz", dst_mode="cccwhd"),
        ])
        post_data = post({
            "box":          torch.tensor(boxes,  dtype=torch.float32),
            "label":        torch.tensor(labels),
            "label_scores": torch.tensor(scores),
            "image":        image_tensor,
            "image_meta_dict": meta,
        })
        world_boxes = post_data["box"].numpy()
        world_scores = (post_data["label_scores"].numpy()
                        if "label_scores" in post_data
                        else scores[:len(world_boxes)])
        nodules = _format_nodules(world_boxes, world_scores)

    print(f"PROGRESS:100:stage_detect done (emitted {len(nodules)} targets)")
    return {"detection": {"nodules": nodules}}


# =============================================================================
# USER EDIT AREA — branch on node_id; each node returns its own payload shape
# =============================================================================
def run_inference(node_id: str, input_path: Path, output_dir: Path,
                  params: dict) -> dict:
    """Route to the node selected by --node-id and return its output.json payload.

    stage_seg (ai_segment) writes output_dir / MASK_NAME and returns
    {"segmentation": {}}, reading use_mirroring. stage_detect (ai_detect)
    writes no mask and returns {"detection": {"nodules": [...]}}, reading
    score_thresh.
    """
    if node_id == "stage_seg":
        return run_stage_seg(input_path, output_dir, params)
    if node_id == "stage_detect":
        return run_stage_detect(input_path, params)
    raise SystemExit(
        f"unknown --node-id {node_id!r}; expected ['stage_seg', 'stage_detect']"
    )
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
