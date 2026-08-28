# 工作流节点规范

[English](nodes.md) | [简体中文](nodes.zh-CN.md)

工作流由节点和有向边组成。节点通过端口接收或输出数据，边用于声明数据流向。完整工作流必须无环。

## 1. 平台节点

| `kind` | 作用 | 输入 | 输出 | 参数 |
| --- | --- | --- | --- | --- |
| `image_input` | 提供当前影像 | – | `image` | – |
| `resample` | 重采样至目标体素间距 | `image` | `image` | `target_spacing_mm: [x, y, z]` |
| `roi_crop` | 按 mask 裁剪或过滤影像 | `image`, `mask` | `image`, `bbox` | `crop_mode`, `crop_margins_mm`, `filter_dilate_mm` |
| `mask_restore` | 将裁剪后的 mask 还原至原始空间 | `mask`, `bbox` | `mask` | – |
| `radiomics` | 计算结构定量结果 | `image`, `mask` | `metrics` | `mode`, `structures` |
| `display_output` | 展示工作流结果 | `mask`, `detections` 或 `metrics` | – | – |
| `image_export` | 导出影像 | `image` | – | `export_dir` |

`roi_crop.crop_mode` 支持 `bbox` 和 `filter`；`radiomics.mode` 支持 `basic` 和 `radiomics`。

表中参数适用于工作流画布。写入模型卡的 `default_workflow` 时，仅支持配置 `resample` 和 `roi_crop` 的参数。

## 2. AI 节点

AI 节点由 `manifest.nodes[]` 声明：

| `category` | 输入 | 输出 |
| --- | --- | --- |
| `ai_segment` | `image` | `mask` |
| `ai_detect` | `image` | `detections` |

在 `default_workflow.nodes[]` 中，AI 节点的 `kind` 必须填写对应的 `nodes[].id`，不能直接填写 `ai_segment` 或 `ai_detect`。

## 3. 节点与连线

工作流节点使用以下格式：

```json
{
  "kind": "resample",
  "id": "resample_input",
  "params": {
    "target_spacing_mm": [2.0, 2.0, 2.0]
  }
}
```

- `kind`：平台节点名称或 manifest 中声明的 AI 节点 `id`
- `id`：工作流内的节点标识；省略时默认与 `kind` 相同
- `params`：当前节点的参数

同一种节点使用多次时，每个节点必须设置不同的 `id`。

边使用 `["源节点.输出端口", "目标节点.输入端口"]` 格式：

```json
[
  ["image_input.image", "resample_input.image"],
  ["resample_input.image", "inference.image"],
  ["inference.mask", "display_output.mask"]
]
```

连线须满足以下要求：

- 源端口与目标端口的数据类型一致
- 每个输入端口最多连接一条边
- 所有必需输入均已连接
- 工作流中至少包含一个 manifest 声明的 AI 节点
- 工作流不存在循环依赖

Standalone 插件无需声明连线。Workflow 可通过 `default_workflow` 提供默认编排，也可由用户在画布中完成编排。

完整写法见 [manifest 注册规范](manifest.zh-CN.md)，可运行案例见 [`examples/`](../examples/)。
