# Model weights directory

[English](README.md) | [简体中文](README.zh-CN.md)

Before building the image, place the nnUNet model directory here. Its structure must match `NNUNET_MODEL["path"]` in `docker/predict.py`:

```text
nnUNet_results/
└── Dataset001_MyOrgans/
    └── nnUNetTrainer__nnUNetPlans__3d_fullres/
        ├── fold_0/
        │   └── checkpoint_final.pth
        ├── dataset.json
        └── plans.json
```

When switching to a different model, two places must be updated together:

| Location | What to change |
| --- | --- |
| `docker/predict.py` -> `NNUNET_MODEL` | `path`, `folds`, `checkpoint` |
| `plugin/manifest.json` -> `nodes[].outputs` | Mapping from model output values to system labels |
