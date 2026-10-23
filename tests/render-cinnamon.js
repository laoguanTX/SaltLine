(() => {
    const a = imports.ui.appletManager.getRunningInstancesForUuid('saltbar@local')[0];
    const Cairo = imports.cairo;
    const GLib = imports.gi.GLib;
    const P = imports.gi.GdkPixbuf;
    const path = GLib.build_filenamev([GLib.get_user_cache_dir(),'saltplayer-barlyrics','cover-'+'0'.repeat(64)+'.png']);
    const pixbuf = P.Pixbuf.new(P.Colorspace.RGB,true,8,128,128);
    pixbuf.fill(0xe83860ff);
    pixbuf.savev(path,'png',[],[]);
    const test = Object.create(a);
    test._dead = false; test._coverName = null; test._coverRequest = 0;
    test.showTranslation = true; test.showCover = true; test.useCoverColors = true;
    test._state = {position:1250,playing:false,sampledAt:Date.now(),line:{start:0,end:2000,text:'圆角封面 · 逐字主题色',translation:'第二行翻译\n另一段翻译',cells:[{start:0,end:2000,text:'圆角封面 · 逐字主题色'}]}};
    test._receivedAt = GLib.get_monotonic_time()/1000; test._receivedWall=Date.now();
    test._area = {queue_repaint: () => {
        const frames=[];
        for(const height of [36,44]) {
            const surface = new Cairo.ImageSurface(Cairo.Format.ARGB32,420,height);
            const cr = new Cairo.Context(surface);
            cr.setSourceRGB(.10,.11,.15);cr.paint();
            test._area.get_context=()=>cr;
            test._area.get_surface_size=()=>[420,height];
            test._paint();
            surface.writeToPNG('@OUTPUT@/frame-'+height+'.png');
            frames.push(test._lastFrame);
        }
        global._saltbarQA=frames;
        imports.gi.Gio.File.new_for_path(path).delete(null);
    }};
    test._loadCover('cover-'+'0'.repeat(64)+'.png');
    return 'async artwork and rendering test started';
})()
