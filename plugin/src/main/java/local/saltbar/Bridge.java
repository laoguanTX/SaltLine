package local.saltbar;

import com.xuncorp.spw.workshop.api.PlaybackExtensionPoint.LyricsLine;
import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import java.util.concurrent.*;

/** One local atomic snapshot; callbacks never perform disk I/O. Times are milliseconds. */
public final class Bridge {
    private static ScheduledExecutorService worker;
    private static List<LyricsLine> timeline = List.of();
    private static LyricsLine current;
    private static String title = "", artist = "", coverFile;
    private static long revision;
    private static long position, anchor;
    private static boolean playing, playbackStateKnown, positionSeen;
    private static Path state;
    private static boolean reportedError;

    static synchronized void start() {
        if (worker != null) return;
        state = RuntimePaths.cacheDirectory().resolve("state.json");
        revision++; coverFile = null;
        timeline = List.of(); current = null; title = artist = "";
        position = 0; anchor = System.nanoTime(); playing = false; reportedError = false;
        playbackStateKnown = false; positionSeen = false;
        worker = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "SaltLine-bridge"); t.setDaemon(true); return t;
        });
        worker.scheduleWithFixedDelay(Bridge::publish, 0, 100, TimeUnit.MILLISECONDS);
    }
    static synchronized void stop() {
        if (worker == null) return;
        worker.shutdownNow(); worker = null;
        // publish holds this same monitor, so no worker can rewrite after deletion.
        try { Files.deleteIfExists(state); Files.deleteIfExists(state.resolveSibling("state.tmp")); }
        catch (IOException e) { System.err.println("SaltLine: " + e); }
        clear();
    }
    static synchronized long revision() { return revision; }
    static synchronized boolean isCurrent(long token) { return worker != null && revision == token; }
    static synchronized Path cacheDirectory() { return state.getParent(); }
    static synchronized void cover(long token, String name) {
        if (isCurrent(token)) coverFile = name;
    }
    static synchronized void position(long value) {
        position = Math.max(0, value); anchor = System.nanoTime();
    }
    static synchronized void updatedPosition(long value) {
        // API has no playback-state getter. Until the first state callback, infer
        // startup playback from consecutive position samples (never from seeks).
        if (!playbackStateKnown && positionSeen) playing = value > position;
        positionSeen = true;
        position(value);
    }
    static synchronized void playing(boolean value) {
        playbackStateKnown = true;
        position = positionNow(); anchor = System.nanoTime(); playing = value;
    }
    static synchronized void track(String name, String singer) {
        revision++; coverFile = null;
        title = name; artist = singer; timeline = List.of(); current = null; positionSeen = false; position(0);
    }
    static synchronized void clear() {
        revision++; coverFile = null;
        timeline = List.of(); current = null; title = artist = ""; playing = false; position(0);
    }
    static synchronized void lines(List<LyricsLine> lines) {
        timeline = lines.stream().sorted(Comparator.comparingLong(LyricsLine::getStartTime)).toList();
        current = null;
    }
    static synchronized void line(LyricsLine line) {
        // A null active-line callback can just mean a gap between sung words.
        // Track/timeline resets and Idle/Ended explicitly clear retained lyrics.
        if (line != null) current = line;
    }
    private static long positionNow() {
        return position + (playing ? Math.min(2000, Math.max(0, (System.nanoTime() - anchor) / 1_000_000)) : 0);
    }
    static LyricsLine select(List<LyricsLine> lines, long time) {
        int lo = 0, hi = lines.size();
        while (lo < hi) {
            int mid = (lo + hi) >>> 1;
            if (lines.get(mid).getStartTime() <= time) lo = mid + 1; else hi = mid;
        }
        if (lo == 0) return null;
        // endTime marks the end of singing, not the end of the line's display.
        // Keep the latest started line until its successor or a playback reset.
        return lines.get(lo - 1);
    }
    private static synchronized void publish() {
        if (worker == null) return;
        long now = positionNow();
        LyricsLine line = timeline.isEmpty() ? current : select(timeline, now);
        if (line != null && now < line.getStartTime()) line = null;
        String json = snapshot(now, System.currentTimeMillis(), playing, title, artist, line, coverFile);
        try {
            Files.createDirectories(state.getParent());
            Files.setPosixFilePermissions(state.getParent(), PosixFilePermissions.fromString("rwx------"));
            Path temp = state.resolveSibling("state.tmp");
            Files.writeString(temp, json);
            Files.setPosixFilePermissions(temp, PosixFilePermissions.fromString("rw-------"));
            Files.move(temp, state, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            reportedError = false;
        } catch (IOException | UnsupportedOperationException e) {
            if (!reportedError) System.err.println("SaltLine cannot write state: " + e);
            reportedError = true;
        }
    }
    static String snapshot(long pos, long sampled, boolean playing, String title, String artist, LyricsLine line) {
        return snapshot(pos, sampled, playing, title, artist, line, null);
    }
    static String snapshot(long pos, long sampled, boolean playing, String title, String artist, LyricsLine line, String cover) {
        StringBuilder s = new StringBuilder("{\"version\":1,\"sampledAt\":").append(sampled)
            .append(",\"position\":").append(pos).append(",\"playing\":").append(playing)
            .append(",\"cover\":").append(quote(cover))
            .append(",\"title\":").append(quote(title)).append(",\"artist\":").append(quote(artist)).append(",\"line\":");
        if (line == null) return s.append("null}").toString();
        s.append("{\"start\":").append(line.getStartTime()).append(",\"end\":").append(line.getEndTime())
            .append(",\"text\":").append(quote(line.getPureMainText()))
            .append(",\"translation\":").append(quote(line.getPureSubText())).append(",\"cells\":[");
        boolean first = true;
        for (LyricsLine.Cell cell : line.getLyricsCells()) {
            if (!first) s.append(','); first = false;
            s.append("{\"start\":").append(cell.getStartTime()).append(",\"end\":").append(cell.getEndTime())
                .append(",\"text\":").append(quote(cell.getText())).append('}');
        }
        return s.append("]}}").toString();
    }
    static String quote(String text) {
        if (text == null) return "null";
        StringBuilder s = new StringBuilder("\"");
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '"' || c == '\\') s.append('\\').append(c);
            else if (c < 32) s.append(String.format("\\u%04x", (int)c));
            else s.append(c);
        }
        return s.append('"').toString();
    }
}
