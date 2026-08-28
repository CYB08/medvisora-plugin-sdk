"""Standalone inference entry point (template).

The platform launches this script once per AI node:
    python /workspace/predict.py --node-id <id> --input <nii.gz> --output <output.json>

Only edit run_inference(). Everything below the USER EDIT AREA — including
main() — is the fixed platform I/O contract, identical in every MedVisora
plugin (this template, the workflow template, and all examples). Do not
change it.

Contract (see docs/contract.md):
    - Segmentation: write the mask as pred.nii.gz into output_dir, return {"segmentation": {}}.
    - Detection:    return {"detection": {"nodules": [...]}} (center_mm/size_mm required).
    - Built-ins:    all tunable parameters (--use-mirroring for ai_segment,
                    --score-thresh for ai_detect, plus anything you declare in
                    manifest.nodes[*].params) arrive packed into ONE JSON object
                    via --extra-params. main() decodes it into params{} verbatim
                    (already correctly typed — bool/float/str); ignore what you
                    don't need. This also means adding a new tunable later never
                    requires touching predict.py.
"""

import argparse
import json
from pathlib import Path


# =============================================================================
# USER EDIT AREA — implement your inference below
# =============================================================================
def run_inference(node_id: str, input_path: Path, output_dir: Path,
                  params: dict) -> dict:
    """Run the full inference pipeline and return the output.json payload.

    Args:
        node_id:    the AI node id; single-node plugins can ignore it.
        input_path: absolute path to the input .nii.gz.
        output_dir: folder where pred.nii.gz (and output.json) live.
        params:     decoded --extra-params. The platform always injects
                    "use_mirroring" (ai_segment) or "score_thresh" (ai_detect),
                    plus anything declared in manifest.nodes[*].params, and
                    "selected_outputs" (list of model output values) when the
                    user narrowed down the structures to keep. Read what this
                    node needs via params.get(key, default) and ignore the rest.

    Progress may be reported at any point; PYTHONUNBUFFERED=1 is set in the
    Dockerfile so the platform picks the lines up immediately:

        print("PROGRESS:40:Running inference")

    Returns:
        A dict written verbatim to output.json. Examples:

        Segmentation (write the mask to output_dir / "pred.nii.gz" first; the
        platform reads this filename by default, or set mask_path below to
        use a different one):
            # sitk.WriteImage(mask, str(output_dir / "pred.nii.gz"))
            return {"segmentation": {}}
            # return {"segmentation": {"mask_path": "your_name.nii.gz"}}

        Instance segmentation (declare instance: true in the manifest, write the
        reserved instance labels into the mask and report their semantics):
            return {"segmentation": {
                "instance": True,
                "labels": [{"label": 1000, "semantic": "Instance 1"}],
            }}

        Detection:
            return {"detection": {"nodules": [
                {
                    # physical coordinates of the input image, in mm; required
                    "center_mm": {"x": 12.5, "y": -33.0, "z": 88.2},
                    "size_mm":   {"width": 8.1, "height": 7.6, "depth": 9.0},
                    "confidence": 87.0,   # optional, 0-100
                },
            ]}}
    """
    raise NotImplementedError("Implement your model inference in run_inference().")
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
