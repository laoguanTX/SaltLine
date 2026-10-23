'use strict';
const assert = require('node:assert/strict');
const C = require('../cinnamon/saltbar@local/connection');
const fallback = '/desktop/cache/saltplayer-barlyrics/state.json';
const custom = '/home/another user/音乐缓存/saltplayer-barlyrics/state.json';
assert.equal(C.statePath({version:1,stateFile:custom},fallback),custom);
for (const config of [null,{}, {version:2,stateFile:custom}, {version:1,stateFile:'relative/state.json'},
    {version:1,stateFile:'/a/../state.json'}, {version:1,stateFile:'/a/evil\0/state.json'}, {version:1,stateFile:'/a/cover.png'}])
    assert.equal(C.statePath(config,fallback),fallback);
console.log('bridge connection: per-player cache routing, Unicode/spaces and old/manual fallback passed');
