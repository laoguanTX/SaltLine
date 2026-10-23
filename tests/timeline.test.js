'use strict';
const assert = require('node:assert/strict');
const T = require('../cinnamon/saltbar@local/timeline');
const cell = {start: 1000, end: 1400, text: '词'};
assert.equal(T.fraction(cell, 999), 0);
assert.equal(T.fraction(cell, 1200), 0.5);
assert.equal(T.fraction(cell, 1400), 1);
assert.equal(T.fraction({start: 100, end: 100}, 100), 1);
assert.equal(T.fraction({start: 100, end: 100}, 99), 0);
const state = {position: 1000, sampledAt: 5000, playing: true, line: {start:1000,end:2000}};
assert.equal(T.positionAt(state, 5050, 100, 200, 0), 1150);
assert.equal(T.positionAt({...state, playing:false}, 5050, 100, 200, 0), 1000);
assert.equal(T.positionAt(state, 5000, 100, 200, -100), 1000);
assert.equal(T.positionAt({...state, position:100}, 5000, 100, 100, 0), 100); // seek backward replaces anchor
assert.equal(T.visibleLine(state, 2000), state.line);
assert.equal(T.visibleLine(state, 2500), state.line); // hold after last word ends
assert.equal(T.visibleLine(state, T.positionAt({...state, position:1990}, 5020, 100, 120, 0)), state.line);
assert.equal(T.fraction(cell, 2500), 1); // retained line stays fully highlighted
const next = {...state, line: {start:3000,end:4000}};
assert.equal(T.visibleLine(next, 3000), next.line);
assert.equal(T.visibleLine({...state, line:null}, 2500), null); // reset clears retained line
assert.equal(T.visibleLine(null, 2500), null); // disconnect clears retained line
assert.equal(T.visibleLine(state, 999), null);
assert.equal(T.visibleLine(state, 1000), state.line);
assert.equal(T.utf8Length('a你😀'), 8);
assert.equal(T.textFor({text:'a b', cells:[]}), 'a b');
console.log('timeline: line-gap retention, snapshot handoff, resets and timing passed');
