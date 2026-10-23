package local.saltbar;

import java.nio.file.Path;

/** One source of truth for the player-side bridge and installer staging paths. */
final class RuntimePaths {
    static Path cacheDirectory() {
        return cacheDirectory(System.getenv("XDG_CACHE_HOME"), System.getProperty("user.home"));
    }
    static Path cacheDirectory(String cache, String home) {
        Path root = cache != null && !cache.isBlank() && Path.of(cache).isAbsolute()
            ? Path.of(cache) : Path.of(home, ".cache");
        return root.resolve("saltplayer-barlyrics");
    }
}
