#!/usr/bin/env python3
"""Build against real Workshop API jars, without embedding host classes."""
import os
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache'
VERSION = (ROOT / 'VERSION').read_text().strip()
DEPS = {
    'api.jar': 'https://jitpack.io/com/github/Moriafly/spw-workshop-api/spw-workshop-api/0.1.0-dev22/spw-workshop-api-0.1.0-dev22.jar',
    'pf4j.jar': 'https://repo.maven.apache.org/maven2/org/pf4j/pf4j/3.12.0/pf4j-3.12.0.jar',
    'kotlin-stdlib.jar': 'https://repo.maven.apache.org/maven2/org/jetbrains/kotlin/kotlin-stdlib/2.2.20/kotlin-stdlib-2.2.20.jar',
}
def find_javac():
    java_home = os.environ.get('JAVA_HOME')
    bundled = sorted(CACHE.glob('jdk-*/bin/javac'))
    candidate = str(Path(java_home) / 'bin/javac') if java_home else shutil.which('javac') or (str(bundled[-1]) if bundled else None)
    if not candidate or not Path(candidate).is_file():
        raise SystemExit('需要 JDK 25 或更新版本，请设置 JAVA_HOME。')
    return str(Path(candidate).resolve())


def build():
    CACHE.mkdir(exist_ok=True)
    metadata = json.loads((ROOT / 'cinnamon/saltbar@local/metadata.json').read_text())
    if metadata['version'] != VERSION:
        raise SystemExit('VERSION 与 Cinnamon metadata.json 版本不一致。')
    javac = find_javac()
    for name, url in DEPS.items():
        dest = CACHE / name
        if not dest.exists():
            with urllib.request.urlopen(url, timeout=90) as response:
                dest.write_bytes(response.read())
        with zipfile.ZipFile(dest): pass
    classes = ROOT / 'build/classes'
    if classes.exists(): shutil.rmtree(classes)
    classes.mkdir(parents=True)
    cp = os.pathsep.join(str(CACHE / n) for n in DEPS)
    sources = sorted((ROOT / 'plugin/src/main/java').rglob('*.java'))
    subprocess.run([javac, '--release', '25', '-proc:none', '-classpath', cp, '-d', str(classes), *map(str, sources)], check=True)
    bundled = classes / 'saltbar-cinnamon'
    bundled.mkdir()
    assets = ROOT / 'cinnamon/saltbar@local'
    manifest = {}
    for path in sorted(assets.rglob('*')):
        if path.is_file():
            relative = path.relative_to(assets).as_posix()
            target = bundled / 'applet' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    (bundled/'assets.list').write_text('\n'.join(manifest)+'\n')
    (bundled/'assets.json').write_text(json.dumps(manifest, sort_keys=True))
    shutil.copyfile(ROOT/'plugin/src/main/resources/cinnamon-installer.py', bundled/'installer.py')
    meta = classes / 'META-INF'
    meta.mkdir()
    (meta / 'extensions.idx').write_text('local.saltbar.PlaybackListener\n')
    (meta / 'MANIFEST.MF').write_text(
        'Manifest-Version: 1.0\nPlugin-Class: local.saltbar.MainPlugin\n'
        f'Plugin-Id: local.saltbar\nPlugin-Version: {VERSION}\n'
        'Plugin-Provider: laoguanTX\nPlugin-Name: SaltLine (盐词)\n'
        'Plugin-Description: Word-synced lyrics for the Cinnamon panel\n'
        'Plugin-Has-Config: false\nPlugin-Permissions: library-read\n\n')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    mod = dist / f'saltline-{VERSION}.spmod'
    with zipfile.ZipFile(mod, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(classes.rglob('*')):
            if path.is_file(): z.write(path, 'classes/' + path.relative_to(classes).as_posix())
    with zipfile.ZipFile(dist / f'saltline-cinnamon-{VERSION}.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted((ROOT / 'cinnamon').rglob('*')):
            if path.is_file(): z.write(path, path.relative_to(ROOT / 'cinnamon'))
    print(mod)
if __name__ == '__main__': build()
