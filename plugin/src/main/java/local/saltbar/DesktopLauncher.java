package local.saltbar;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.function.Predicate;

/** Discover desktop tools without assuming a particular user's PATH or CPU architecture. */
final class DesktopLauncher {
    static final Set<String> SANITIZED = Set.of("LD_LIBRARY_PATH", "LD_PRELOAD", "GI_TYPELIB_PATH",
        "GIO_EXTRA_MODULES", "GIO_MODULE_DIR", "GSETTINGS_SCHEMA_DIR", "GTK_PATH", "GTK_MODULES");
    record Plan(String mode, List<String> prefix) {
        List<String> command(Path directory, String action, String token) {
            List<String> command = new ArrayList<>(prefix);
            command.addAll(List.of("-I", directory.resolve("installer.py").toString(), action,
                "--source", directory.toString(), "--token", token,
                "--state-file", RuntimePaths.cacheDirectory().resolve("state.json").toString()));
            return command;
        }
    }
    static Plan detect() throws IOException {
        return detect(System.getenv(), Files::isExecutable, Files.isDirectory(Path.of("/run/host/usr")),
            Files.isRegularFile(Path.of("/.flatpak-info")) || System.getenv("FLATPAK_ID") != null);
    }
    static Plan detect(Map<String,String> environment, Predicate<Path> executable, boolean container, boolean flatpak) throws IOException {
        if (flatpak) throw new IOException("暂不支持 Flatpak 内的自动面板安装，请使用发行版原生 Steam 或 SaltPlayer。");
        if (container) {
            String launcher = find(environment, executable, "steam-runtime-launch-client", List.of(
                "/usr/bin/steam-runtime-launch-client", "/usr/lib/pressure-vessel/from-host/bin/steam-runtime-launch-client",
                "/run/pressure-vessel/pv-from-host/bin/steam-runtime-launch-client"));
            if (launcher == null) throw new IOException("未找到 Steam 宿主启动接口，请更新并重新启动原生 Steam。");
            List<String> command = new ArrayList<>(List.of(launcher, "--alongside-steam"));
            // Keep the host service's PATH, HOME and XDG values, not the container's.
            for (String name : SANITIZED.stream().sorted().toList()) command.add("--unset-env="+name);
            for (String name : List.of("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE")) command.add("--unset-env="+name);
            command.addAll(List.of("--", "/usr/bin/env", "python3"));
            return new Plan("steam-host", List.copyOf(command));
        }
        String python = find(environment, executable, "python3", List.of("/usr/bin/python3", "/usr/local/bin/python3"));
        if (python == null) throw new IOException("未找到系统 Python 3，请安装 Python 3.8 或更新版本后重新启用模组。");
        return new Plan("native", List.of(python));
    }
    private static String find(Map<String,String> environment, Predicate<Path> executable, String name, List<String> defaults) {
        List<String> candidates = new ArrayList<>(defaults);
        for (String directory : environment.getOrDefault("PATH", "").split(":")) {
            if (!directory.isEmpty() && Path.of(directory).isAbsolute()) candidates.add(Path.of(directory,name).toString());
        }
        return candidates.stream().distinct().filter(p -> executable.test(Path.of(p))).findFirst().orElse(null);
    }
    static void sanitize(Map<String,String> environment) {
        environment.keySet().removeIf(name -> name.startsWith("PYTHON") || SANITIZED.contains(name));
    }
}
