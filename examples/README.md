# Examples

[English](README.md) | [简体中文](README.zh-CN.md)

MedVisora places no constraints on model architecture, training framework, runtime environment or internal processing. Packaging the inference as a Docker image that follows the platform I/O contract is all that integration requires. This directory uses **nnUNet** and **MONAI** to demonstrate the Standalone and Workflow packaging modes.

The documentation and templates in this SDK can be handed to a large language model such as GPT or Claude, together with the specification of the target model, to generate the inference script and the image build configuration. The templates and examples follow a uniform structure so that a model can read and reuse them directly.

| Example | Mode | Key point | Deployment |
| --- | --- | --- | --- |
| `standalone_nnunet` | Standalone | General single-node segmentation; a new task only needs new weights and a new manifest | [See below](#deploy-standalone_nnunet) |
| `workflow_nnunet` | Workflow | General two-stage segmentation; resampling, cropping and restoring are handled by platform nodes | [See below](#deploy-workflow_nnunet) |
| `standalone_lung_tumor_nnunet` | Standalone | Two-stage pipeline packaged as a single node; cropping and restoring happen inside the container | [See below](#deploy-standalone_lung_tumor_nnunet) |
| `workflow_lung_nodule_detection` | Workflow | One image providing both a segmentation and a detection AI node, with `roi_crop` in `filter` mode | [See below](#deploy-workflow_lung_nodule_detection) |

Standalone suits cases where a single container performs the entire process. Choose Workflow when the stages need to be arranged on the canvas or combined with platform nodes.

This repository does not distribute model weights or the nnUNet source; both must be supplied before building an image. Weights for the nnUNet examples go into each example's `docker/nnUNet_results/`, and `workflow_lung_nodule_detection` additionally requires detection weights in `docker/model/`. Both directories contain a `README.md` describing the expected structure.

Registering `manifest.json` neither packages nor installs the image. After building, confirm that the tag named by `docker.image` appears in `docker images`; the platform checks image availability before starting inference.

All commands below are executed with the SDK root as the working directory.

## Quick start: from an empty template

When the model is not based on nnUNet and the inference code has to be written from scratch, start from `templates/`: use `templates/standalone` for a single AI node, and `templates/workflow` for multiple AI nodes that also need a default workflow.

**1. Copy the template**

```bash
cp -r templates/standalone my-model
```

On Windows PowerShell, use `Copy-Item -Recurse templates/standalone my-model`.

**2. Implement the inference**

Implement model loading and inference inside the `USER EDIT AREA` of `my-model/docker/predict.py`. The rest of the file is the platform I/O contract and must not be modified.

**3. Build the image**

```bash
docker build -t my-model:1.0 my-model/docker/
```

Whenever the weights or `predict.py` change, use a new tag and update `docker.image` in `manifest.json` to match.

**4. Write the manifest**

In `my-model/plugin/manifest.json`, set the image name to the tag just built and declare the AI nodes:

```json
{ "docker": { "image": "my-model:1.0" } }
```

In Workflow mode, every `nodes[].id` must match a key in the routing table of `predict.py` exactly.

**5. Validate**

```bash
python tools/validate.py my-model/plugin/manifest.json
```

**6. Register**

In MedVisora, choose **Card → Register Model Card** (Ctrl+Shift+A) and select `my-model/plugin/manifest.json` in the dialog.

## Deploy standalone_nnunet

One AI node producing a segmentation mask in a single pass. Requires one set of nnUNet weights.

**1. Obtain the nnUNet source**

```bash
git clone --branch v2.8.1 --depth 1 https://github.com/MIC-DKFZ/nnUNet.git examples/standalone_nnunet/docker/nnUNet
```

**2. Add the model weights**

Place the nnUNet model directory in `examples/standalone_nnunet/docker/nnUNet_results/`. Its structure must match `NNUNET_MODEL["path"]` in `docker/predict.py`; see that directory's [`README.md`](standalone_nnunet/docker/nnUNet_results/README.md).

**3. Build the image**

After the first two steps, `examples/standalone_nnunet/docker/` should contain:

```text
docker/
├── Dockerfile
├── predict.py
├── requirements.txt
├── nnUNet/
└── nnUNet_results/
    └── Dataset001_MyOrgans/
        └── nnUNetTrainer__nnUNetPlans__3d_fullres/
            ├── fold_0/
            ├── dataset.json
            └── plans.json
```

```bash
docker build -t my-organ-seg:1.0 examples/standalone_nnunet/docker/
```

**4. Validate (optional)**

```bash
python tools/validate.py examples/standalone_nnunet/plugin/manifest.json
```

**5. Register in MedVisora**

Choose **Card → Register Model Card** (Ctrl+Shift+A) and select `examples/standalone_nnunet/plugin/manifest.json` in the dialog.

## Deploy workflow_nnunet

Two AI nodes in a pipeline of resampling, coarse localization, ROI cropping, fine segmentation and mask restoration. Requires two sets of nnUNet weights.

**1. Obtain the nnUNet source**

```bash
git clone --branch v2.8.1 --depth 1 https://github.com/MIC-DKFZ/nnUNet.git examples/workflow_nnunet/docker/nnUNet
```

**2. Add the model weights**

Place both the coarse and the fine weight sets in `examples/workflow_nnunet/docker/nnUNet_results/`. Their structure must match `STAGE_MODELS` in `docker/predict.py`; see that directory's [`README.md`](workflow_nnunet/docker/nnUNet_results/README.md).

**3. Build the image**

```text
docker/
├── Dockerfile
├── predict.py
├── requirements.txt
├── nnUNet/
└── nnUNet_results/
    ├── Dataset001_MyTaskCoarse/
    │   └── nnUNetTrainer__nnUNetPlans__3d_fullres/
    └── Dataset002_MyTaskFine/
        └── nnUNetTrainer__nnUNetPlans__3d_fullres/
```

```bash
docker build -t my-twostage-seg:1.0 examples/workflow_nnunet/docker/
```

**4. Validate (optional)**

```bash
python tools/validate.py examples/workflow_nnunet/plugin/manifest.json
```

**5. Register in MedVisora**

After registration, `default_workflow` is turned into a workflow that can be started directly from the model card. The resampling spacing and crop margins can be edited in `default_workflow.nodes[*].params`, or adjusted on the workflow canvas after registration.

## Deploy standalone_lung_tumor_nnunet

The same two-stage process as `workflow_nnunet`, packaged as a single AI node: ROI cropping and mask restoration happen inside the container, so two sets of nnUNet weights are still required.

**1. Obtain the nnUNet source**

```bash
git clone --branch v2.8.1 --depth 1 https://github.com/MIC-DKFZ/nnUNet.git examples/standalone_lung_tumor_nnunet/docker/nnUNet
```

**2. Add the model weights**

Place both the coarse and the fine weight sets in `examples/standalone_lung_tumor_nnunet/docker/nnUNet_results/`. Their structure must match `STAGE1_MODEL` and `STAGE2_MODEL` in `docker/predict.py`; see that directory's [`README.md`](standalone_lung_tumor_nnunet/docker/nnUNet_results/README.md).

**3. Build the image**

```bash
docker build -t my-lung-tumor:1.0 examples/standalone_lung_tumor_nnunet/docker/
```

**4. Validate (optional)**

```bash
python tools/validate.py examples/standalone_lung_tumor_nnunet/plugin/manifest.json
```

**5. Register in MedVisora**

The crop margin is fixed by `CROP_MARGIN_MM` in `docker/predict.py`; changing it requires rebuilding the image. To make that margin adjustable from the interface, split the stages the way `workflow_nnunet` does.

## Deploy workflow_lung_nodule_detection

One image providing two AI nodes: the segmentation node writes a mask, the detection node returns a target list. Requires one set of nnUNet segmentation weights and one TorchScript detection checkpoint.

**1. Obtain the nnUNet source**

```bash
git clone --branch v2.8.1 --depth 1 https://github.com/MIC-DKFZ/nnUNet.git examples/workflow_lung_nodule_detection/docker/nnUNet
```

**2. Add the model weights**

Place the segmentation weights in `examples/workflow_lung_nodule_detection/docker/nnUNet_results/` and the detection weights in `examples/workflow_lung_nodule_detection/docker/model/`; see [`nnUNet_results/README.md`](workflow_lung_nodule_detection/docker/nnUNet_results/README.md) and [`model/README.md`](workflow_lung_nodule_detection/docker/model/README.md) respectively.

**3. Build the image**

```text
docker/
├── Dockerfile
├── predict.py
├── requirements.txt
├── nnUNet/
├── nnUNet_results/
│   └── Dataset001_MyLungSeg/
│       └── nnUNetTrainer__nnUNetPlans__3d_fullres/
└── model/
    └── detector.pt
```

```bash
docker build -t my-lung-nodule:1.0 examples/workflow_lung_nodule_detection/docker/
```

This example additionally depends on MONAI, so the build takes longer than the other three.

**4. Validate (optional)**

```bash
python tools/validate.py examples/workflow_lung_nodule_detection/plugin/manifest.json
```

**5. Register in MedVisora**

After registration, `default_workflow` uses the segmentation node's output as the ROI filter for the detection node. The detection threshold can be adjusted on the model card or on the workflow canvas.

## Deploying a custom model from an example

Starting from `standalone_nnunet` is recommended:

1. Copy the weights into `docker/nnUNet_results/`
2. Edit `NNUNET_MODEL` in `docker/predict.py` (`STAGE_MODELS` for Workflow) so the paths match the weight directory
3. Build the image and note the tag: `docker build -t my-nnunet:1.0 examples/standalone_nnunet/docker/`
4. Edit `plugin/manifest.json`: update `docker.image` and configure the `outputs` label mapping for the model's output values

```json
"docker": { "image": "my-nnunet:1.0", "ipc": "host" },
"nodes": [
  {
    "id": "inference",
    "title": "AI Inference",
    "category": "ai_segment",
    "outputs": [
      { "model": 1, "label": 5 },
      { "model": 2, "label": 6, "group": "Group A" }
    ]
  }
]
```

5. Validate, then register in MedVisora

## Third-party components

The [nnUNet](https://github.com/MIC-DKFZ/nnUNet) and [MONAI](https://github.com/Project-MONAI/MONAI) projects referenced by these examples are both distributed under the Apache License 2.0. Neither their source nor their weights ship with this repository, and their respective license terms apply when they are used.
