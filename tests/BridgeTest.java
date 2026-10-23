package local.saltbar;
import com.xuncorp.spw.workshop.api.PlaybackExtensionPoint.LyricsLine;
import java.util.List;
import java.nio.file.*;
import java.awt.image.BufferedImage;
import java.io.*;
import javax.imageio.ImageIO;
public class BridgeTest {
    public static void main(String[] args) {
        LyricsLine a = new LyricsLine(1000, 2000, List.of(new LyricsLine.Cell(1000,1500,"你"), new LyricsLine.Cell(1500,2000,"好😀")), "你好😀", "hello\n\"world\"");
        LyricsLine b = new LyricsLine(3000, 4000, List.of(), "next", null);
        List<LyricsLine> lines = List.of(a,b);
        assert Bridge.select(lines, 999) == null;
        assert Bridge.select(lines, 1000) == a;
        assert Bridge.select(lines, 1999) == a;
        assert Bridge.select(lines, 2000) == a;
        assert Bridge.select(lines, 2999) == a;
        assert Bridge.select(lines, 3000) == b;
        assert Bridge.select(lines, 4000) == b;
        assert Bridge.select(lines, 1500) == a; // backward seek
        assert Bridge.select(lines, 2500) == a; // seek into the gap
        assert Bridge.select(lines, 0) == null; // seek back before the first line
        assert Bridge.select(List.of(), 2500) == null;
        System.out.println(Bridge.snapshot(1250, 10000, true, "title\t\\", "artist", a));
        try {
            BufferedImage original = new BufferedImage(400, 200, BufferedImage.TYPE_INT_ARGB);
            for (int y=0;y<200;y++) for (int x=0;x<400;x++) original.setRGB(x,y,0xffe02040);
            var bytes = new ByteArrayOutputStream(); ImageIO.write(original, "png", bytes);
            byte[] thumbnail = CoverArt.thumbnail(bytes.toByteArray());
            BufferedImage decoded = ImageIO.read(new ByteArrayInputStream(thumbnail));
            assert decoded.getWidth() == 128 && decoded.getHeight() == 128;
            assert decoded.getRGB(64,64) == 0xffe02040;
            assert CoverArt.thumbnail(new byte[]{1,2,3}) == null;
            assert CoverArt.thumbnail(new byte[0]) == null;
        } catch (IOException e) { throw new RuntimeException(e); }
        Bridge.start(); Bridge.lines(lines);
        long firstRevision = Bridge.revision();
        Bridge.cover(firstRevision, "cover-test.png");
        await("\"cover\":\"cover-test.png\"");
        Bridge.updatedPosition(1000); Bridge.updatedPosition(1250);
        await("\"playing\":true");
        Bridge.playing(false); Bridge.position(1100);
        await("\"position\":1100,\"playing\":false");
        Bridge.position(2500); Bridge.line(null);
        await("\"position\":2500,\"playing\":false");
        await("\"text\":\"你好😀\"");
        Bridge.position(3000);
        await("\"text\":\"next\"");
        Bridge.position(2500);
        await("\"text\":\"你好😀\"");
        Bridge.lines(List.of()); Bridge.line(null);
        await("\"line\":null");
        Bridge.line(a); Bridge.position(2500); Bridge.line(null);
        await("\"text\":\"你好😀\""); // no-timeline callback fallback also retains the line
        Bridge.track("new track", "artist");
        Bridge.cover(firstRevision, "cover-stale.png");
        await("\"cover\":null");
        await("\"line\":null");
        Bridge.lines(lines); Bridge.position(2500);
        await("\"text\":\"你好😀\"");
        Bridge.clear();
        await("\"line\":null");
        Bridge.stop();
    }
    private static void await(String expected) {
        Path path = Path.of(System.getenv("XDG_CACHE_HOME"), "saltplayer-barlyrics/state.json");
        long deadline = System.nanoTime() + 2_000_000_000L;
        while (System.nanoTime() < deadline) {
            try {
                if (Files.exists(path) && Files.readString(path).contains(expected)) return;
                Thread.sleep(20);
            } catch (Exception e) { throw new RuntimeException(e); }
        }
        throw new AssertionError("snapshot did not contain " + expected);
    }
}
