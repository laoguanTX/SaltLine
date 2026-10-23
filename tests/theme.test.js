'use strict';
const assert = require('node:assert/strict');
const T = require('../cinnamon/saltbar@local/theme');
// Row stride includes padding; transparent blue pixels must not outweigh opaque red.
const pixels = new Uint8Array(24 * 4);
for (let y=0;y<4;y++) for (let x=0;x<4;x++) {
    const i=y*24+x*4; pixels.set(x===0 ? [0,0,255,0] : [240,40,80,255], i);
}
const rgb = T.dominant(pixels,4,4,24,4);
assert.ok(rgb[0] > .9 && rgb[1] < .2);
assert.equal(T.dominant(new Uint8Array(16),2,2,8,4),null);
assert.equal(T.palette(null,[1,1,1]),null);
const dark = T.palette(rgb,[1,1,1]);
const light = T.palette(rgb,[0,0,0]);
assert.notEqual(dark.highlight,light.highlight);
assert.ok(/^#[0-9a-f]{6}$/.test(dark.highlight));
const brightness = hex => hex.match(/[0-9a-f]{2}/g).reduce((n,x)=>n+parseInt(x,16),0);
assert.ok(brightness(dark.highlight)>brightness(light.highlight));
assert.equal(T.translationRow('翻译一\r\n\n翻译二\u2028罗马音'), '翻译一 翻译二 罗马音');
assert.equal(T.translationRow(null),'');
console.log('theme: artwork color, transparency, panel contrast and single translation row passed');
