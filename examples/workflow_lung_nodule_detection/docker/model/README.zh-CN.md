# 模型权重目录（`stage_detect` 节点）

[English](README.md) | [简体中文](README.zh-CN.md)

检测节点的权重是**单个 TorchScript 文件**，文件名须与 `docker/predict.py` 中的 `DET_MODEL["path"]` 一致：

```text
model/
└── detector.pt
```

`DET_MODEL` 中的 `spacing`、`nms_thresh`、`base_anchor_shapes` 等取自 MONAI 公开的 LUNA16 RetinaNet 配置，须替换为与目标检测模型训练配置一致的取值，否则推理结果不可用。

另一个节点 `stage_seg` 的权重放在 [`../nnUNet_results/`](../nnUNet_results/README.zh-CN.md)。
