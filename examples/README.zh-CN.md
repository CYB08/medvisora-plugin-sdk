# 示例

[English](README.md) | [简体中文](README.zh-CN.md)

MedVisora 不限制模型架构、训练框架、运行环境与内部处理流程。只要将推理封装为 Docker 镜像并遵循平台输入输出协议，即可完成接入。本目录以 **nnUNet** 与 **MONAI** 为例，演示 Standalone 与 Workflow 两种封装方式。

可将本 SDK 的文档与模板连同目标模型的规格一并提供给 GPT、Claude 等大语言模型，用于生成推理脚本与镜像构建配置。模板与示例已按统一结构组织，便于模型直接理解并复用。

| 示例 | 模式 | 要点 | 部署步骤 |
| --- | --- | --- | --- |
| `standalone_nnunet` | Standalone | 通用单节点分割，更换任务仅需替换权重与 manifest | [见下](#部署-standalone_nnunet) |
| `workflow_nnunet` | Workflow | 通用两阶段分割，重采样、裁剪与还原交由平台节点 | [见下](#部署-workflow_nnunet) |
| `standalone_lung_tumor_nnunet` | Standalone | 两阶段流程封装为单节点，裁剪与还原在容器内完成 | [见下](#部署-standalone_lung_tumor_nnunet) |
| `workflow_lung_nodule_detection` | Workflow | 单个镜像提供分割与检测两类 AI 节点，`roi_crop` 采用 `filter` 模式 | [见下](#部署-workflow_lung_nodule_detection) |

Standalone 适用于在单个容器内完成全部处理的场景。若需在画布中编排工作流，或与平台节点拼接，可选用 Workflow。

本仓库不分发模型权重与 nnUNet 源码，构建镜像前须自行准备。nnUNet 示例的权重放入各自的 `docker/nnUNet_results/`，`workflow_lung_nodule_detection` 另需将检测权重放入 `docker/model/`；两处目录下均有 `README.md` 说明所需结构。

注册 `manifest.json` 不会打包或安装镜像。构建完成后须确认 `docker images` 中存在 `docker.image` 指定的 tag，平台在启动推理前会检查镜像可用性。

以下命令均以 SDK 根目录为工作目录执行。

## 快速开始：从空模板起步

不基于 nnUNet、需要自行实现推理代码时，从 `templates/` 起步：单 AI 节点使用 `templates/standalone`，多 AI 节点并需要提供默认工作流时使用 `templates/workflow`。

**1. 复制模板**

```bash
cp -r templates/standalone my-model
```

Windows PowerShell 使用 `Copy-Item -Recurse templates/standalone my-model`。

**2. 实现推理**

在 `my-model/docker/predict.py` 的 `USER EDIT AREA` 中实现模型加载与推理。文件其余部分为平台 I/O 契约，请勿修改。

**3. 构建镜像**

```bash
docker build -t my-model:1.0 my-model/docker/
```

权重或 `predict.py` 变更后必须更换 tag，并同步更新 `manifest.json` 中的 `docker.image`。

**4. 编写 manifest**

在 `my-model/plugin/manifest.json` 中填写与构建 tag 一致的镜像名，并声明 AI 节点：

```json
{ "docker": { "image": "my-model:1.0" } }
```

Workflow 模式下，每个 `nodes[].id` 须与 `predict.py` 路由表中的 key 完全一致。

**5. 校验**

```bash
python tools/validate.py my-model/plugin/manifest.json
```

**6. 导入**

在 MedVisora 中选择「模型卡 → 注册模型卡」（Ctrl+Shift+A），在对话框中选择 `my-model/plugin/manifest.json`。

## 部署 standalone_nnunet

单 AI 节点，一次推理输出分割 mask，需要一套 nnUNet 权重。

**1. 获取 nnUNet 源码**

```bash
git clone --branch v2.8.1 --depth 1 https://github.com/MIC-DKFZ/nnUNet.git examples/standalone_nnunet/docker/nnUNet
```

**2. 放入模型权重**

将 nnUNet 模型目录放入 `examples/standalone_nnunet/docker/nnUNet_results/`，结构须与 `docker/predict.py` 中的 `NNUNET_MODEL["path"]` 一致，详见该目录的 [`README.md`](standalone_nnunet/docker/nnUNet_results/README.zh-CN.md)。

**3. 构建镜像**

完成前两步后，`examples/standalone_nnunet/docker/` 应包含：

```text
docker/
├── Dockerfile
├── predict.py
├── requirements.txt
├── nnUNet/
└── nnUNet_results/
    └── Dataset001_MyOrgans/
        └── nnUNetTrainer__nnUNetPlans__3d_fullres/
            ├── fold_0/
            ├── dataset.json
            └── plans.json
```

```bash
docker build -t my-organ-seg:1.0 examples/standalone_nnunet/docker/
```

**4.（可选）校验**

```bash
python tools/validate.py examples/standalone_nnunet/plugin/manifest.json
```

**5. 导入 MedVisora**

选择「模型卡 → 注册模型卡」（Ctrl+Shift+A），在对话框中选择 `examples/standalone_nnunet/plugin/manifest.json`。

## 部署 workflow_nnunet

两个 AI 节点，管线为重采样、粗定位、ROI 裁剪、精细分割、空间还原，需要两套 nnUNet 权重。

**1. 获取 nnUNet 源码**

```bash
git clone --branch v2.8.1 --depth 1 https://github.com/MIC-DKFZ/nnUNet.git examples/workflow_nnunet/docker/nnUNet
```

**2. 放入模型权重**

粗定位与精细分割的两套权重均放入 `examples/workflow_nnunet/docker/nnUNet_results/`，结构须与 `docker/predict.py` 中的 `STAGE_MODELS` 一致，详见该目录的 [`README.md`](workflow_nnunet/docker/nnUNet_results/README.zh-CN.md)。

**3. 构建镜像**

```text
docker/
├── Dockerfile
├── predict.py
├── requirements.txt
├── nnUNet/
└── nnUNet_results/
    ├── Dataset001_MyTaskCoarse/
    │   └── nnUNetTrainer__nnUNetPlans__3d_fullres/
    └── Dataset002_MyTaskFine/
        └── nnUNetTrainer__nnUNetPlans__3d_fullres/
```

```bash
docker build -t my-twostage-seg:1.0 examples/workflow_nnunet/docker/
```

**4.（可选）校验**

```bash
python tools/validate.py examples/workflow_nnunet/plugin/manifest.json
```

**5. 导入 MedVisora**

导入后 `default_workflow` 会自动编排为可从模型卡直接启动的工作流。重采样间距与裁剪范围可在 `default_workflow.nodes[*].params` 中修改，或导入后在工作流画布中调节。

## 部署 standalone_lung_tumor_nnunet

与 `workflow_nnunet` 相同的两阶段流程，但封装为单个 AI 节点：ROI 裁剪与空间还原在容器内完成，因此同样需要两套 nnUNet 权重。

**1. 获取 nnUNet 源码**

```bash
git clone --branch v2.8.1 --depth 1 https://github.com/MIC-DKFZ/nnUNet.git examples/standalone_lung_tumor_nnunet/docker/nnUNet
```

**2. 放入模型权重**

粗定位与精细分割的两套权重均放入 `examples/standalone_lung_tumor_nnunet/docker/nnUNet_results/`，结构须与 `docker/predict.py` 中的 `STAGE1_MODEL` 与 `STAGE2_MODEL` 一致，详见该目录的 [`README.md`](standalone_lung_tumor_nnunet/docker/nnUNet_results/README.zh-CN.md)。

**3. 构建镜像**

```bash
docker build -t my-lung-tumor:1.0 examples/standalone_lung_tumor_nnunet/docker/
```

**4.（可选）校验**

```bash
python tools/validate.py examples/standalone_lung_tumor_nnunet/plugin/manifest.json
```

**5. 导入 MedVisora**

裁剪范围由 `docker/predict.py` 中的 `CROP_MARGIN_MM` 固定，调整后须重新构建镜像。若需在界面上调节该参数，改用 `workflow_nnunet` 的拆分方式。

## 部署 workflow_lung_nodule_detection

单个镜像提供两个 AI 节点：分割节点输出 mask，检测节点输出目标列表。需要一套 nnUNet 分割权重和一份 TorchScript 检测权重。

**1. 获取 nnUNet 源码**

```bash
git clone --branch v2.8.1 --depth 1 https://github.com/MIC-DKFZ/nnUNet.git examples/workflow_lung_nodule_detection/docker/nnUNet
```

**2. 放入模型权重**

分割权重放入 `examples/workflow_lung_nodule_detection/docker/nnUNet_results/`，检测权重放入 `examples/workflow_lung_nodule_detection/docker/model/`，分别详见 [`nnUNet_results/README.md`](workflow_lung_nodule_detection/docker/nnUNet_results/README.zh-CN.md) 与 [`model/README.md`](workflow_lung_nodule_detection/docker/model/README.zh-CN.md)。

**3. 构建镜像**

```text
docker/
├── Dockerfile
├── predict.py
├── requirements.txt
├── nnUNet/
├── nnUNet_results/
│   └── Dataset001_MyLungSeg/
│       └── nnUNetTrainer__nnUNetPlans__3d_fullres/
└── model/
    └── detector.pt
```

```bash
docker build -t my-lung-nodule:1.0 examples/workflow_lung_nodule_detection/docker/
```

本例额外依赖 MONAI，构建耗时长于其余三个示例。

**4.（可选）校验**

```bash
python tools/validate.py examples/workflow_lung_nodule_detection/plugin/manifest.json
```

**5. 导入 MedVisora**

导入后 `default_workflow` 会将分割节点的输出作为检测节点的 ROI 过滤依据。检测阈值可在模型卡或工作流画布中调节。

## 基于示例部署自定义模型

推荐从 `standalone_nnunet` 起步：

1. 将权重复制到 `docker/nnUNet_results/`
2. 修改 `docker/predict.py` 中的 `NNUNET_MODEL`（Workflow 为 `STAGE_MODELS`），使路径与权重目录一致
3. 构建镜像并记录 tag：`docker build -t my-nnunet:1.0 examples/standalone_nnunet/docker/`
4. 编辑 `plugin/manifest.json`：更新 `docker.image`，并按模型输出配置 `outputs` 标签映射

```json
"docker": { "image": "my-nnunet:1.0", "ipc": "host" },
"nodes": [
  {
    "id": "inference",
    "title": "AI Inference",
    "category": "ai_segment",
    "outputs": [
      { "model": 1, "label": 5 },
      { "model": 2, "label": 6, "group": "Group A" }
    ]
  }
]
```

5. 校验后导入 MedVisora

## 第三方组件

示例引用的 [nnUNet](https://github.com/MIC-DKFZ/nnUNet) 与 [MONAI](https://github.com/Project-MONAI/MONAI) 均以 Apache License 2.0 分发，其权重与源码不随本仓库提供，使用时须遵守各自的许可条款。
