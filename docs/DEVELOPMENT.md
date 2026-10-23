# 开发与验证

源码使用 Java，编译需要 **JDK 25 或更新版本**、Python 3 和网络（首次下载依赖）。设置 `JAVA_HOME` 后：

```bash
python3 scripts/build.py
python3 scripts/test.py
```

构建脚本也会查找 PATH 中的 javac 和 `.cache/jdk-*/bin/javac`。完整测试另需 Node.js、系统 Python 的 PyGObject 和 Cinnamon 设置架构。构建与测试从项目根目录运行。

产物为 `dist/saltline-1.2.1.spmod` 和 `dist/saltline-cinnamon-1.2.1.zip`。`.spmod` 按官方格式包含 `classes/META-INF/MANIFEST.MF`、PF4J 扩展索引及插件类；不打包宿主 API、Kotlin 或 PF4J，避免类加载冲突。

```text
plugin/src/main/java/local/saltbar/
  MainPlugin.java         启停与当前歌词初始化
  PlaybackListener.java   官方播放扩展回调
  Bridge.java             同步、序列化与原子写入
  CoverArt.java           官方封面读取、缩略图与换歌竞态处理
  CinnamonIntegration.java  嵌入资源提取与后台安装／停用
plugin/src/main/resources/
  cinnamon-installer.py   用户目录安装、面板管理与所有权清理
cinnamon/saltbar@local/
  applet.js               面板绘制、异步读取、设置与清理
  timeline.js             时间和文字计算
  theme.js                封面取色、明暗适配和翻译单行处理
scripts/                  编译、测试和小程序安装
tests/                   Java 与 JavaScript 测试
```

已验证：针对真实 dev22 API 编译；时间边界、间奏与回退跳转；JSON 特殊字符、中文和 Emoji；写入与停用清理；JavaScript 时间插值、暂停、补偿和 UTF-8 字节偏移；Cinnamon 实际加载、读取测试快照和绘制。另已验证缩略图裁剪、损坏图片、迟到封面丢弃、透明像素过滤、深浅面板主题色，以及 Cinnamon 异步图片加载和 36/44 像素的双行绘制。此外，15 项安装器回归测试覆盖幂等、升级、自动条目移动、手动布局保留、迟到停用、重新启动后删除、中断恢复、哈希及路径校验。Java 已用包内真实资源完成隔离目录中的安装、停用、重新启用和删除验证；本机真实安装器升级后，Cinnamon 已加载 1.2.0。**SaltPlayer 内真实启停回调仍需导入新版模组后验证**。

运行中的 Cinnamon 可额外验证图片加载与绘制（使用独立测试对象，不替换正在播放的歌词）：

```bash
/usr/bin/python3 scripts/check-cinnamon.py
```

测试截图输出到 `build/qa/`。


## 项目目录

- `plugin/`：SaltPlayer Java 插件与随包安装器。
- `cinnamon/`：Cinnamon 面板小程序源码。
- `scripts/`：构建、测试及手动安装工具。
- `tests/`：Java、JavaScript、Python 测试和绘制验证脚本。
- `docs/`：开发、发布说明与版本记录。
- `dist/`：本地构建安装包，不纳入 Git；历史版本在 `dist/archive/`。
- `build/`：编译输出和绘制验证图片，不纳入 Git。
- `.cache/`：本机 JDK、依赖与下载缓存，不纳入 Git。

项目版本由根目录 `VERSION` 管理，面板 metadata 的版本需同步。首次构建下载 API、PF4J、Kotlin 标准库作为编译依赖，不会将这些宿主依赖打包。

## Steam Runtime 与 Python 环境

1.2.2 起安装器使用 Python 隔离模式，清除继承的 Python 和动态库路径。Steam pressure-vessel 容器内通过 `steam-runtime-launch-client --alongside-steam` 调用宿主 Python，并将待安装资源解压到共享的用户缓存目录，避免容器私有 `/tmp` 不可见。原生启动不经过宿主启动器。

没有 Python GI 或 Cinnamon 本地设置架构时，以 Python 标准库调用 `gdbus`，通过当前 Cinnamon 会话读写面板设置及重新加载。不会安装系统软件、修改 Steam 配置或要求管理员权限。Flatpak 等额外沙箱仍不保证宿主访问。

新增测试以 `python3 -I -S` 确保 GI 不可见，使用隔离的模拟桌面完成完整安装生命周期；也验证环境污染过滤与 Steam 启动参数。已实际通过本机 Steam 宿主启动接口运行安装器。
