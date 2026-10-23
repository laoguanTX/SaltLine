# 用户兼容性与排查

SaltLine 面向 **Linux 原生 SaltPlayer 1.19.0+、Cinnamon 水平面板**。安装包内只有 JVM 字节码、Python 和小程序资源，不包含开发者电脑的 JDK、用户配置或发行版专用二进制文件。

## 支持范围

| 环境 | 安装路径与验证范围 |
| --- | --- |
| 原生播放器 + Cinnamon | 优先系统 Python 3.8+；无 Python GI 时改用 gdbus。本机 Cinnamon 6.6.9 实测安装、加载、绘制。 |
| 发行版原生 Steam + Steam Runtime | 从运行时自带接口调用宿主工具，保留宿主桌面的 PATH、HOME、XDG 环境；已实测本机 Steam 宿主启动链路。 |
| Ubuntu 22.04 / 24.04 | GitHub Actions 分别使用系统 Python 构建、运行隔离安装生命周期与无 GI 测试。CI 不等同于真实桌面播放验证。 |
| Mint、Debian、Fedora、Arch 的 Cinnamon | 安装器不硬编码用户名、包管理器或 CPU 架构，支持自定义 Python PATH；仍需要对应发行版用户实测反馈。 |
| Flatpak Steam / 播放器 | 暂不支持自动访问宿主面板。安装器会明确提示使用原生版本，不自动申请或扩大沙箱权限。 |
| GNOME、KDE、Windows、Wine、仅竖直面板 | 不支持本小程序；没有运行 Cinnamon 时不修改面板设置。 |

用户只需订阅并启用模组，不需要安装 JDK、Node.js 或下载依赖 JAR。封面功能需要授予模组的读取曲库权限。

## 安装与更新的保护

- 安装前检测桌面会话；无 Cinnamon 时不写入小程序文件。
- 临时目录在用户共享缓存中，支持含空格、中文和自定义 XDG 路径。
- 面板从安装器生成的 `bridge.json` 读取播放器实际缓存路径；歌词和封面共用此目录，避免两端 XDG 不同导致一直等待。
- 读写面板配置失败会明确报错；写入成功后确认小程序完成初始化，否则显示恢复建议。
- 桌面尚未就绪或安装锁被占用时最多尝试三次；不持续弹窗或无限重试。
- 重复启用不会创建重复条目，多个面板优先选择主显示器的水平面板。
- 保留其他小程序、原有手动条目与用户配置；不自动安装系统软件，不需要管理员权限。

## 日志与自检

安装过程会保留一份限长诊断日志：

```text
$XDG_CACHE_HOME/saltplayer-barlyrics/integration.log
```

默认是 `~/.cache/saltplayer-barlyrics/integration.log`。日志记录运行路径（native / steam-host）、操作、结果和错误原因，不包含歌曲内容、密码或令牌；不会自动上传。反馈时可先检查并隐去自己的用户名和本机路径。

如需从源码进行只读自检，可在项目根目录运行：

```bash
python3 -I plugin/src/main/resources/cinnamon-installer.py diagnose
```

只读自检不创建安装记录或修改面板配置。输出包括 Python / 通信后端、是否存在水平面板、是否已加载小程序等。

## 常见情况

- **没有 Python 3**：按发行版的正常方式安装 Python 3.8+，再启用模组；不要使用 pip 安装 `gi` 来替换系统组件。
- **缺少 gdbus 且无 GI**：安装发行版提供的 GLib 命令行工具或 PyGObject，随后重试。安装器不会代为执行提权命令。
- **文件已安装但小程序未加载**：打开 Cinnamon 系统设置 → 小程序，检查“盐词”的加载错误；重新登录桌面后再启用模组。
- **等待连接**：确认模组启用，检查 `bridge.json` 指向的 `state.json` 是否持续更新。旧版手动小程序可通过新版模组重新启用更新。
- **没有逐字效果**：歌曲必须带逐字时间戳；普通 LRC 无法自动得到真实逐字时间。
- **封面缺失**：检查读取曲库权限与歌曲的内嵌专辑图片。

反馈建议附：发行版、Cinnamon / SaltPlayer / SaltLine 版本、Steam 原生或 Flatpak、复现步骤，以及经检查的安装日志。其他发行版和真实歌曲的兼容性仍需实测，不能仅凭自动测试保证所有用户环境。
