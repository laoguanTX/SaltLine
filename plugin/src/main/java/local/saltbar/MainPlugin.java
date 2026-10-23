package local.saltbar;

import com.xuncorp.spw.workshop.api.PluginContext;
import com.xuncorp.spw.workshop.api.SpwPlugin;
import com.xuncorp.spw.workshop.api.WorkshopApi;

public final class MainPlugin extends SpwPlugin {
    private final CinnamonIntegration cinnamon = new CinnamonIntegration();
    public MainPlugin(PluginContext context) { super(context); }
    @Override public void start() {
        cinnamon.enable();
        Bridge.start();
        CoverArt.start();
        CoverArt.request(null);
        Bridge.lines(WorkshopApi.playback().getLyricsLines());
    }
    @Override public void stop() { cinnamon.disable(); CoverArt.stop(); Bridge.stop(); }
    @Override public void delete() { cinnamon.remove(); CoverArt.stop(); Bridge.stop(); }
}
