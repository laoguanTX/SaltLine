package local.saltbar;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import com.xuncorp.spw.workshop.api.WorkshopApi;

/** Runs installation outside the UI thread, using embedded resources only. */
final class CinnamonIntegration {
    private final String token = UUID.randomUUID().toString();
    private final ThreadPoolExecutor worker = new ThreadPoolExecutor(0, 1, 1, TimeUnit.SECONDS,
        new LinkedBlockingQueue<>(), r -> {
            Thread thread = new Thread(r, "SaltBar-Cinnamon"); thread.setDaemon(true); return thread;
        });

    void enable() { submit("enable"); }
    void disable() { submit("disable"); }
    void remove() { submit("remove"); worker.shutdown(); }

    private void submit(String action) {
        if (worker.isShutdown()) return;
        if (!System.getProperty("os.name", "").toLowerCase(Locale.ROOT).contains("linux")) {
            if (action.equals("enable")) warn("SaltBar 自动面板安装仅支持 Linux Cinnamon 桌面。");
            return;
        }
        worker.execute(() -> {
            Path temporary = null;
            try {
                temporary = Files.createTempDirectory("saltbar-cinnamon-");
                extract("installer.py", temporary);
                if (action.equals("enable")) {
                    extract("assets.json", temporary);
                    String index;
                    try (InputStream input = resource("assets.list")) {
                        index = new String(input.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
                    }
                    for (String name : index.lines().toList()) {
                        if (name.isBlank()) continue;
                        if (name.contains("..") || name.startsWith("/") || name.contains("\\")) throw new IOException("Invalid asset path");
                        extract("applet/"+name, temporary);
                    }
                }
                Process process = new ProcessBuilder("/usr/bin/python3", temporary.resolve("installer.py").toString(), action,
                    "--source", temporary.toString(), "--token", token).redirectErrorStream(true)
                    .redirectOutput(temporary.resolve("result.txt").toFile()).start();
                if (!process.waitFor(15, TimeUnit.SECONDS)) {
                    process.destroyForcibly(); process.waitFor();
                    throw new IOException("Cinnamon 安装操作超时");
                }
                String output = Files.readString(temporary.resolve("result.txt"));
                if (process.exitValue() != 0) throw new IOException(output.strip());
                System.out.println("SaltBar Cinnamon: " + output.strip());
                output.lines().filter(line -> line.startsWith("WARNING: "))
                    .forEach(line -> warn(line.substring(9)));
            } catch (Exception error) {
                System.err.println("SaltBar Cinnamon " + action + ": " + error);
                warn("SaltBar 面板操作失败：" + error.getMessage());
                if (error instanceof InterruptedException) Thread.currentThread().interrupt();
            } finally {
                if (temporary != null) try (var paths = Files.walk(temporary)) {
                    for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(path);
                } catch (IOException error) { System.err.println("SaltBar temporary cleanup: "+error); }
            }
        });
    }
    private static InputStream resource(String name) throws IOException {
        InputStream input = CinnamonIntegration.class.getResourceAsStream("/saltbar-cinnamon/"+name);
        if (input == null) throw new FileNotFoundException("Missing bundled resource: "+name);
        return input;
    }
    private static void extract(String name, Path directory) throws IOException {
        Path path = directory.resolve(name);
        Files.createDirectories(path.getParent());
        try (InputStream input = resource(name)) { Files.copy(input, path); }
    }
    private static void warn(String message) {
        // Host UI calls must originate on the Swing dispatch thread.
        javax.swing.SwingUtilities.invokeLater(() -> {
            try { WorkshopApi.ui().toast(message, WorkshopApi.Ui.ToastType.Warning); }
            catch (Exception error) { System.err.println("SaltBar notification: "+error); }
        });
    }
}
