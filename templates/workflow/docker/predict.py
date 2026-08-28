"""Workflow inference entry point (template).

One image, multiple AI nodes. The platform injects --node-id to pick the stage:
    stage_a : full image (optionally resampled by the canvas) -> coarse mask
    stage_b : cropped ROI (from roi_crop)                     -> fine mask

Only edit the stage functions and STAGE_ROUTES. Everything else — including
main() — is the SAME fixed platform I/O contract as templates/standalone,
identical in every plugin. Do not change it.

Contract (see docs/contract.md): each stage reads --input, writes its mask as
pred.nii.gz into output_dir (the platform reads this filename by default; use
a different name only if you also set output.json's segmentation.mask_path),
and returns {"segmentation": {}}. All tunable parameters arrive packed into
one JSON object via --extra-params; read only what a given stage needs from
params{}.
"""

import argparse
import json
from pathlib import Path


# =============================================================================
# USER EDIT AREA — implement one function per stage, then route on node_id
# =============================================================================
def run_stage_a(input_path: Path, output_dir: Path, params: dict) -> dict:
    """Coarse stage: input image -> binary mask written to output_dir / "pred.nii.gz"."""
    raise NotImplementedError("Implement stage_a inference.")


def run_stage_b(input_path: Path, output_dir: Path, params: dict) -> dict:
    """Fine stage: cropped ROI image -> fine mask written to output_dir / "pred.nii.gz"."""
    raise NotImplementedError("Implement stage_b inference.")


# node-id -> stage function. Keys MUST match manifest.nodes[*].id.
STAGE_ROUTES = {
    "stage_a": run_stage_a,
    "stage_b": run_stage_b,
}


def run_inference(node_id: str, input_path: Path, output_dir: Path,
                  params: dict) -> dict:
    """Route to the stage selected by --node-id and return its output.json payload."""
    if node_id not in STAGE_ROUTES:
        raise SystemExit(f"unknown --node-id {node_id!r}; expected {list(STAGE_ROUTES)}")
    return STAGE_ROUTES[node_id](input_path, output_dir, params)
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
