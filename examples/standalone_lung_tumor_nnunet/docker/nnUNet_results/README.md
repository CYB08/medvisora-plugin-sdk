# Model weights directory

[English](README.md) | [简体中文](README.zh-CN.md)

This example is a two-stage pipeline and requires **two** sets of weights. Their structure must match `STAGE1_MODEL["path"]` and `STAGE2_MODEL["path"]` in `docker/predict.py`:

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

When the dataset name, the trainer or the fold differs, update `STAGE1_MODEL` and `STAGE2_MODEL` in `docker/predict.py` accordingly.

The cropping and label-merging logic of this example is written for the "coarse localization plus fine segmentation" shape and is not a general pipeline. For other tasks, refer to [`examples/standalone_nnunet/`](../../../standalone_nnunet/) or rewrite `run_inference()` here.
