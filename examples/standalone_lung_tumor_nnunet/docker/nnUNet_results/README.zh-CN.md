# 模型权重目录

[English](README.md) | [简体中文](README.zh-CN.md)

本例为两阶段管线，需要**两套**权重，结构须与 `docker/predict.py` 中的 `STAGE1_MODEL["path"]` / `STAGE2_MODEL["path"]` 一致：

```text
nnUNet_results/
├── Dataset001_MyOrganCoarse/
│   └── nnUNetTrainer__nnUNetPlans__3d_fullres/
│       ├── fold_0/
│       │   └── checkpoint_final.pth
│       ├── dataset.json
│       └── plans.json
└── Dataset002_MyLesionFine/
    └── nnUNetTrainer__nnUNetPlans__3d_fullres/
        ├── fold_0/
        │   └── checkpoint_best.pth
        ├── dataset.json
        └── plans.json
```

数据集名、trainer 或 fold 不同时，同步修改 `docker/predict.py` 中的 `STAGE1_MODEL` / `STAGE2_MODEL`。

本例的裁剪与标签合并逻辑针对「粗定位 + 精细分割」这一形态编写，不构成通用管线。其他任务可参考 [`examples/standalone_nnunet/`](../../../standalone_nnunet/)，或改写本例的 `run_inference()`。
