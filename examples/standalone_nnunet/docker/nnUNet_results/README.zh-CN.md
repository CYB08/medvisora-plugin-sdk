# 模型权重目录

[English](README.md) | [简体中文](README.zh-CN.md)

构建镜像前，将 nnUNet 模型目录放入此处，结构须与 `docker/predict.py` 中的 `NNUNET_MODEL["path"]` 一致：

```text
nnUNet_results/
└── Dataset001_MyOrgans/
    └── nnUNetTrainer__nnUNetPlans__3d_fullres/
        ├── fold_0/
        │   └── checkpoint_final.pth
        ├── dataset.json
        └── plans.json
```

替换为其他模型时，须同步修改两处：

| 位置 | 需要修改的内容 |
| --- | --- |
| `docker/predict.py` → `NNUNET_MODEL` | `path`、`folds`、`checkpoint` |
| `plugin/manifest.json` → `nodes[].outputs` | 模型输出值 → 系统标签的映射 |
