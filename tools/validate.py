#!/usr/bin/env python3
"""Offline validator for a MedVisora plugin manifest (spec v1.0).

Standalone and dependency-free: it checks the registration requirements and the
workflow structure, so you can catch problems before building/shipping.

Usage:
    python validate.py path/to/manifest.json      # validate a JSON file
    python validate.py path/to/plugin_folder      # validate a folder that contains manifest.json

Exit code 0 = valid, 1 = invalid, 2 = usage/IO error.
"""

import json
import os
import re
import sys
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple

# Label regions defined by the plugin spec:
#   0-999      system presets        -- the only range static `outputs` may claim; the
#                                       display name is built-in, so `semantic` must be
#                                       omitted. The id must already exist in the
#                                       platform's label table; this script checks the
#                                       range only and registration checks membership
#   1000-1099  instance segmentation -- reserved for instance labels, which are assigned
#                                       at runtime, so nothing static may live here
#   1100-1199  manual drawing        -- belongs to the end user
SYSTEM_LABEL_MAX = 999
INSTANCE_LABEL_MIN = 1000
INSTANCE_LABEL_MAX = 1099
MANUAL_LABEL_MIN = 1100

_BASE_KINDS = {
    "image_input", "resample", "roi_crop", "mask_restore", "radiomics",
    "display_output", "image_export",
}
_AI_CATEGORIES = ("ai_segment", "ai_detect")
_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Ports of the built-in workflow nodes, as documented in docs/nodes.md.
_BASE_PORTS = {
    "image_input":    ({}, {"image": "image"}),
    "resample":       ({"image": "image"}, {"image": "image"}),
    "roi_crop":       ({"image": "image", "mask": "mask"},
                       {"image": "image", "bbox": "bbox"}),
    "mask_restore":   ({"mask": "mask", "bbox": "bbox"}, {"mask": "mask"}),
    "radiomics":      ({"image": "image", "mask": "mask"}, {"metrics": "metrics"}),
    "display_output": ({"mask": "mask", "detections": "detection",
                        "metrics": "metrics"}, {}),
    "image_export":   ({"image": "image"}, {}),
}
_REQUIRED_INPUTS = {
    "resample": {"image"},
    "ai_segment": {"image"},
    "ai_detect": {"image"},
    "roi_crop": {"image", "mask"},
    "mask_restore": {"mask", "bbox"},
    "radiomics": {"image", "mask"},
    "image_export": {"image"},
}


def _is_intish(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return True
    if isinstance(v, str):
        try:
            int(v.strip())
            return True
        except ValueError:
            return False
    return False


def validate_manifest(manifest: dict, plugin_dir: str = "") -> Tuple[bool, List[str]]:
    """Return (ok, errors). All problems are collected, not just the first."""
    errors: List[str] = []

    if not isinstance(manifest, dict):
        return False, ["manifest top level must be a JSON object"]

    # 1. Top-level required fields
    for field in ("key", "name", "version"):
        val = manifest.get(field)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"top-level '{field}' must be a non-empty string")
    key = manifest.get("key")
    if isinstance(key, str) and key.strip() and not _KEY_RE.fullmatch(key.strip()):
        errors.append("top-level 'key' may only contain letters, digits, '_', '-', '.'")

    task = manifest.get("task")
    if not isinstance(task, list) or not task:
        errors.append('top-level \'task\' must be a non-empty array, e.g. ["segmentation"]')
        task = []
    elif not all(isinstance(item, str) and item.strip() for item in task):
        errors.append("top-level 'task' entries must be non-empty strings")

    # This SDK documents the segmentation/detection contract (see
    # docs/contract.md); those plugins are described by the node graph checked
    # below. Rendering plugins run as a single unit and declare no AI nodes.
    has_node_graph = "rendering" not in set(task)

    # 2. docker config. Every plugin is a docker image.
    docker = manifest.get("docker")
    if not isinstance(docker, dict) or not str(docker.get("image", "")).strip():
        errors.append("docker.image missing: a plugin must declare an image name")
    elif not isinstance(docker.get("image"), str):
        errors.append("docker.image must be a non-empty string")

    # 3. nodes (AI node declarations)
    nodes = manifest.get("nodes")
    if not isinstance(nodes, list):
        if has_node_graph:
            errors.append("nodes missing: a segmentation/detection plugin needs >=1 AI node")
        nodes = []
    elif has_node_graph and not nodes:
        errors.append("nodes empty: a segmentation/detection plugin needs >=1 AI node")

    ai_node_categories: Dict[str, str] = {}
    seen_ids = set()
    for i, node in enumerate(nodes):
        loc = f"nodes[{i}]"
        if not isinstance(node, dict):
            errors.append(f"{loc} must be an object")
            continue

        category = node.get("category")
        if category not in _AI_CATEGORIES:
            errors.append(f"{loc}.category invalid: {category!r} (use ai_segment or ai_detect)")

        nid = node.get("id")
        if not isinstance(nid, str) or not nid.strip():
            errors.append(f"{loc}.id missing: an AI node must declare a unique id")
        else:
            nid = nid.strip()
            if not _NODE_ID_RE.fullmatch(nid):
                errors.append(
                    f"{loc}.id invalid: use only letters, digits, '_' and '-' "
                    "(dots are reserved for workflow port references)"
                )
            if nid in _BASE_KINDS or nid in _AI_CATEGORIES:
                errors.append(f"{loc}.id conflicts with built-in node kind: {nid!r}")
            if nid in seen_ids:
                errors.append(f"{loc}.id duplicated: {nid!r}")
            else:
                seen_ids.add(nid)
                if category in _AI_CATEGORIES:
                    ai_node_categories[nid] = category

        if not isinstance(node.get("title"), str) or not node["title"].strip():
            errors.append(f"{loc}.title missing: an AI node must declare a display title")

        if category == "ai_detect" and node.get("outputs") is not None:
            errors.append(f"{loc}.outputs is only supported by ai_segment nodes")
        else:
            _validate_outputs(node.get("outputs"), loc, errors)
        _validate_instance(node, loc, errors)
        _validate_params(node.get("params"), loc, errors)
        args = node.get("args")
        if args is not None and (
            not isinstance(args, list)
            or not all(isinstance(arg, str) and arg for arg in args)
        ):
            errors.append(f"{loc}.args, if declared, must be an array of non-empty strings")

    # 4. workflow definition is optional, even with multiple AI nodes.
    # Without a default_workflow / workflow.json, each AI node shows up as a
    # standalone node on the canvas for the user to wire up and save manually.
    # Only a single-AI-node plugin can be auto-run from the model card directly.
    has_external_wf = bool(plugin_dir) and os.path.isfile(
        os.path.join(plugin_dir, "workflow.json")
    )

    # 5. workflow structure (inline first, else external workflow.json)
    wf = manifest.get("default_workflow")
    if wf is not None and not isinstance(wf, dict):
        errors.append("default_workflow must be an object")
        wf = None
    if wf is None and has_external_wf:
        wf_path = os.path.join(plugin_dir, "workflow.json")
        try:
            with open(wf_path, "r", encoding="utf-8") as f:
                wf = json.load(f)
        except (OSError, ValueError) as e:
            errors.append(f"workflow.json parse failed: {e}")
            wf = None
        if wf is not None and not isinstance(wf, dict):
            errors.append("workflow.json top level must be an object")
            wf = None
    if isinstance(wf, dict):
        errors.extend(_validate_workflow(wf, ai_node_categories))

    return (len(errors) == 0), errors


def _validate_outputs(outputs, loc: str, errors: List[str]) -> None:
    if outputs is None:
        return
    if not isinstance(outputs, list) or not outputs:
        errors.append(f"{loc}.outputs, if declared, must be a non-empty array")
        return
    seen_models = set()
    for j, ent in enumerate(outputs):
        oloc = f"{loc}.outputs[{j}]"
        if not isinstance(ent, dict):
            errors.append(f"{oloc} must be an object")
            continue
        model = ent.get("model")
        if not _is_intish(model):
            errors.append(f"{oloc}.model must be an integer")
        else:
            model = int(model)
            if model <= 0:
                errors.append(f"{oloc}.model must be greater than 0 (0 is background)")
            elif model in seen_models:
                errors.append(f"{oloc}.model duplicated: {model}")
            else:
                seen_models.add(model)
        label = ent.get("label")
        if not _is_intish(label):
            errors.append(f"{oloc}.label must be an integer")
            continue
        label = int(label)
        if label <= 0:
            errors.append(f"{oloc}.label must be greater than 0 (0 is background)")
        semantic = ent.get("semantic")
        if semantic is not None and not isinstance(semantic, str):
            errors.append(f"{oloc}.semantic, if declared, must be a string")
        has_semantic = isinstance(semantic, str) and bool(semantic.strip())
        if label > SYSTEM_LABEL_MAX:
            errors.append(
                f"{oloc}: label {label} is outside the system range 0-{SYSTEM_LABEL_MAX}. "
                f"{INSTANCE_LABEL_MIN}-{INSTANCE_LABEL_MAX} is reserved for instance "
                f"segmentation (labels assigned at runtime) and "
                f"{MANUAL_LABEL_MIN}+ for manual drawing; map the structure into the "
                f"system range instead"
            )
        elif has_semantic:
            errors.append(
                f"{oloc}: system preset label {label} already has a name; "
                f"remove the custom 'semantic'"
            )


def _validate_instance(node: dict, loc: str, errors: List[str]) -> None:
    """Cross-check the optional `instance` declaration. Nodes without it are untouched.

    `instance: true` means the node's labels are instance ids assigned at runtime and the
    semantics are reported with the result. That is incompatible with a static `outputs`
    mapping, which fixes the labels ahead of time, so declaring both is rejected here
    rather than left to produce an unusable result after registration.
    """
    if "instance" not in node:
        return
    if not isinstance(node.get("instance"), bool):
        errors.append(f"{loc}.instance, if declared, must be a boolean true/false")
        return
    if not node["instance"]:
        return
    if node.get("category") != "ai_segment":
        errors.append(
            f"{loc}.instance is only valid on ai_segment nodes; detection produces no labels"
        )
    if node.get("outputs") is not None:
        errors.append(
            f"{loc} declares both instance and outputs: instance labels are assigned at "
            f"runtime and semantics are reported with the result, so outputs must be omitted"
        )


def _validate_params(params, loc: str, errors: List[str]) -> None:
    if params is None:
        return
    if not isinstance(params, list):
        errors.append(f"{loc}.params, if declared, must be an array")
        return
    seen_flags = set()
    for j, p in enumerate(params):
        ploc = f"{loc}.params[{j}]"
        if not isinstance(p, dict):
            errors.append(f"{ploc} must be an object")
            continue
        flag = p.get("flag")
        if not isinstance(flag, str) or not flag.strip():
            errors.append(f"{ploc}.flag must be a non-empty string")
        else:
            flag = flag.strip()
            if not flag.startswith("--") or len(flag) <= 2:
                errors.append(f"{ploc}.flag must use the '--name' form")
            if flag in seen_flags:
                errors.append(f"{ploc}.flag duplicated: {flag!r}")
            seen_flags.add(flag)
        if "options" in p and not isinstance(p["options"], list):
            errors.append(f"{ploc}.options, if declared, must be an array")
        elif isinstance(p.get("options"), list) and not p["options"]:
            errors.append(f"{ploc}.options, if declared, must not be empty")
        if "min" in p and not _is_number(p["min"]):
            errors.append(f"{ploc}.min must be a number")
        if "max" in p and not _is_number(p["max"]):
            errors.append(f"{ploc}.max must be a number")
        if _is_number(p.get("min")) and _is_number(p.get("max")):
            if float(p["min"]) > float(p["max"]):
                errors.append(f"{ploc}: 'min' must not exceed 'max'")
        if "default" in p and isinstance(p.get("options"), list):
            if p["default"] not in p["options"]:
                errors.append(f"{ploc}: 'default' must be one of the declared 'options'")


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_vector(value, loc: str, errors: List[str], *, positive: bool) -> None:
    if not isinstance(value, list) or len(value) != 3 or not all(
        _is_number(item) for item in value
    ):
        errors.append(f"{loc} must be an array of three numbers")
        return
    if positive and any(float(item) <= 0 for item in value):
        errors.append(f"{loc} values must be greater than 0")
    if not positive and any(float(item) < 0 for item in value):
        errors.append(f"{loc} values must be greater than or equal to 0")


def _validate_workflow_params(kind: str, params, loc: str, errors: List[str]) -> None:
    if params is None:
        return
    if not isinstance(params, dict):
        errors.append(f"{loc}.params, if declared, must be an object")
        return
    # A default workflow may only configure 'resample' and 'roi_crop'; parameters
    # on any other node are dropped when the workflow is built (see docs/nodes.md).
    allowed = {
        "resample": {"target_spacing_mm"},
        "roi_crop": {"crop_mode", "crop_margins_mm", "filter_dilate_mm"},
    }.get(kind)
    if allowed is None:
        if params:
            errors.append(
                f"{loc}.params has no effect on {kind!r}: a default workflow may only "
                f"configure 'resample' and 'roi_crop'; set the rest on the canvas"
            )
        return
    for name in sorted(set(params) - allowed):
        errors.append(f"{loc}.params contains unsupported field: {name!r}")

    if kind == "resample" and "target_spacing_mm" in params:
        _validate_vector(
            params["target_spacing_mm"],
            f"{loc}.params.target_spacing_mm",
            errors,
            positive=True,
        )
    elif kind == "roi_crop":
        mode = params.get("crop_mode")
        if mode is not None and mode not in ("bbox", "filter"):
            errors.append(f"{loc}.params.crop_mode must be 'bbox' or 'filter'")
        for name in ("crop_margins_mm", "filter_dilate_mm"):
            if name in params:
                _validate_vector(
                    params[name], f"{loc}.params.{name}", errors, positive=False
                )


def _validate_workflow(wf: dict, ai_node_categories: Dict[str, str]) -> List[str]:
    """Validate node identity, parameters, ports, required inputs and DAG shape."""
    errs: List[str] = []
    global_params = wf.get("params")
    if global_params is not None:
        if not isinstance(global_params, dict):
            errs.append("workflow.params, if declared, must be an object")
        else:
            allowed = {"crop_mode", "crop_margins_mm", "filter_dilate_mm"}
            for name in sorted(set(global_params) - allowed):
                errs.append(f"workflow.params contains unsupported field: {name!r}")
            mode = global_params.get("crop_mode")
            if mode is not None and mode not in ("bbox", "filter"):
                errs.append("workflow.params.crop_mode must be 'bbox' or 'filter'")
            for name in ("crop_margins_mm", "filter_dilate_mm"):
                if name in global_params:
                    _validate_vector(
                        global_params[name],
                        f"workflow.params.{name}",
                        errs,
                        positive=False,
                    )

    nodes = wf.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return ["workflow.nodes must be a non-empty array"]

    ai_node_ids = set(ai_node_categories)
    valid_kinds = set(_BASE_KINDS) | ai_node_ids
    node_kinds: Dict[str, str] = {}
    node_ports: Dict[str, Tuple[Dict[str, str], Dict[str, str]]] = {}
    used_ai_nodes: Set[str] = set()
    for i, n in enumerate(nodes):
        loc = f"workflow.nodes[{i}]"
        if not isinstance(n, dict):
            errs.append(f"{loc} must be an object")
            continue
        kind = n.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            errs.append(f"{loc}.kind missing")
            continue
        kind = kind.strip()
        if kind not in valid_kinds:
            errs.append(
                f"{loc}.kind unknown: {kind!r} (not a workflow node listed in "
                f"docs/nodes.md, nor an AI node id declared in this manifest)"
            )
        node_id = n.get("id", kind)
        if not isinstance(node_id, str) or not node_id.strip():
            errs.append(f"{loc}.id, if declared, must be a non-empty string")
            continue
        node_id = node_id.strip()
        if "." in node_id:
            errs.append(f"{loc}.id must not contain '.'")
        if node_id in node_kinds:
            errs.append(
                f"{loc}.id duplicated: {node_id!r}; assign unique ids when a kind is reused"
            )
            continue

        if kind in ai_node_ids:
            used_ai_nodes.add(kind)
        node_kinds[node_id] = kind
        _validate_workflow_params(kind, n.get("params"), loc, errs)

    for node_id, kind in node_kinds.items():
        if kind in ai_node_ids:
            category = ai_node_categories[kind]
            outputs = (
                {"mask": "mask"}
                if category == "ai_segment"
                else {"detections": "detection"}
            )
            node_ports[node_id] = (
                {"image": "image"},
                outputs,
            )
        elif kind in _BASE_PORTS:
            node_ports[node_id] = _BASE_PORTS[kind]

    if ai_node_ids and not used_ai_nodes:
        errs.append("workflow must include at least one AI node declared in top-level nodes")

    edges = wf.get("edges")
    if edges is None:
        edges = []
    if not isinstance(edges, list):
        errs.append("workflow.edges, if declared, must be an array")
        return errs

    incoming: Dict[str, Set[str]] = defaultdict(set)
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    indegree = {node_id: 0 for node_id in node_kinds}
    for i, e in enumerate(edges):
        loc = f"workflow.edges[{i}]"
        if isinstance(e, list) and len(e) == 2 and all(isinstance(x, str) for x in e):
            if any(endpoint.count(".") != 1 for endpoint in e):
                errs.append(f'{loc} invalid format (expect ["a.port","b.port"])')
                continue
            src, src_port = e[0].split(".", 1)
            dst, dst_port = e[1].split(".", 1)
        elif (
            isinstance(e, list)
            and len(e) == 4
            and all(isinstance(x, str) and x for x in e)
        ):
            src, src_port, dst, dst_port = e
        else:
            errs.append(f'{loc} invalid format (expect ["a.port","b.port"])')
            continue

        if src not in node_kinds:
            errs.append(f"{loc} source node not found: {src!r}")
        if dst not in node_kinds:
            errs.append(f"{loc} target node not found: {dst!r}")
        if src not in node_kinds or dst not in node_kinds:
            continue

        src_outputs = node_ports.get(src, ({}, {}))[1]
        dst_inputs = node_ports.get(dst, ({}, {}))[0]
        if src_port not in src_outputs:
            errs.append(f"{loc} output port not found: {src}.{src_port}")
        if dst_port not in dst_inputs:
            errs.append(f"{loc} input port not found: {dst}.{dst_port}")
        if src_port in src_outputs and dst_port in dst_inputs:
            if src_outputs[src_port] != dst_inputs[dst_port]:
                errs.append(
                    f"{loc} port type mismatch: {src}.{src_port} "
                    f"cannot connect to {dst}.{dst_port}"
                )
            if dst_port in incoming[dst]:
                errs.append(f"{loc} input port already connected: {dst}.{dst_port}")
            incoming[dst].add(dst_port)

        if dst not in adjacency[src]:
            adjacency[src].add(dst)
            indegree[dst] += 1

    for node_id, kind in node_kinds.items():
        required_kind = kind
        if kind in ai_node_ids:
            required_kind = ai_node_categories[kind]
        required = _REQUIRED_INPUTS.get(required_kind, set())
        missing = required - incoming.get(node_id, set())
        if missing:
            errs.append(
                f"workflow node {node_id!r} missing required input(s): "
                + ", ".join(sorted(missing))
            )
        if kind == "display_output" and not incoming.get(node_id):
            errs.append(
                f"workflow node {node_id!r} must connect at least one output "
                "(mask, detections or metrics)"
            )

    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target in adjacency.get(node_id, set()):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(node_kinds):
        errs.append("workflow contains a cycle")

    return errs


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    target = argv[1]
    if os.path.isdir(target):
        plugin_dir = target
        manifest_path = os.path.join(target, "manifest.json")
    else:
        manifest_path = target
        plugin_dir = os.path.dirname(os.path.abspath(target))

    if not os.path.isfile(manifest_path):
        print(f"[ERROR] manifest.json not found: {manifest_path}")
        return 2

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as e:
        print(f"[ERROR] failed to read/parse manifest.json: {e}")
        return 2

    ok, errors = validate_manifest(manifest, plugin_dir)
    if ok:
        print(f"[OK] {manifest_path} is valid (spec v1.0).")
        print("     Note: outputs.label is range-checked only; registration verifies "
              "each id against the platform label table.")
        return 0

    print(f"[INVALID] {manifest_path} has {len(errors)} problem(s):")
    for e in errors:
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
