package local.saltbar;

import com.xuncorp.spw.workshop.api.PlaybackExtensionPoint.MediaItem;
import com.xuncorp.spw.workshop.api.PluginPermission;
import com.xuncorp.spw.workshop.api.WorkshopApi;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.concurrent.*;
import javax.imageio.ImageIO;

/** Decode artwork away from both playback callbacks and the Cinnamon process. */
final class CoverArt {
    private static ExecutorService worker;
    static synchronized void start() {
        worker = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "SaltBar-cover"); t.setDaemon(true); return t;
        });
    }
    static synchronized void stop() {
        if (worker != null) worker.shutdownNow();
        worker = null;
    }
    static synchronized void request(MediaItem requested) {
        if (worker == null) return;
        long revision = Bridge.revision();
        worker.execute(() -> {
            if (!Bridge.isCurrent(revision)) return;
            try {
                if (!WorkshopApi.manager().isPermissionGranted(PluginPermission.LIBRARY_READ)) return;
                MediaItem item = requested;
                if (item == null || item.getId().isBlank()) {
                    item = WorkshopApi.playback().getCurrentMediaItem();
                    if (item == null || requested != null && !item.getPath().equals(requested.getPath())) return;
                }
                if (!Bridge.isCurrent(revision) || item.getId().isBlank()) return;
                byte[] bytes = WorkshopApi.library().getCoverById(item.getId()).toCompletableFuture().get(10, TimeUnit.SECONDS);
                if (bytes == null || !Bridge.isCurrent(revision)) return;
                byte[] thumbnail = thumbnail(bytes);
                if (thumbnail == null || !Bridge.isCurrent(revision)) return;
                String name = "cover-" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(thumbnail)) + ".png";
                Path directory = Bridge.cacheDirectory();
                Files.createDirectories(directory);
                Files.setPosixFilePermissions(directory, PosixFilePermissions.fromString("rwx------"));
                Path temp = Files.createTempFile(directory, "cover-", ".tmp");
                try {
                    Files.write(temp, thumbnail);
                    Files.move(temp, directory.resolve(name), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
                } finally { Files.deleteIfExists(temp); }
                Bridge.cover(revision, name);
                // Keep a small cache, including recently used covers for in-flight readers.
                try (var paths = Files.list(directory)) {
                    var covers = paths.filter(p -> p.getFileName().toString().matches("cover-[0-9a-f]{64}\\.png"))
                        .sorted((a,b) -> Long.compare(b.toFile().lastModified(), a.toFile().lastModified())).toList();
                    for (int i = 4; i < covers.size(); i++)
                        if (!covers.get(i).getFileName().toString().equals(name)) Files.deleteIfExists(covers.get(i));
                }
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            catch (Exception e) {
                if (Bridge.isCurrent(revision)) System.err.println("SaltBar cover: " + e);
            }
        });
    }
    static byte[] thumbnail(byte[] bytes) throws IOException {
        if (bytes.length == 0 || bytes.length > 16 * 1024 * 1024) return null;
        BufferedImage image;
        try (var stream = ImageIO.createImageInputStream(new ByteArrayInputStream(bytes))) {
            var readers = ImageIO.getImageReaders(stream);
            if (!readers.hasNext()) return null;
            var reader = readers.next();
            try {
                reader.setInput(stream);
                int w = reader.getWidth(0), h = reader.getHeight(0);
                if (w < 1 || h < 1 || (long)w * h > 32_000_000) return null;
                var param = reader.getDefaultReadParam();
                int sampling = Math.max(1, Math.min(w, h) / 512);
                param.setSourceSubsampling(sampling, sampling, 0, 0);
                image = reader.read(0, param);
            } finally { reader.dispose(); }
        }
        BufferedImage result = new BufferedImage(128, 128, BufferedImage.TYPE_INT_ARGB);
        var graphics = result.createGraphics();
        try {
            graphics.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BICUBIC);
            int size = Math.min(image.getWidth(), image.getHeight());
            int x = (image.getWidth() - size) / 2, y = (image.getHeight() - size) / 2;
            graphics.drawImage(image, 0, 0, 128, 128, x, y, x + size, y + size, null);
        } finally { graphics.dispose(); }
        var out = new ByteArrayOutputStream();
        ImageIO.write(result, "png", out);
        return out.toByteArray();
    }
}
