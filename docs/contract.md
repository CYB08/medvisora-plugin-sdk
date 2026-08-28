# Container I/O Contract

[English](contract.md) | [简体中文](contract.zh-CN.md)

MedVisora uses one container interface for all Docker segmentation and detection plugins. When the platform runs an AI node, it mounts the input directory into the container and invokes the inference script; the container writes the result descriptor and any related files back into that same directory. Standalone and Workflow use the identical interface, and the framework and processing pipeline inside the image are unconstrained.

## 1. Fixed paths

| Item | Default | Description |
| --- | --- | --- |
| Mount directory | `/data` | Directory through which the platform and the container exchange data |
| Input image | `/data/input.nii.gz` | NIfTI format |
| Result descriptor | `/data/output.json` | JSON format |
| Inference script | `/workspace/predict.py` | Configurable through `docker.script` |
| Interpreter | `python` | Configurable through `docker.entrypoint` |

A Dockerfile must not set `ENTRYPOINT`, so that the platform can invoke the configured interpreter and inference script.

## 2. Command-line arguments

The platform passes the following arguments to the inference script:

| Argument | Requirement | Description |
| --- | --- | --- |
| `--node-id` | Recommended | The `manifest.nodes[].id` of the current AI node; multi-node images use it to select the stage to run |
| `--input` | Required | Absolute path of the input image |
| `--output` | Required | Absolute path of `output.json`; its parent directory is also the directory for result files |
| `--extra-params` | Recommended | JSON object string holding the tunable parameters of the current node |

The inference script should parse arguments with `parse_known_args()` so that future additions remain compatible.

Each `flag` in `manifest.nodes[].params` is converted into an `--extra-params` key by removing the leading `--` and replacing hyphens with underscores.

The platform supplies the following built-in parameters to AI nodes; they are sent even when the manifest declares no `params`:

| Key | Applies to | Type | Description |
| --- | --- | --- | --- |
| `use_mirroring` | `ai_segment` | Boolean | Whether to enable mirroring test-time augmentation |
| `score_thresh` | `ai_detect` | Float | Confidence threshold for detection results |

Declaring a `flag` of the same name in `manifest.nodes[].params` overrides the default. The platform may also supply `selected_outputs`, the model output values chosen by the user. A container should read only the keys it needs and fall back to its own defaults for keys that are absent.

## 3. Output format

The container must write valid JSON to the location given by `--output`, containing at least `segmentation` or `detection`.

### Segmentation

A segmentation node writes its mask into the directory containing `output.json`. The default file name is `pred.nii.gz`:

```json
{ "segmentation": {} }
```

To use a different file name, declare it through `mask_path`:

```json
{ "segmentation": { "mask_path": "result.nii.gz" } }
```

`mask_path` must be a file name in the same directory as `output.json`. For non-instance segmentation, the mask keeps the model's raw output values; the label mapping rules are described in the [manifest specification](manifest.md).

### Detection

A detection node returns a target list through `detection.nodules` and writes no mask. Each target should carry physical coordinates and dimensions consistent with the input image, expressed in millimetres:

```json
{
  "detection": {
    "nodules": [
      {
        "center_mm": { "x": 12.5, "y": -33.0, "z": 88.2 },
        "size_mm": { "width": 8.1, "height": 7.6, "depth": 9.0 },
        "confidence": 87.0
      }
    ]
  }
}
```

`center_mm` and `size_mm` are required; `confidence` is optional and ranges from 0 to 100. Custom fields may be added alongside these; the platform does not interpret them and their presence does not affect result processing.

### Instance segmentation

An instance segmentation node must declare `instance: true` in the manifest and write the mask together with a semantic list:

```json
{
  "segmentation": {
    "instance": true,
    "labels": [
      { "label": 1000, "semantic": "Instance 1" },
      { "label": 1001, "semantic": "Instance 2" }
    ]
  }
}
```

The mask of an instance segmentation node must use the platform's reserved instance labels directly, matching the values listed in `labels`, and does not go through the `outputs` mapping. The label range and the corresponding manifest requirements are described in the [manifest specification](manifest.md).

A single result may contain both `segmentation` and `detection`.

## 4. Progress reporting

The inference script can report progress on standard output:

```text
PROGRESS:35:Running inference
```

The format is `PROGRESS:<0-100>:<message>`, and the message may be empty. Setting `PYTHONUNBUFFERED=1` in the Dockerfile is recommended so that output buffering does not delay progress updates.

## 5. Success and failure

- The task succeeds when the container exits with code `0` and the result descriptor and the files it declares are valid.
- The task fails when the exit code is non-zero, when `output.json` is missing or cannot be parsed, or when a declared result file does not exist.
- When the user cancels a task, the platform terminates the running container.

Docker resources, node parameters, label mapping and instance segmentation settings are covered by the [manifest specification](manifest.md); workflow nodes and connection rules are covered by the [node specification](nodes.md).
