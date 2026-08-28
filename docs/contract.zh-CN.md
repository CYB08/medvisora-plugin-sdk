# 容器输入输出协议

[English](contract.md) | [简体中文](contract.zh-CN.md)

MedVisora 对 Docker 分割与检测插件采用统一的容器接口。平台执行 AI 节点时，将输入目录挂载至容器并调用推理脚本；容器完成推理后，在同一目录写出结果描述及相关文件。Standalone 与 Workflow 使用相同接口，镜像内部的框架和处理流程不受限制。

## 1. 固定路径

| 项目 | 默认值 | 说明 |
| --- | --- | --- |
| 挂载目录 | `/data` | 平台与容器交换数据的目录 |
| 输入影像 | `/data/input.nii.gz` | NIfTI 格式 |
| 输出描述 | `/data/output.json` | JSON 格式 |
| 推理脚本 | `/workspace/predict.py` | 可通过 `docker.script` 配置 |
| 解释器 | `python` | 可通过 `docker.entrypoint` 配置 |

Dockerfile 不应设置 `ENTRYPOINT`，以确保平台能够调用指定的解释器和推理脚本。

## 2. 命令行参数

平台调用推理脚本时提供以下参数：

| 参数 | 要求 | 说明 |
| --- | --- | --- |
| `--node-id` | 建议接收 | 当前 AI 节点的 `manifest.nodes[].id`；多节点镜像据此选择推理阶段 |
| `--input` | 必须 | 输入影像的绝对路径 |
| `--output` | 必须 | `output.json` 的绝对路径，其所在目录也是结果文件目录 |
| `--extra-params` | 建议接收 | JSON 对象字符串，包含当前节点的可调参数 |

推理脚本应使用 `parse_known_args()` 解析参数，以兼容后续扩展。

`manifest.nodes[].params` 中的 `flag` 会转换为 `--extra-params` 的键：移除前导 `--`，并将连字符替换为下划线。

平台为 AI 节点提供以下内置参数，manifest 未声明 `params` 时同样会下发：

| 键 | 适用节点 | 类型 | 说明 |
| --- | --- | --- | --- |
| `use_mirroring` | `ai_segment` | 布尔 | 是否启用镜像测试时增强 |
| `score_thresh` | `ai_detect` | 浮点 | 检测结果的置信度阈值 |

在 `manifest.nodes[].params` 中声明同名 `flag` 可覆盖其默认值。平台还可能提供 `selected_outputs`，表示用户选择的模型输出值。容器应按需读取所需的键，并为缺失的键保留自身默认值。

## 3. 输出格式

容器必须在 `--output` 指定的位置写入合法 JSON，并至少包含 `segmentation` 或 `detection`。

### 分割

分割节点将 mask 写入 `output.json` 所在目录。默认文件名为 `pred.nii.gz`：

```json
{ "segmentation": {} }
```

如需使用其他文件名，可通过 `mask_path` 声明：

```json
{ "segmentation": { "mask_path": "result.nii.gz" } }
```

`mask_path` 应为与 `output.json` 同目录的文件名。非实例分割的 mask 使用模型原始输出值，标签映射规则见 [manifest 规范](manifest.zh-CN.md)。

### 检测

检测节点通过 `detection.nodules` 返回目标列表，无需写出 mask。每个目标应包含与输入影像一致的物理坐标和尺寸，单位为毫米：

```json
{
  "detection": {
    "nodules": [
      {
        "center_mm": { "x": 12.5, "y": -33.0, "z": 88.2 },
        "size_mm": { "width": 8.1, "height": 7.6, "depth": 9.0 },
        "confidence": 87.0
      }
    ]
  }
}
```

`center_mm` 与 `size_mm` 为必填字段；`confidence` 为可选字段，取值范围为 0–100。除上述字段外可附加自定义字段，平台不解析这些字段，其存在不影响结果处理。

### 实例分割

实例分割节点须在 manifest 中声明 `instance: true`，并按照实例分割规范写出 mask 和语义列表：

```json
{
  "segmentation": {
    "instance": true,
    "labels": [
      { "label": 1000, "semantic": "Instance 1" },
      { "label": 1001, "semantic": "Instance 2" }
    ]
  }
}
```

实例分割 mask 须直接使用平台预留的实例标签，并与 `labels` 中的值保持一致，不使用 `outputs` 映射。标签范围及 manifest 配置要求见 [manifest 规范](manifest.zh-CN.md)。

同一结果可以同时包含 `segmentation` 与 `detection`。

## 4. 进度上报

推理脚本可通过标准输出上报进度：

```text
PROGRESS:35:Running inference
```

格式为 `PROGRESS:<0-100>:<message>`，消息可以为空。建议在 Dockerfile 中设置 `PYTHONUNBUFFERED=1`，避免输出缓冲影响进度更新。

## 5. 成功与失败

- 容器退出码为 `0`，且结果描述及其声明的文件有效时，任务执行成功。
- 退出码非 `0`、`output.json` 缺失或无法解析、声明的结果文件不存在时，任务执行失败。
- 用户取消任务时，平台将终止当前容器。

Docker 资源、节点参数、标签映射和实例分割配置见 [manifest 规范](manifest.zh-CN.md)；工作流节点与连接规则见 [节点规范](nodes.zh-CN.md)。
