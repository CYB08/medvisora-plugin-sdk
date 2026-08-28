# Model weights directory (`stage_seg` node)

[English](README.md) | [简体中文](README.zh-CN.md)

Place the nnUNet model directory for the `stage_seg` node here. Its structure must match `SEG_MODEL["path"]` in `docker/predict.py`:

```text
nnUNet_results/
└── Dataset001_MyLungSeg/
    └── nnUNetTrainer__nnUNetPlans__3d_fullres/
        ├── fold_0/
        │   └── checkpoint_final.pth
        ├── dataset.json
        └── plans.json
```

When the dataset name, the trainer or the fold differs, update `SEG_MODEL` in `docker/predict.py` accordingly.

The weights of the other node, `stage_detect`, are a single `.pt` file located in [`../model/`](../model/README.md).
