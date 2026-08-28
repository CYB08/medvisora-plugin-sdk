# manifest 注册规范

[English](manifest.md) | [简体中文](manifest.zh-CN.md)

`manifest.json` 用于声明 Docker 镜像、模型信息及其提供的 AI 节点。平台读取并校验该文件后生成模型卡，并将相应节点加入工作流。

## 1. 最小示例

以下配置适用于单节点分割插件：

```json
{
  "key": "my_model",
  "name": "My Model",
  "version": "v1.0",
  "task": ["segmentation"],
  "docker": {
    "image": "my-model:1.0"
  },
  "nodes": [
    {
      "id": "inference",
      "title": "AI Inference",
      "category": "ai_segment",
      "outputs": [
        { "model": 1, "label": 2 }
      ]
    }
  ]
}
```

`docker.image` 必须与本地构建或导入的镜像名称一致。

## 2. 顶层字段

| 字段 | 要求 | 说明 |
| --- | --- | --- |
| `key` | 必填 | 插件唯一标识，可使用字母、数字、下划线、连字符和点 |
| `name` | 必填 | 模型卡名称 |
| `version` | 必填 | 展示版本 |
| `task` | 必填 | 任务类型数组，例如 `segmentation` 或 `detection` |
| `docker` | 必填 | Docker 镜像及运行配置 |
| `nodes` | 必填 | 插件提供的 AI 节点 |
| `team` | 可选 | 作者或团队 |
| `desc` | 可选 | 简要说明 |
| `modality` | 可选 | 影像模态，例如 `CT` 或 `MR` |
| `default_workflow` | 可选 | 模型卡默认工作流 |

## 3. Docker 配置

| 字段 | 要求 | 说明 |
| --- | --- | --- |
| `image` | 必填 | Docker 镜像名称和 tag |
| `script` | 可选 | 推理脚本路径，默认 `/workspace/predict.py` |
| `entrypoint` | 可选 | 脚本解释器，默认 `python` |
| `gpus` | 可选 | Docker GPU 参数；省略时使用平台配置，空字符串表示不添加 GPU 参数 |
| `shm_size` | 可选 | 容器共享内存大小 |
| `ipc` | 可选 | Docker IPC 配置 |
| `cpus` | 可选 | 容器 CPU 限制 |

示例：

```json
{
  "docker": {
    "image": "my-model:1.0",
    "ipc": "host"
  }
}
```

## 4. AI 节点

每个 `nodes[]` 条目声明镜像提供的一项 AI 能力：

| 字段 | 要求 | 说明 |
| --- | --- | --- |
| `id` | 必填 | 节点唯一标识，也是传入容器的 `--node-id` |
| `title` | 必填 | 工作流中的显示名称 |
| `category` | 必填 | `ai_segment` 或 `ai_detect` |
| `outputs` | 可选 | 分割模型输出值与平台标签的映射 |
| `params` | 可选 | 可在界面调节的推理参数 |
| `instance` | 可选 | 实例分割节点设为 `true` |
| `args` | 可选 | 传给推理脚本的固定参数数组 |

多节点镜像中，`id` 必须与推理脚本的节点路由标识一致。

`id` 仅允许使用字母、数字、下划线和连字符，不得包含点，也不得与平台节点名称或 `ai_segment`、`ai_detect` 重名。

### outputs

`outputs` 仅适用于 `ai_segment`，用于将模型输出值映射为平台支持的语义标签：

```json
{
  "outputs": [
    { "model": 1, "label": 2, "group": "Group A" }
  ]
}
```

- `model`：模型 mask 中的原始值，必须为正整数，同一节点内不得重复
- `label`：平台系统标签表中已分配的语义标签 ID，取值范围为 `1–999`
- `group`：可选，仅用于模型卡中的结果分组

标签名称由平台维护，`outputs` 不得声明 `semantic`。未声明 `outputs` 时，平台保留 mask 的原始值。实例分割节点不得声明 `outputs`。

### params

`params` 用于声明用户可调的推理参数。参数将通过 `--extra-params` 传入容器：

```json
{
  "params": [
    {
      "flag": "--threshold",
      "title": "Threshold",
      "default": 0.5,
      "min": 0.0,
      "max": 1.0
    }
  ]
}
```

| 字段 | 要求 | 说明 |
| --- | --- | --- |
| `flag` | 必填 | 参数标识，须采用 `--name` 格式，同一节点内不得重复 |
| `title` | 建议 | 界面显示名称 |
| `default` | 可选 | 默认值；声明 `options` 时须为其中之一 |
| `min`、`max` | 可选 | 数值范围，`min` 不得大于 `max` |
| `options` | 可选 | 离散取值数组，不得为空 |

分割节点内置 `--use-mirroring`、检测节点内置 `--score-thresh`，无需声明即可生效；使用同名 `flag` 可覆盖其默认值。参数传入容器的键名规则见[容器输入输出协议](contract.zh-CN.md)。

### instance

实例分割节点应设置 `instance: true`，并省略 `outputs`：

```json
{
  "id": "instance_seg",
  "title": "Instance Segmentation",
  "category": "ai_segment",
  "instance": true
}
```

实例 mask 使用平台预留标签 `1000–1099`，并在 `output.json` 中返回相同标签及其语义。输出格式见[容器输入输出协议](contract.zh-CN.md)。

## 5. Standalone 与 Workflow

模型卡上的封装模式由 AI 节点数量决定：声明一个 AI 节点为 Standalone，两个及以上为 Workflow。

能否从模型卡直接启动推理，取决于平台能否确定运行图：

- 单个 AI 节点且未声明 `default_workflow`：平台自动构建 `image_input → AI 节点 → display_output` 的最小工作流
- 声明了 `default_workflow`：按该工作流运行
- 多个 AI 节点且未声明 `default_workflow`：须在工作流画布中手动编排后运行

需要将 AI 节点与平台节点组合时，在 `default_workflow` 中声明节点与连线：

```json
{
  "default_workflow": {
    "nodes": [
      { "kind": "image_input" },
      {
        "kind": "resample",
        "params": { "target_spacing_mm": [2.0, 2.0, 2.0] }
      },
      { "kind": "inference" },
      { "kind": "display_output" }
    ],
    "edges": [
      ["image_input.image", "resample.image"],
      ["resample.image", "inference.image"],
      ["inference.mask", "display_output.mask"]
    ]
  }
}
```

`kind` 使用平台节点名称或顶层 `nodes[].id`。边的格式为 `["源节点.端口", "目标节点.端口"]`。可用节点、端口及参数见[工作流节点规范](nodes.zh-CN.md)。

模型卡默认工作流支持在 `resample` 和 `roi_crop` 节点中声明 `params`；其他节点参数可在工作流画布中配置。

工作流可内联于 `default_workflow`，也可外置为与 `manifest.json` 同目录的 `workflow.json`；两者同时存在时以内联声明为准。

## 6. 校验与导入

离线校验支持传入 manifest 文件或插件目录，路径相对于当前工作目录：

```bash
python tools/validate.py path/to/plugin/manifest.json
python tools/validate.py path/to/plugin/
```

校验通过后，在 MedVisora 中选择「模型卡 → 注册模型卡」，导入 `manifest.json`。注册过程不包含镜像分发，运行前 `docker.image` 指定的 tag 须在本机可用。

离线工具用于检查文件结构与工作流连接；`outputs.label` 是否属于平台已分配标签，以导入时的校验结果为准。

完整配置见 [`templates/`](../templates/) 和 [`examples/`](../examples/)。
