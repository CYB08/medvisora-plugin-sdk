# Manifest Specification

[English](manifest.md) | [简体中文](manifest.zh-CN.md)

`manifest.json` declares the Docker image, the model information and the AI nodes the plugin provides. After reading and validating this file, the platform generates a model card and adds the declared nodes to the workflow.

## 1. Minimal example

The following configuration covers a single-node segmentation plugin:

```json
{
  "key": "my_model",
  "name": "My Model",
  "version": "v1.0",
  "task": ["segmentation"],
  "docker": {
    "image": "my-model:1.0"
  },
  "nodes": [
    {
      "id": "inference",
      "title": "AI Inference",
      "category": "ai_segment",
      "outputs": [
        { "model": 1, "label": 2 }
      ]
    }
  ]
}
```

`docker.image` must match the name of the image built or imported locally.

## 2. Top-level fields

| Field | Requirement | Description |
| --- | --- | --- |
| `key` | Required | Unique plugin identifier; letters, digits, underscores, hyphens and dots are allowed |
| `name` | Required | Model card name |
| `version` | Required | Displayed version |
| `task` | Required | Array of task types, for example `segmentation` or `detection` |
| `docker` | Required | Docker image and runtime configuration |
| `nodes` | Required | AI nodes the plugin provides |
| `team` | Optional | Author or team |
| `desc` | Optional | Short description |
| `modality` | Optional | Imaging modality, for example `CT` or `MR` |
| `default_workflow` | Optional | Default workflow of the model card |

## 3. Docker configuration

| Field | Requirement | Description |
| --- | --- | --- |
| `image` | Required | Docker image name and tag |
| `script` | Optional | Path of the inference script, `/workspace/predict.py` by default |
| `entrypoint` | Optional | Script interpreter, `python` by default |
| `gpus` | Optional | Docker GPU argument; the platform setting applies when omitted, and an empty string adds no GPU argument |
| `shm_size` | Optional | Shared memory size of the container |
| `ipc` | Optional | Docker IPC configuration |
| `cpus` | Optional | CPU limit of the container |

Example:

```json
{
  "docker": {
    "image": "my-model:1.0",
    "ipc": "host"
  }
}
```

## 4. AI nodes

Each `nodes[]` entry declares one AI capability provided by the image:

| Field | Requirement | Description |
| --- | --- | --- |
| `id` | Required | Unique node identifier, also passed to the container as `--node-id` |
| `title` | Required | Display name in the workflow |
| `category` | Required | `ai_segment` or `ai_detect` |
| `outputs` | Optional | Mapping from segmentation model output values to platform labels |
| `params` | Optional | Inference parameters adjustable from the interface |
| `instance` | Optional | Set to `true` for instance segmentation nodes |
| `args` | Optional | Array of fixed arguments passed to the inference script |

In a multi-node image, each `id` must match the corresponding routing key in the inference script.

An `id` may contain only letters, digits, underscores and hyphens. It must not contain dots, and must not collide with a platform node name or with `ai_segment` or `ai_detect`.

### outputs

`outputs` applies to `ai_segment` only and maps model output values to semantic labels supported by the platform:

```json
{
  "outputs": [
    { "model": 1, "label": 2, "group": "Group A" }
  ]
}
```

- `model`: the raw value in the model mask; must be a positive integer and unique within the node
- `label`: an ID already allocated in the platform's system label table, in the range `1-999`
- `group`: optional, used only to group results on the model card

Label names are maintained by the platform, so `outputs` must not declare `semantic`. When `outputs` is omitted, the platform keeps the raw values of the mask. Instance segmentation nodes must not declare `outputs`.

### params

`params` declares inference parameters that the user can adjust. They reach the container through `--extra-params`:

```json
{
  "params": [
    {
      "flag": "--threshold",
      "title": "Threshold",
      "default": 0.5,
      "min": 0.0,
      "max": 1.0
    }
  ]
}
```

| Field | Requirement | Description |
| --- | --- | --- |
| `flag` | Required | Parameter identifier in `--name` form; unique within the node |
| `title` | Recommended | Display name in the interface |
| `default` | Optional | Default value; must be one of `options` when `options` is declared |
| `min`, `max` | Optional | Numeric range; `min` must not exceed `max` |
| `options` | Optional | Array of discrete values; must not be empty |

Segmentation nodes have a built-in `--use-mirroring` and detection nodes a built-in `--score-thresh`, both effective without being declared; using a `flag` of the same name overrides its default. The rules for how parameters are keyed inside the container are described in the [container I/O contract](contract.md).

### instance

An instance segmentation node should set `instance: true` and omit `outputs`:

```json
{
  "id": "instance_seg",
  "title": "Instance Segmentation",
  "category": "ai_segment",
  "instance": true
}
```

An instance mask uses the platform's reserved labels `1000-1099` and reports the same labels together with their semantics in `output.json`. The output format is described in the [container I/O contract](contract.md).

## 5. Standalone and Workflow

The packaging mode shown on the model card follows the number of AI nodes: one AI node is Standalone, two or more is Workflow.

Whether inference can be started directly from the model card depends on whether the platform can determine the run graph:

- One AI node with no `default_workflow`: the platform builds the minimal workflow `image_input -> AI node -> display_output`
- `default_workflow` declared: the plugin runs according to that workflow
- Several AI nodes with no `default_workflow`: the graph must be arranged manually on the workflow canvas before running

To combine AI nodes with platform nodes, declare the nodes and edges in `default_workflow`:

```json
{
  "default_workflow": {
    "nodes": [
      { "kind": "image_input" },
      {
        "kind": "resample",
        "params": { "target_spacing_mm": [2.0, 2.0, 2.0] }
      },
      { "kind": "inference" },
      { "kind": "display_output" }
    ],
    "edges": [
      ["image_input.image", "resample.image"],
      ["resample.image", "inference.image"],
      ["inference.mask", "display_output.mask"]
    ]
  }
}
```

`kind` is either a platform node name or a top-level `nodes[].id`. An edge takes the form `["source_node.port", "target_node.port"]`. The available nodes, ports and parameters are listed in the [workflow node specification](nodes.md).

A default workflow on a model card supports `params` on the `resample` and `roi_crop` nodes; parameters of the other nodes are configured on the workflow canvas.

The workflow may be inlined in `default_workflow` or placed in a `workflow.json` next to `manifest.json`. When both exist, the inline declaration takes precedence.

## 6. Validation and registration

Offline validation accepts either a manifest file or a plugin directory, resolved relative to the current working directory:

```bash
python tools/validate.py path/to/plugin/manifest.json
python tools/validate.py path/to/plugin/
```

Once validation passes, choose **Card → Register Model Card** in MedVisora and import `manifest.json`. Registration does not distribute the image: the tag named by `docker.image` must be available locally before the plugin runs.

The offline tool checks the file structure and the workflow connections. Whether an `outputs.label` is an ID the platform has allocated is decided by the check performed at registration time.

Complete configurations are available in [`templates/`](../templates/) and [`examples/`](../examples/).
