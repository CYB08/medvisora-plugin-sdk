# Workflow Node Specification

[English](nodes.md) | [简体中文](nodes.zh-CN.md)

A workflow consists of nodes and directed edges. Nodes receive and emit data through ports, and edges declare the direction of data flow. A complete workflow must be acyclic.

## 1. Platform nodes

| `kind` | Purpose | Inputs | Outputs | Parameters |
| --- | --- | --- | --- | --- |
| `image_input` | Provides the current image | – | `image` | – |
| `resample` | Resamples to a target voxel spacing | `image` | `image` | `target_spacing_mm: [x, y, z]` |
| `roi_crop` | Crops or filters the image by a mask | `image`, `mask` | `image`, `bbox` | `crop_mode`, `crop_margins_mm`, `filter_dilate_mm` |
| `mask_restore` | Restores a cropped mask to the original space | `mask`, `bbox` | `mask` | – |
| `radiomics` | Computes quantitative results for structures | `image`, `mask` | `metrics` | `mode`, `structures` |
| `display_output` | Presents the workflow result | `mask`, `detections` or `metrics` | – | – |
| `image_export` | Exports the image | `image` | – | `export_dir` |

`roi_crop.crop_mode` accepts `bbox` and `filter`; `radiomics.mode` accepts `basic` and `radiomics`.

The parameters in the table apply to the workflow canvas. In a `default_workflow` written into a model card, only the parameters of `resample` and `roi_crop` are supported.

## 2. AI nodes

AI nodes are declared through `manifest.nodes[]`:

| `category` | Inputs | Outputs |
| --- | --- | --- |
| `ai_segment` | `image` | `mask` |
| `ai_detect` | `image` | `detections` |

Inside `default_workflow.nodes[]`, the `kind` of an AI node must be the corresponding `nodes[].id`; `ai_segment` and `ai_detect` cannot be used directly.

## 3. Nodes and edges

A workflow node takes the following form:

```json
{
  "kind": "resample",
  "id": "resample_input",
  "params": {
    "target_spacing_mm": [2.0, 2.0, 2.0]
  }
}
```

- `kind`: a platform node name, or the `id` of an AI node declared in the manifest
- `id`: the node identifier within the workflow; defaults to `kind` when omitted
- `params`: the parameters of this node

When the same kind of node is used more than once, each occurrence must be given a distinct `id`.

An edge takes the form `["source_node.output_port", "target_node.input_port"]`:

```json
[
  ["image_input.image", "resample_input.image"],
  ["resample_input.image", "inference.image"],
  ["inference.mask", "display_output.mask"]
]
```

Edges must satisfy the following requirements:

- The source and target ports carry the same data type
- Each input port accepts at most one edge
- Every required input is connected
- The workflow contains at least one AI node declared in the manifest
- The workflow has no circular dependency

A Standalone plugin declares no edges. A Workflow plugin can provide a default arrangement through `default_workflow`, or leave the arrangement to the user on the canvas.

Complete syntax is covered by the [manifest specification](manifest.md), and runnable cases are available in [`examples/`](../examples/).
