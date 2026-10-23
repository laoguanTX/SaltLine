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
            Thread thread = new Thread(r, "SaltLine-Cinnamon"); thread.setDaemon(true); return thread;
        });

    void enable() { submit("enable"); }
    void disable() { submit("disable"); }
    void remove() { submit("remove"); worker.shutdown(); }

    private void submit(String action) {
        if (worker.isShutdown()) return;
        if (!System.getProperty("os.name", "").toLowerCase(Locale.ROOT).contains("linux")) {
            if (action.equals("enable")) warn("SaltLine 自动面板安装仅支持 Linux Cinnamon 桌面。");
            return;
        }
        worker.execute(() -> {
            Path temporary = null;
            String mode = "detecting";
            try {
                Path directory = RuntimePaths.cacheDirectory();
                Files.createDirectories(directory);
                // /tmp can be private to Steam's container. HOME/cache is shared
                // with its host launcher, which must read these extracted assets.
                temporary = Files.createTempDirectory(directory, "installer-");
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
                DesktopLauncher.Plan plan = DesktopLauncher.detect();
                mode = plan.mode();
                Path result = temporary.resolve("result.txt");
                String output = "";
                int exit = 1;
                for (int attempt = 0; attempt < 3; attempt++) {
                    ProcessBuilder builder = new ProcessBuilder(plan.command(temporary, action, token))
                        .redirectErrorStream(true).redirectOutput(result.toFile());
                    DesktopLauncher.sanitize(builder.environment());
                    Process process = builder.start();
                    if (!process.waitFor(30, TimeUnit.SECONDS)) {
                        process.destroyForcibly(); process.waitFor();
                        throw new IOException("Cinnamon 安装超时，请登录桌面后重新启用模组。");
                    }
                    exit = process.exitValue();
                    output = Files.readString(result);
                    if (exit == 0 || !(output.contains("desktop-unavailable") || output.contains("installer-busy"))) break;
                    if (attempt < 2) Thread.sleep(750L*(attempt+1));
                }
                saveReport(action, plan.mode(), exit == 0, output);
                if (exit != 0) throw new IOException(output.strip());
                System.out.println("SaltLine Cinnamon: " + output.strip());
                output.lines().filter(line -> line.startsWith("WARNING: "))
                    .forEach(line -> warn(line.substring(9)));
            } catch (Exception error) {
                System.err.println("SaltLine Cinnamon " + action + ": " + error);
                saveReport(action, mode, false, error.toString());
                String message = error.getMessage();
                // Installer details remain in the log; display the human-readable first line.
                if (message != null) message = message.lines().findFirst().orElse(message).replace("SaltLine Cinnamon: ", "");
                warn("SaltLine：" + message + "\n诊断日志：" + RuntimePaths.cacheDirectory().resolve("integration.log"));
                if (error instanceof InterruptedException) Thread.currentThread().interrupt();
            } finally {
                if (temporary != null) try (var paths = Files.walk(temporary)) {
                    for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(path);
                } catch (IOException error) { System.err.println("SaltLine temporary cleanup: "+error); }
            }
        });
    }
    private static void saveReport(String action, String mode, boolean success, String message) {
        try {
            Path directory = RuntimePaths.cacheDirectory();
            Files.createDirectories(directory);
            if (message.length() > 32768) message = message.substring(message.length()-32768);
            Path temp = Files.createTempFile(directory, "report-", ".tmp");
            try {
                Files.writeString(temp, "SaltLine " + java.time.Instant.now() + "\naction="+action+" mode="+mode+" success="+success+"\n"+message);
                Files.move(temp, directory.resolve("integration.log"), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } finally { Files.deleteIfExists(temp); }
        } catch (IOException error) { System.err.println("SaltLine diagnostic report: "+error); }
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
            catch (Exception error) { System.err.println("SaltLine notification: "+error); }
        });
    }
}
