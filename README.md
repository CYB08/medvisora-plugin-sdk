# MedVisora Plugin SDK

[English](README.md) | [简体中文](README.zh-CN.md)

Project homepage: [https://medvisora.com/](https://medvisora.com/)

Download MedVisora for Windows: [MedVisora_Setup_1.0.0.exe](https://github.com/CYB08/medvisora-plugin-sdk/releases/download/v1.0.0/MedVisora_Setup_1.0.0.exe)

MedVisora is a model integration and workflow platform for medical imaging that brings inference, image interaction and workflow orchestration together in one system. A single plugin specification lets you package a local model as a Docker image and register it as a model card, which immediately gives that model the platform's existing reading, annotation, 3D reconstruction and quantitative analysis capabilities. Its AI nodes can be wired to platform nodes on the canvas to form multi-stage segmentation, detection and analysis pipelines, with no front-end development required.

Integration takes two steps: build the inference image, then register it through `plugin/manifest.json`. The container must follow the [container I/O contract](docs/contract.md).

**Segmentation model card plugin**

![Segmentation model card plugin](pic/pic1.png)

**Rendering model card plugin**

<img src="pic/pic2.png" width="49%" alt="Rendering model card plugin"> <img src="pic/pic3.png" width="49%" alt="Rendering model card plugin">

`templates/` provides a minimal project skeleton: implement its inference entry point and the image is ready to build. `examples/` provides complete cases with deployment steps, described in the [examples guide](examples/README.md). Configuration fields and workflow rules are covered by the [manifest specification](docs/manifest.md) and the [node specification](docs/nodes.md).

## Support

Report bugs, or ask about model integration and image builds, via [Issues](https://github.com/CYB08/medvisora-plugin-sdk/issues) or [medvisora@163.com](mailto:medvisora@163.com).

This repository is distributed under the [LICENSE](LICENSE) in the repository root.
