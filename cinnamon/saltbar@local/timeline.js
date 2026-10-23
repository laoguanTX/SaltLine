'use strict';
function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
function fraction(cell, position) {
    if (position < cell.start) return 0;
    if (cell.end <= cell.start) return 1;
    return clamp((position - cell.start) / (cell.end - cell.start), 0, 1);
}
function positionAt(state, now, receivedAt, monotonicNow, offset) {
    const transit = clamp(now - state.sampledAt, 0, 500);
    return state.position + (state.playing ? transit + clamp(monotonicNow - receivedAt, 0, 500) : 0) + offset;
}
function visibleLine(state, position) {
    // The bridge owns line selection. Local interpolation may cross endTime
    // before the next snapshot arrives; keep displaying this line in that gap.
    return state && state.line && position >= state.line.start ? state.line : null;
}
function textFor(line) {
    // Retain spaces exactly as parsed by the host; only use cells when they cover the text.
    return line.text || line.cells.map(c => c.text).join('');
}
function utf8Length(text) {
    let size = 0;
    for (const ch of text) { const n = ch.codePointAt(0); size += n < 128 ? 1 : n < 2048 ? 2 : n < 65536 ? 3 : 4; }
    return size;
}
module.exports = {clamp, fraction, positionAt, visibleLine, textFor, utf8Length};
