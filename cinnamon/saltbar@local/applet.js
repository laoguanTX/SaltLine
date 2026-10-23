'use strict';
const Applet = imports.ui.applet;
const Settings = imports.ui.settings;
const St = imports.gi.St;
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;
const Clutter = imports.gi.Clutter;
const Pango = imports.gi.Pango;
const PangoCairo = imports.gi.PangoCairo;
const Mainloop = imports.mainloop;
const ByteArray = imports.byteArray;
const T = require('./timeline');
const Connection = require('./connection');
const Theme = require('./theme');
const GdkPixbuf = imports.gi.GdkPixbuf;
const Gdk = imports.gi.Gdk;

class SaltLineApplet extends Applet.Applet {
    constructor(metadata, orientation, panelHeight, instanceId) {
        super(orientation, panelHeight, instanceId);
        this.setAllowedLayout(Applet.AllowedLayout.HORIZONTAL);
        this._dead = false;
        this._reading = false;
        this._state = null;
        this._lastRead = 0;
        this._receivedAt = 0;
        this._coverName = null;
        this._cover = null;
        this._dominant = null;
        this._coverRequest = 0;
        this._cancellable = new Gio.Cancellable();
        let config = null;
        try {
            const file = Gio.File.new_for_path(GLib.build_filenamev([metadata.path, 'bridge.json']));
            const [ok, bytes] = file.load_contents(null);
            if (ok && bytes.length < 16384) config = JSON.parse(ByteArray.toString(bytes));
        } catch (_) { /* Older/manual installations use the desktop cache directory. */ }
        const fallback = GLib.build_filenamev([GLib.get_user_cache_dir(), 'saltplayer-barlyrics', 'state.json']);
        this._file = Gio.File.new_for_path(Connection.statePath(config, fallback));
        this._area = new St.DrawingArea({reactive: false, y_expand: true});
        this.actor.add_child(this._area);
        this._area.connect('repaint', () => this._paint());
        this.settings = new Settings.AppletSettings(this, metadata.uuid, instanceId);
        for (const key of ['width', 'fontSize', 'fontFamily', 'highlightColor', 'textColor', 'showTranslation', 'hideIdle', 'offset', 'showCover', 'useCoverColors'])
            this.settings.bind(key, key, () => this._resize());
        this._resize();
        this.set_applet_tooltip('SaltLine：等待 SaltPlayer 创意工坊插件\n右键 → 配置，可调整宽度、字号和时间补偿');
        this._timer = Mainloop.timeout_add(33, () => {
            if (this._dead) return false;
            const now = GLib.get_monotonic_time() / 1000;
            if (now - this._lastRead >= 100) { this._lastRead = now; this._read(); }
            if (this._state && Date.now() - this._state.sampledAt > 3000) this._accept(null);
            if (this._state && this._state.playing) this._area.queue_repaint();
            return true;
        });
        this._saltlineReady = true;
        this._read();
    }
    _resize() {
        if (!this._area) return;
        this._area.set_width((this.hideIdle && !this._state ? 24 : this.width) * global.ui_scale);
        this._area.queue_repaint();
    }
    _accept(state) {
        this._state = state;
        this._loadCover(state && state.cover);
        this._receivedWall = Date.now();
        this._receivedAt = GLib.get_monotonic_time() / 1000;
        this._resize();
        let tooltip = 'SaltLine：等待 SaltPlayer 创意工坊插件';
        if (state) {
            tooltip = [state.title, state.artist].filter(Boolean).join(' — ') || 'SaltPlayer';
            tooltip += state.playing ? '\n播放中' : '\n已暂停';
            if (state.line) tooltip += '\n' + state.line.text + (state.line.translation ? '\n' + state.line.translation : '');
        }
        this.set_applet_tooltip(tooltip + '\n右键 → 配置');
    }
    _loadCover(name) {
        name = typeof name === 'string' && /^cover-[0-9a-f]{64}\.png$/.test(name) ? name : null;
        if (name === this._coverName) return;
        this._coverName = name;
        const request = ++this._coverRequest;
        this._cover = null; this._dominant = null;
        if (!name) return;
        const file = this._file.get_parent().get_child(name);
        file.read_async(GLib.PRIORITY_DEFAULT, this._cancellable, (source, result) => {
            let stream;
            try { stream = source.read_finish(result); }
            catch (_) { return; }
            GdkPixbuf.Pixbuf.new_from_stream_at_scale_async(stream, 128, 128, true, this._cancellable, (_object, loaded) => {
                try {
                    const pixbuf = GdkPixbuf.Pixbuf.new_from_stream_finish(loaded);
                    if (this._dead || request !== this._coverRequest) return;
                    this._cover = pixbuf;
                    this._dominant = Theme.dominant(pixbuf.get_pixels(), pixbuf.width, pixbuf.height, pixbuf.rowstride, pixbuf.n_channels);
                    this._area.queue_repaint();
                } catch (_) { /* Keep the placeholder for unreadable artwork. */ }
                finally { stream.close_async(GLib.PRIORITY_DEFAULT, null, null); }
            });
        });
    }
    _roundedRect(cr, x, y, size, radius) {
        cr.newPath();
        cr.arc(x + size - radius, y + radius, radius, -Math.PI / 2, 0);
        cr.arc(x + size - radius, y + size - radius, radius, 0, Math.PI / 2);
        cr.arc(x + radius, y + size - radius, radius, Math.PI / 2, Math.PI);
        cr.arc(x + radius, y + radius, radius, Math.PI, Math.PI * 1.5);
        cr.closePath();
    }
    _paintCover(cr, x, y, size, color) {
        cr.save();
        this._roundedRect(cr, x, y, size, Math.max(3, size * .2));
        cr.clip();
        if (this._cover) {
            cr.translate(x, y);
            cr.scale(size / this._cover.width, size / this._cover.height);
            Gdk.cairo_set_source_pixbuf(cr, this._cover, 0, 0);
            cr.paint();
        } else {
            this._color(cr, color, '#8bd5ca'); cr.paintWithAlpha(.15);
            const icon = this._layout(cr, '♪', size * .6);
            const [w,h] = icon.get_pixel_size();
            this._draw(cr, icon, x + (size-w)/2, y + (size-h)/2, color);
        }
        cr.restore();
    }
    _read() {
        if (this._reading || this._dead) return;
        this._reading = true;
        this._file.load_contents_async(this._cancellable, (file, result) => {
            this._reading = false;
            if (this._dead) return;
            try {
                const [ok, bytes] = file.load_contents_finish(result);
                if (!ok || bytes.length > 1024 * 1024) throw new Error('Invalid snapshot size');
                const state = JSON.parse(ByteArray.toString(bytes));
                if (state.version !== 1 || !Number.isFinite(state.position) || !Number.isFinite(state.sampledAt) ||
                    Math.abs(Date.now() - state.sampledAt) > 3000) throw new Error('Invalid or stale snapshot');
                this._accept(state);
            } catch (_) { if (this._state) this._accept(null); }
        });
    }
    _layout(cr, text, size) {
        const layout = PangoCairo.create_layout(cr);
        const font = Pango.FontDescription.from_string(this.fontFamily || 'Sans');
        font.set_absolute_size(size * Pango.SCALE);
        layout.set_font_description(font);
        layout.set_text(text, -1);
        layout.set_single_paragraph_mode(true);
        return layout;
    }
    _color(cr, value, fallback) {
        const [ok, color] = Clutter.Color.from_string(value);
        Clutter.cairo_set_source_color(cr, ok ? color : Clutter.Color.from_string(fallback)[1]);
    }
    _draw(cr, layout, x, y, color) {
        cr.moveTo(x, y); this._color(cr, color, '#cdd6f4'); PangoCairo.show_layout(cr, layout);
    }
    _paint() {
        const cr = this._area.get_context();
        try {
            const [width, height] = this._area.get_surface_size();
            const scale = global.ui_scale;
            const now = GLib.get_monotonic_time() / 1000;
            const state = this._state;
            const pos = state ? T.positionAt(state, this._receivedWall, this._receivedAt, now, this.offset) : 0;
            const line = T.visibleLine(state, pos);
            const text = line ? T.textFor(line) : state ? (state.title || 'SaltPlayer · 暂无歌词') : this.hideIdle ? '♪' : '♪ SaltPlayer · 等待连接';
            const translation = line && this.showTranslation ? Theme.translationRow(line.translation) : '';
            const foreground = this.actor.get_theme_node().get_foreground_color();
            const colors = this.useCoverColors ? Theme.palette(this._dominant, [foreground.red/255, foreground.green/255, foreground.blue/255]) : null;
            const highlight = colors ? colors.highlight : this.highlightColor;
            const normal = colors ? colors.text : this.textColor;
            const margin = 6 * scale;
            const coverSize = Math.max(1, Math.min(height - 4 * scale, 48 * scale));
            const coverWidth = this.showCover && !(this.hideIdle && !state) ? coverSize + margin : 0;
            const left = margin + coverWidth;
            const available = Math.max(1, width - left - margin);
            if (coverWidth) this._paintCover(cr, margin, (height-coverSize)/2, coverSize, highlight);
            let mainSize = this.fontSize * scale;
            let subSize = Math.max(9, this.fontSize * .72) * scale;
            let layout = this._layout(cr, text, mainSize);
            let sub = translation ? this._layout(cr, translation, subSize) : null;
            let [tw, th] = layout.get_pixel_size();
            let sh = sub ? sub.get_pixel_size()[1] : 0;
            const gap = translation ? scale : 0;
            const fit = Math.min(1, Math.max(1, height - 4 * scale - gap) / Math.max(1, th + sh));
            if (fit < 1) {
                layout = this._layout(cr, text, mainSize * fit);
                sub = translation ? this._layout(cr, translation, subSize * fit) : null;
                [tw, th] = layout.get_pixel_size();
                sh = sub ? sub.get_pixel_size()[1] : 0;
            }
            const y = Math.max(0, (height - th - sh - gap) / 2);
            // Pango measures full shaped text so kerning, CJK and fallback fonts stay aligned.
            const cells = line && line.cells && line.cells.map(c => c.text).join('') === text ? line.cells : [];
            const clips = [];
            let byteIndex = 0, focus = 0;
            for (const cell of cells) {
                const start = layout.index_to_pos(byteIndex).x / Pango.SCALE;
                byteIndex += T.utf8Length(cell.text);
                const end = layout.index_to_pos(byteIndex).x / Pango.SCALE;
                const amount = T.fraction(cell, pos);
                if (amount > 0) clips.push([Math.min(start, start + (end - start) * amount), Math.abs(end - start) * amount]);
                if (pos >= cell.start) focus = start + (end - start) * amount;
            }
            const shift = tw > available ? T.clamp(focus - available * .45, 0, tw - available) : 0;
            const x = left + (tw <= available ? (available - tw) / 2 : -shift);
            cr.save(); cr.rectangle(left, 0, available, height); cr.clip();
            this._draw(cr, layout, x, y, normal);
            if (line && cells.length === 0) this._draw(cr, layout, x, y, highlight);
            for (const [left, span] of clips) {
                cr.save(); cr.rectangle(x + left, y, span, th); cr.clip();
                this._draw(cr, layout, x, y, highlight); cr.restore();
            }
            if (sub) {
                sub.set_width(available * Pango.SCALE);
                sub.set_ellipsize(Pango.EllipsizeMode.END);
                sub.set_height(-1);
                const [sw] = sub.get_pixel_size();
                this._draw(cr, sub, left + Math.max(0, (available - sw) / 2), y + th + gap, normal);
            }
            this._lastFrame = {hasCover: !!this._cover, highlight, mainY:y, mainHeight:th, translationY:sub ? y+th+gap : null, translationHeight:sh, height};
            cr.restore();
        } catch (e) { global.logError('SaltLine repaint: ' + e); }
        finally { cr.$dispose(); }
    }
    on_applet_removed_from_panel() {
        this._dead = true;
        this._cancellable.cancel();
        if (this._timer) Mainloop.source_remove(this._timer);
        this.settings.finalize();
    }
}
function main(metadata, orientation, panelHeight, instanceId) {
    return new SaltLineApplet(metadata, orientation, panelHeight, instanceId);
}
