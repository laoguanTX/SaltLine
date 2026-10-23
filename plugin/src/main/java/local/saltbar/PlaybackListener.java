package local.saltbar;

import com.xuncorp.spw.workshop.api.PlaybackExtensionPoint;
import java.util.List;

// Registered in META-INF/extensions.idx; no annotation processor required.
@org.pf4j.Extension
public final class PlaybackListener implements PlaybackExtensionPoint {
    @Override public void onPositionUpdated(long position) { Bridge.updatedPosition(position); }
    @Override public void onSeekTo(long position) { Bridge.position(position); }
    @Override public void onIsPlayingChanged(boolean playing) { Bridge.playing(playing); }
    @Override public void onStateChanged(State state) {
        if (state == State.Idle || state == State.Ended) Bridge.clear();
    }
    @Override public String onBeforeLoadLyrics(MediaItem item) {
        Bridge.track(item.getTitle(), item.getArtist());
        CoverArt.request(item);
        return null;
    }
    @Override public void onLyricsLinesUpdated(List<LyricsLine> lines) { Bridge.lines(lines); }
    @Override public void onLyricsLineUpdated(LyricsLine line) { Bridge.line(line); }
}
