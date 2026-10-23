#!/usr/bin/env python3
import json, os, pathlib, shutil, subprocess, tempfile
from build import ROOT, CACHE, build, find_javac
build()
javac = find_javac()
java = str(pathlib.Path(javac).with_name('java'))
cp = os.pathsep.join(map(str,[ROOT/'build/classes',CACHE/'api.jar',CACHE/'pf4j.jar',CACHE/'kotlin-stdlib.jar']))
subprocess.run([javac,'--release','25','-proc:none','-cp',cp,'-d',str(ROOT/'build/classes'),*[str(p) for p in sorted((ROOT/'tests').glob('*.java'))]],check=True)
with tempfile.TemporaryDirectory() as temp:
    env = dict(os.environ, XDG_CACHE_HOME=temp)
    out = subprocess.check_output([java,'-ea','-cp',cp,'local.saltbar.BridgeTest'],env=env,text=True)
    data = json.loads(out)
    assert data['line']['cells'][1]['text'] == '好😀'
    assert data['line']['translation'] == 'hello\n"world"'
    assert data['title'] == 'title\t\\'
    assert not (pathlib.Path(temp)/'saltplayer-barlyrics/state.json').exists()
print('bridge: selection, JSON escaping, lifecycle passed')
node = shutil.which('node')
if not node:
    local_node = pathlib.Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
    node = str(local_node) if local_node.is_file() else None
if not node:
    raise SystemExit('完整测试需要 Node.js，请先安装并加入 PATH。')
for script in (ROOT/'cinnamon').rglob('*.js'): subprocess.run([node,'--check',str(script)],check=True)
for name in ['timeline.test.js', 'theme.test.js']:
    subprocess.run([node,str(ROOT/'tests'/name)],check=True)

subprocess.run(['python3', str(ROOT/'tests/installer.test.py')], check=True)
with tempfile.TemporaryDirectory() as temp:
    env = dict(os.environ, XDG_DATA_HOME=temp+'/data', XDG_STATE_HOME=temp+'/state', GSETTINGS_BACKEND='memory')
    subprocess.run([java,'-ea','-cp',cp,'local.saltbar.CinnamonIntegrationTest'],env=env,check=True)
