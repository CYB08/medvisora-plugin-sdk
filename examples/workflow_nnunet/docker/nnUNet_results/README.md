# Model weights directory

[English](README.md) | [简体中文](README.zh-CN.md)

This example is a two-stage pipeline and requires **two** sets of weights. Their structure must match `STAGE_MODELS` in `docker/predict.py`:

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

Any nnUNet process of the form "coarse localization -> ROI crop -> fine segmentation" can reuse this pipeline. Adapting it to another task requires updating three places:

| Location | What to change |
| --- | --- |
| `docker/predict.py` -> `STAGE_MODELS` | `path`, `checkpoint` and `binarize` of both stages |
| `plugin/manifest.json` -> `stage_fine.outputs` | Mapping from model output values to system labels |
| `plugin/manifest.json` -> `default_workflow` | `resample.target_spacing_mm`, `roi_crop.crop_margins_mm` |
