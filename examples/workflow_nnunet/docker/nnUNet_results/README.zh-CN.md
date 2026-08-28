# 模型权重目录

[English](README.md) | [简体中文](README.zh-CN.md)

本例为两阶段管线，需要**两套**权重，结构须与 `docker/predict.py` 中的 `STAGE_MODELS` 一致：

```text
nnUNet_results/
├── Dataset001_MyTaskCoarse/
│   └── nnUNetTrainer__nnUNetPlans__3d_fullres/
│       ├── fold_0/
│       │   └── checkpoint_best.pth
│       ├── dataset.json
│       └── plans.json
└── Dataset002_MyTaskFine/
    └── nnUNetTrainer__nnUNetPlans__3d_fullres/
        ├── fold_0/
        │   └── checkpoint_best.pth
        ├── dataset.json
        └── plans.json
```

任何「粗定位 → ROI 裁剪 → 精细分割」的 nnUNet 流程都可复用本管线。复用到其他任务时，须同步修改三处：

| 位置 | 需要修改的内容 |
| --- | --- |
| `docker/predict.py` → `STAGE_MODELS` | 两个阶段的 `path`、`checkpoint`、`binarize` |
| `plugin/manifest.json` → `stage_fine.outputs` | 模型输出值 → 系统标签的映射 |
| `plugin/manifest.json` → `default_workflow` | `resample.target_spacing_mm`、`roi_crop.crop_margins_mm` |
