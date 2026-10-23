'use strict';
// Quantized dominant-color voting avoids averaging contrasting artwork into gray.
function dominant(pixels, width, height, rowstride, channels) {
    const bins = new Map();
    for (let y = 0; y < height; y += 2) for (let x = 0; x < width; x += 2) {
        const i = y * rowstride + x * channels;
        if (channels === 4 && pixels[i + 3] < 128) continue;
        const r = pixels[i] / 255, g = pixels[i + 1] / 255, b = pixels[i + 2] / 255;
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        if (max < 0.08 || min > 0.95) continue;
        const saturation = max - min;
        const key = (pixels[i] >> 5) * 64 + (pixels[i + 1] >> 5) * 8 + (pixels[i + 2] >> 5);
        const bin = bins.get(key) || {weight:0, count:0, r:0, g:0, b:0};
        bin.weight += 0.2 + saturation * 2;
        bin.count++; bin.r += r; bin.g += g; bin.b += b;
        bins.set(key, bin);
    }
    let best = null;
    for (const bin of bins.values()) if (!best || bin.weight > best.weight) best = bin;
    return best ? [best.r / best.count, best.g / best.count, best.b / best.count] : null;
}
function palette(rgb, foreground) {
    if (!rgb) return null;
    const max = Math.max(...rgb), min = Math.min(...rgb), d = max - min;
    let h = 0;
    if (d > 0) {
        const index = rgb.indexOf(max);
        h = index === 0 ? ((rgb[1] - rgb[2]) / d + 6) % 6 : index === 1 ? (rgb[2] - rgb[0]) / d + 2 : (rgb[0] - rgb[1]) / d + 4;
        h /= 6;
    }
    const darkPanel = foreground[0] * .2126 + foreground[1] * .7152 + foreground[2] * .0722 > .5;
    const light = darkPanel ? .74 : .32;
    const saturation = d < .05 ? .12 : .68;
    const c = (1 - Math.abs(2 * light - 1)) * saturation;
    const x = c * (1 - Math.abs((h * 6) % 2 - 1)), m = light - c / 2;
    const sectors = [[c,x,0],[x,c,0],[0,c,x],[0,x,c],[x,0,c],[c,0,x]];
    const highlight = sectors[Math.min(5, Math.floor(h * 6))].map(v => v + m);
    const toHex = values => '#' + values.map(v => Math.round(Math.max(0,Math.min(1,v))*255).toString(16).padStart(2,'0')).join('');
    return {
        highlight: toHex(highlight),
        text: toHex(foreground.map((v,i) => v * .78 + highlight[i] * .22))
    };
}
function translationRow(text) {
    // Several translations/romanizations are still rendered as a single second row.
    return String(text || '').split(/[\r\n\u2028\u2029]+/).map(s => s.trim()).filter(Boolean).join(' ');
}
module.exports = {dominant, palette, translationRow};
