# 发布安装包

## GitHub Releases

1. 在项目根目录执行 `python3 scripts/test.py`，确认测试通过。
2. 确认根目录 `VERSION` 和 `cinnamon/saltbar@local/metadata.json` 版本一致。
3. 执行 `python3 scripts/build.py` 生成最新安装包。
4. 将 `dist/saltline-<版本>.spmod` 与可选的 `dist/saltline-cinnamon-<版本>.zip` 上传至对应版本的 GitHub Release。源码由 GitHub 自动提供下载。

源码提交不包含 JDK、缓存、编译文件、安装包和本机配置。旧版本安装包仅在本地 `dist/archive/` 留存。

## Steam 创意工坊

Steam 库中右键 SaltPlayer → 属性 → 通用，在启动选项添加：

```text
--workshop-publisher
```

从 Steam 完全重启播放器，在 **创意工坊 → 创意工坊创作中心 → 发布新 Mod** 中上传 `.spmod`，并选择小于 1 MB 的 PNG、JPG 或 GIF 封面。发布后检查 Steam 条目的协议和可见范围，新条目默认私有。更新时选中已有条目，替换包并填写更新说明。

1.2.0 及以后的 `.spmod` 已内置 Cinnamon 小程序和安装器，无需用户额外下载面板 ZIP。介绍中应写明 Linux Cinnamon 环境、首次需要启用模组，以及内嵌封面所需的读取曲库权限。

具体操作以 [SaltPlayer 官方发布指南](https://saltplayer.com/workshop/publishing) 为准。
