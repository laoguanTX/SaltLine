package local.saltbar;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

public final class DesktopLauncherTest {
    public static void main(String[] args) throws Exception {
        var nativePlan = DesktopLauncher.detect(Map.of("PATH","/other/bin"), p -> p.toString().equals("/usr/bin/python3"),false,false);
        assert nativePlan.mode().equals("native");
        assert nativePlan.prefix().equals(List.of("/usr/bin/python3"));
        var custom = DesktopLauncher.detect(Map.of("PATH","/custom profile/bin:/bin"), p -> p.toString().equals("/custom profile/bin/python3"),false,false);
        assert custom.prefix().get(0).equals("/custom profile/bin/python3");
        var steam = DesktopLauncher.detect(Map.of(), p -> p.toString().equals("/usr/lib/pressure-vessel/from-host/bin/steam-runtime-launch-client"),true,false);
        var command = steam.command(Path.of("/home/another user/音乐 cache/installer-test"),"enable","token-with-spaces");
        assert steam.mode().equals("steam-host");
        assert command.contains("--alongside-steam");
        assert command.contains("--unset-env=PYTHONHOME");
        assert command.contains("/usr/bin/env") && command.contains("python3");
        assert command.contains("/home/another user/音乐 cache/installer-test/installer.py");
        assert command.contains("--state-file") && command.contains("token-with-spaces");
        assert !command.contains("--clear-env") && !command.contains("--pass-env=HOME") && !command.contains("-c");
        for (var pair : List.of(new boolean[]{true,false},new boolean[]{false,true},new boolean[]{false,false})) {
            try {
                DesktopLauncher.detect(Map.of(),p -> false,pair[0],pair[1]);
                throw new AssertionError("missing tools/environment must fail with a useful error");
            } catch (IOException expected) { assert !expected.getMessage().isBlank(); }
        }
        var environment = new HashMap<>(Map.of("PYTHONHOME","polluted","LD_LIBRARY_PATH","polluted","DBUS_SESSION_BUS_ADDRESS","session","XDG_CACHE_HOME","/user/cache"));
        DesktopLauncher.sanitize(environment);
        assert !environment.containsKey("PYTHONHOME") && !environment.containsKey("LD_LIBRARY_PATH");
        assert environment.get("DBUS_SESSION_BUS_ADDRESS").equals("session");
        assert RuntimePaths.cacheDirectory("relative/path","/home/other user").equals(Path.of("/home/other user/.cache/saltplayer-barlyrics"));
        assert RuntimePaths.cacheDirectory("/custom/缓存","/home/other user").equals(Path.of("/custom/缓存/saltplayer-barlyrics"));
        System.out.println("desktop launcher: native/custom PATH, Steam host, missing tools, Flatpak and shared cache passed");
    }
}
