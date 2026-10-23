#!/usr/bin/env python3
"""Render isolated synthetic fixtures using the running Cinnamon applet."""
import json
from pathlib import Path
import time
from gi.repository import Gio, GLib

root = Path(__file__).resolve().parent.parent
output = root/'build/qa'
output.mkdir(parents=True,exist_ok=True)
bus = Gio.bus_get_sync(Gio.BusType.SESSION,None)
def evaluate(script):
    ok, result = bus.call_sync('org.Cinnamon','/org/Cinnamon','org.Cinnamon','Eval',GLib.Variant('(s)',(script,)),None,Gio.DBusCallFlags.NONE,10000,None).unpack()
    if not ok: raise RuntimeError(result)
    return json.loads(result) if result else None
script=(root/'tests/render-cinnamon.js').read_text().replace('@OUTPUT@',str(output))
evaluate('delete global._saltbarQA')
print(evaluate(script))
deadline=time.monotonic()+5
while time.monotonic()<deadline:
    frames=evaluate('global._saltbarQA')
    if frames: break
    time.sleep(.05)
else: raise RuntimeError('Artwork did not finish loading')
try:
    for frame in frames:
        assert frame['hasCover']
        assert frame['highlight'] != '#8bd5ca'
        assert frame['translationY'] >= frame['mainY']+frame['mainHeight']
        assert frame['translationY']+frame['translationHeight'] <= frame['height']
    print('Cinnamon: asynchronous cover decode, theme and two-row layout at 36/44 px passed')
    print(output)
finally: evaluate('delete global._saltbarQA')
