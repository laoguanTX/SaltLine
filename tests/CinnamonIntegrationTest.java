package local.saltbar;

import java.nio.file.*;

/** Launches the real embedded installer with isolated XDG dirs and in-memory settings. */
public final class CinnamonIntegrationTest {
    public static void main(String[] args) throws Exception {
        CinnamonIntegration integration = new CinnamonIntegration();
        Path state = Path.of(System.getenv("XDG_STATE_HOME"), "saltplayer-barlyrics/cinnamon-install.json");
        Path applet = Path.of(System.getenv("XDG_DATA_HOME"), "cinnamon/applets/saltbar@local");
        integration.enable();
        await(() -> Files.exists(state) && Files.exists(applet.resolve("theme.js")));
        assert Files.readString(applet.resolve("metadata.json")).contains(args[0]);
        assert Files.readString(state).contains("\"created\": true");
        integration.disable();
        await(() -> Files.readString(state).contains("\"entries\": []"));
        assert Files.exists(applet.resolve("applet.js"));
        integration.enable();
        await(() -> Files.readString(state).contains("panel1:left:"));
        integration.remove();
        await(() -> !Files.exists(applet));
        System.out.println("embedded installer: extraction, install, disable, re-enable and removal passed");
    }
    @FunctionalInterface private interface Check { boolean ready() throws Exception; }
    private static void await(Check check) throws Exception {
        long deadline = System.nanoTime()+8_000_000_000L;
        while (System.nanoTime()<deadline) {
            if (check.ready()) return;
            Thread.sleep(20);
        }
        throw new AssertionError("installer lifecycle timed out");
    }
}
