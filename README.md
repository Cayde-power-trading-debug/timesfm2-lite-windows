# TimesFM 2.0 Lite for Windows

一个独立的 Windows 本地时间序列预测工具。只输入时间和数字，使用官方 **TimesFM 2.0 500M** 模型预测，并导出可独立打开的输入、结果 HTML 和 CSV。

支持 NVIDIA GPU 与 CPU；默认自动检测设备。不依赖现有 SaaS、企业数据库或系统 Python。

## 下载与运行

从 [Releases](https://github.com/Cayde-power-trading-debug/timesfm2-lite-windows/releases/latest) 下载 `timesfm2-lite-windows-v1.0.0.zip`，完整解压到可写目录。

1. 双击 **一键安装.cmd**。首次需要联网安装依赖并下载官方模型；包含真实预测自检。
2. 双击 **启动.cmd**，浏览器打开本地页面 `http://127.0.0.1:8899`。
3. 输入时间与数值，或输入开始时间后粘贴一列数值，检查输入后开始预测。
4. 输入、输出、CSV、复现信息保存在同一个 `输入与输出/批次编号/` 目录。

下载 ZIP 或克隆本仓库均包含便携 Python 的官方压缩包，首次安装时解压。**仓库和发布 ZIP 不包含模型权重**，首次安装脚本从 Google 官方 Hugging Face 仓库下载固定版本并校验 SHA256。依赖与模型下载需要数 GB 空间；完成安装后可离线预测。

仅打开 HTML 不能运行模型：请先安装并运行本地服务。

## CPU 与 GPU

```powershell
# 自动选择；无可用 GPU 时兼容 CPU
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Task Install

# 没有 GPU 的电脑，安装纯 CPU 版本
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Task Install -Device cpu
```

GPU 模式使用官方 PyTorch CUDA 12.4 轮子，运行组件随轮子安装，无需完整 CUDA Toolkit。GPU 驱动单独使用 `GPU驱动安装.cmd` 或脚本的 Driver 任务；有效驱动不会自动重装或降级，需要更新时由用户选择适配硬件的 NVIDIA 官方签名安装器。

## 功能与边界

- 上下文上限 **2048 点**；超过上限使用最新 2048 点，导出仍保留全部输入和实际消费范围。
- 预测步数 1–2048，可选择 15 分钟、30 分钟、小时或日采样。
- 真实零值保留；缺失可选择使用此前有效数值的因果中位数补齐。
- 输入与输出标注中国节假日、补班日、普通周末；内置 2025、2026 年官方日期。未覆盖年份明确标注未知。
- 节假日标签用于展示，**不作为 TimesFM 单变量模型的节假日修正项**。
- 不包含天气门控、企业分摊、停工修正或申报策略。

## 文档

- [完整使用说明](使用说明.md)：所有安装、下载、驱动、参数与导出命令。
- [节假日维护说明](节假日维护说明.md)：下一年度官方通知的下载、识别、核对和更新。
- [测试记录](docs/测试记录.md)：测试范围与限制。
- [第三方组件说明](THIRD_PARTY_NOTICES.md)：Python、pip、TimesFM 与其他依赖的来源和许可证。

## 测试

业务逻辑及 HTTP/导出测试不需要下载模型：

```powershell
python -m unittest discover -s tests -v
```

安装完成后的真实模型自检：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Task Test -Device cpu
```

测试使用合成序列，只证明软件功能可运行，不证明具体业务数据的预测准确率。

## License

本仓库自主代码按 [MIT License](LICENSE) 发布。第三方组件和下载的模型分别遵守各自许可证；本工具与 Google、Python Software Foundation、PyTorch 或 NVIDIA 无官方隶属关系。
