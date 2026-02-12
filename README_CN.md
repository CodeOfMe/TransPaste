# TransPaste-基于本地大语言模型的轻量级剪贴板翻译软件

TransPaste 通过 Ollama 驱动，旨在无缝融入日常工作流程，自动检测复制到剪贴板的文本，并将其替换为高质量的目标语言翻译。

## 项目背景

在当今全球化的数字环境中，对快速、准确翻译的需求无处不在。传统的翻译工作流程往往涉及繁琐的步骤：复制文本，切换到翻译网站或应用程序，粘贴文本，等待结果，复制翻译，最后切回原应用程序粘贴。这种不断的上下文切换会打断思路，降低生产力。此外，许多在线翻译服务需要将敏感数据发送到云端服务器，这对于处理机密文档或个人通信的专业人士来说引发了严重的数据隐私担忧。

TransPaste 旨在解决这两个关键问题：工作流摩擦和数据隐私。通过利用 Ollama 支持的 `gemma3:1b`、`qwen3:0.6b` 等本地 LLM 的强大功能，TransPaste 确保数据永远不会离开本地机器。翻译完全在本地硬件上进行，提供数据安全保障。此外，通过直接在剪贴板内自动化“翻译并替换”机制，TransPaste 消除了手动上下文切换的需要。用户只需复制一种语言的文本，即可立即以另一种语言粘贴，使跨语言交流像原生输入一样自然。该项目代表了朝着更集成、更私密、更高效的 AI 辅助生产力工具迈出的一步。

## 应用场景

TransPaste 用途广泛，可应用于存在语言障碍的众多场景。

1.  **跨境电商与客户支持**：支持人员经常需要用多种语言与客户沟通。TransPaste 允许其复制客户的查询并立即理解，或用母语起草回复，并将翻译版本直接粘贴到聊天窗口中，显著加快响应时间。
2.  **软件开发**：开发人员经常遇到非流利语言编写的文档、错误消息或代码注释。借助 TransPaste，日语或中文错误日志可被复制，英语解释将被粘贴到笔记或搜索引擎中，简化调试过程。其亦有助于通过将概念翻译成英语标识符来命名变量。
3.  **学术研究与阅读**：查阅国际论文的研究人员可以复制大段外文文本，并将翻译粘贴到摘要笔记中。这种流畅的工作流鼓励更深入地接触国际资源，而不会被不断的标签页切换分心。
4.  **语言学习**：语言学习者可以使用 TransPaste 来验证理解。通过复制书写的句子并粘贴回来，可以看到 AI 如何翻译，或者相反，复制外语句子以获得即时翻译，实时强化词汇和语法知识。

## 兼容硬件

由于 TransPaste 依赖于 Ollama 提供的本地 LLM 推理，硬件要求主要取决于选择运行的模型。

*   **处理器 (CPU)**：推荐使用现代多核处理器（Intel Core i5/i7/i9 或 AMD Ryzen 5/7/9）。虽然 Ollama 可以仅在 CPU 上运行，但性能会随着更高的 CPU 时钟速度和核心数显着提升，特别是对于量化模型。
*   **显卡 (GPU)**：为了获得最佳体验，强烈建议使用支持 CUDA 的专用 NVIDIA GPU。至少 4GB 显存的 GPU 可以流畅运行像 `gemma3:1b` 或 `qwen3:0.6b` 这样的较小模型。对于较大模型（7B 参数及以上），建议使用 8GB 到 16GB 的显存，以确保近乎瞬时的翻译。
*   **内存 (RAM)**：系统内存至关重要，特别是如果在 CPU 上运行模型或者模型大小超过 GPU 显存。对于运行小模型的基本操作，至少需要 8GB RAM。推荐 16GB 或 32GB 以实现更流畅的多任务处理，确保翻译过程不会拖慢其他正在运行的应用程序。
*   **存储**：强烈建议使用 SSD（固态硬盘）而不是 HDD。将模型加载到内存需要快速的读取速度。还需要足够的磁盘空间来存储模型本身；小模型可能需要 1-2GB，而更大、更高质量的模型可能占用 5GB 到 20GB 或更多。

## 操作系统

TransPaste 使用 Python 和 PySide6 框架（Qt for Python）构建，使其具有天生的跨平台特性。

*   **Windows**：该应用程序已针对 Windows 10 和 Windows 11 进行了全面测试和优化。其与 Windows 系统托盘和剪贴板子系统无缝集成。提供的截图和说明基于 Windows 环境，确保原生的外观和体验。
*   **Linux**：Linux 用户（特别是 Ubuntu 24.04）可以运行 TransPaste。应用程序强制使用 XCB 插件以确保与剪贴板操作的兼容性，即使在基于 Wayland 的系统上（通过 XWayland）。
    *   **环境要求**：确保已安装 `libxcb` 及其相关库。在 Ubuntu 上执行：
        ```bash
        sudo apt install libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 libxcb-xkb1 libxkbcommon-x11-0
        ```
    *   这确保 PySide6 应用程序可以正确启动并与系统托盘及剪贴板交互。

## 依赖环境

要成功运行 TransPaste，必须在系统上安装和配置多个软件组件和 Python 库。

1.  **Python 3.10+**：核心应用程序是用 Python 编写的。需要安装相对较新版本的 Python。推荐 Python 3.10 或更新版本，以确保与最新的类型提示功能和库优化兼容。
2.  **Ollama**：这是驱动翻译的后端引擎。必须从 [ollama.com](https://ollama.com) 下载并安装 Ollama。Ollama 充当本地服务器，托管 LLM 并公开 TransPaste 连接的 API。还必须拉取至少一个模型（例如 `ollama pull gemma3:1b`）才能使应用程序工作。
3.  **PySide6**：此库为 Qt 框架提供图形用户界面 (GUI) 绑定。其允许 TransPaste 创建系统托盘图标、菜单并高效处理系统级剪贴板事件。其是一个用于桌面应用程序开发的强大且成熟的框架。
4.  **Requests**：一个简单而强大的 Python HTTP 库。TransPaste 使用 `requests` 与本地 Ollama API 服务器通信。其处理发送提示和接收生成的翻译。
5.  **Regex (re)**：内置 Python 模块，用于对文本进行后处理，通过去除不必要的引号或来自 LLM 响应的对话填充词来确保输出干净。

## 安装过程

按照以下步骤在本地机器上设置 TransPaste。

1.  **安装 Ollama**：
    *   访问 [ollama.com](https://ollama.com) 并下载适用于操作系统的安装程序。
    *   运行安装程序并按照屏幕上的说明进行操作。
    *   打开终端或命令提示符，运行 `ollama run gemma3:1b`（或 `qwen3:0.6b`）以下载并验证模型是否正常工作。让 Ollama 服务在后台运行。

2.  **克隆仓库**：
    *   打开终端。
    *   导航到想要存储项目的目录。
    *   运行：`git clone https://github.com/CodeOfMe/TransPaste.git`
    *   进入目录：`cd TransPaste`

3.  **设置 Python 环境**：
    *   （可选但推荐）创建虚拟环境：`python -m venv venv`
    *   激活虚拟环境：
        *   Windows: `venv\Scripts\activate`
        *   Linux: `source venv/bin/activate`

4.  **安装依赖项**：
    *   TransPaste 是一个标准的 Python 包，可以通过 pip 安装：
        ```bash
        pip install .
        ```
    *   或者，如果从 PyPI 安装（发布后）：
        ```bash
        pip install transpaste
        ```

5.  **运行应用程序**：
    *   在终端执行命令：`transpaste`
    *   系统托盘中会出现一个剪贴板图标，表示程序已启动。
    *   也支持命令行参数：
        ```bash
        transpaste --model qwen3:0.6b --target French
        ```

## 运行截图

以下截图演示了 TransPaste 的使用和配置。

### 1. 启用/禁用开关
此功能提供了一种在不退出应用程序的情况下暂停翻译的快速方法。禁用时，剪贴板内容保持不变，允许进行标准的复制粘贴操作。

![启用/禁用开关](images/2-启用开关.png)

### 2. 源语言选择
右键单击系统托盘图标以访问菜单。在“源语言”下，可以选择正在复制的文本的语言。推荐一般使用“自动检测”，允许模型自动推断源语言。

![源语言选择](images/0-原始语言选择.png)

### 3. 目标语言选择
此菜单允许定义希望将文本翻译成哪种语言。默认设置为英语，但可以根据即时需求轻松切换到中文、日语、法语和许多其他语言。

![目标语言选择](images/1-目标语言选择.png)

### 4. 模型选择
TransPaste 允许选择用于翻译的本地 LLM。此菜单根据在 Ollama 中可用的模型动态填充。可以根据需要即时在像 `gemma3:1b` 或 `qwen3:0.6b` 这样的模型之间切换。

![模型选择](images/3-模型选择.png)


### 5. 实际效果

![实际效果](https://raw.githubusercontent.com/CodeOfMe/TransPaste/main/images/Demo.gif)

## 授权协议

TransPaste 是根据 **GNU 通用公共许可证 v3.0 (GPLv3)** 许可的免费开源软件。

本软件赋予使用、研究、共享和修改的自由。根据 GPLv3 的条款，允许重新分发和修改，确保软件对社区保持免费和开放。
