# 模型权重目录（`stage_seg` 节点）

[English](README.md) | [简体中文](README.zh-CN.md)

将 `stage_seg` 节点的 nnUNet 模型目录放入此处，结构须与 `docker/predict.py` 中的 `SEG_MODEL["path"]` 一致：

```text
nnUNet_results/
└── Dataset001_MyLungSeg/
    └── nnUNetTrainer__nnUNetPlans__3d_fullres/
        ├── fold_0/
        │   └── checkpoint_final.pth
        ├── dataset.json
        └── plans.json
```

数据集名、trainer 或 fold 不同时，同步修改 `docker/predict.py` 中的 `SEG_MODEL`。

另一个节点 `stage_detect` 的权重是单个 `.pt` 文件，放在 [`../model/`](../model/README.zh-CN.md)。
