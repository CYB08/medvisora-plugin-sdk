# Model weights directory (`stage_detect` node)

[English](README.md) | [简体中文](README.zh-CN.md)

The detection node's weights are a **single TorchScript file** whose name must match `DET_MODEL["path"]` in `docker/predict.py`:

```text
model/
└── detector.pt
```

The `spacing`, `nms_thresh` and `base_anchor_shapes` values in `DET_MODEL` come from MONAI's public LUNA16 RetinaNet configuration. They must be replaced with the values the target detection model was trained with, otherwise the inference results are unusable.

The weights of the other node, `stage_seg`, are located in [`../nnUNet_results/`](../nnUNet_results/README.md).
