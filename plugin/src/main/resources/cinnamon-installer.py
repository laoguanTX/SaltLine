#!/usr/bin/env python3
"""Manage only SaltLine's applet files and panel entries, for the current user."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import shutil
import subprocess
import sys
import time

UUID = 'saltbar@local'


class InstallError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def panel_id(panels):
    valid = [p.split(':') for p in panels if len(p.split(':')) == 3
             and p.split(':')[0].isdigit() and p.split(':')[-1] in ('top', 'bottom')]
    valid.sort(key=lambda p: p[1] != '0')
    return 'panel'+valid[0][0] if valid else None


def write_setting(settings, method, key, value):
    if not getattr(settings, method)(key, value):
        raise InstallError('settings-readonly', '面板设置不可写，请检查系统策略或以当前桌面用户运行播放器。')


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.saltbar-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def read_record(path):
    if not path.exists(): return {}
    record = json.loads(path.read_text())
    if record.get('uuid') != UUID: raise RuntimeError('SaltLine 安装记录无效，已保留现有文件。')
    return record


def asset_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts or '\\' in name:
        raise RuntimeError('非法资源路径')
    return path


class Integration:
    def __init__(self, data_home, state_home, settings, reload_applet, verify_applet=None):
        self.destination = Path(data_home)/'cinnamon/applets'/UUID
        self.record_path = Path(state_home)/'saltplayer-barlyrics/cinnamon-install.json'
        self.settings = settings
        self.reload_applet = reload_applet
        self.verify_applet = verify_applet

    def enable(self, source, token, state_file=None):
        source = Path(source)
        manifest = json.loads((source/'assets.json').read_text())
        assets = {}
        # Validate everything before modifying installed files or panel settings.
        for name, digest in manifest.items():
            relative = asset_path(name)
            data = (source/'applet'/relative).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest: raise RuntimeError('小程序资源校验失败：'+name)
            assets[name] = data
        if json.loads(assets['metadata.json'])['uuid'] != UUID: raise RuntimeError('小程序 UUID 不匹配')
        state_file = Path(state_file) if state_file is not None else xdg_path('XDG_CACHE_HOME', '.cache')/'saltplayer-barlyrics/state.json'
        if not state_file.is_absolute() or state_file.name != 'state.json' or '..' in state_file.parts:
            raise InstallError('invalid-state-path', '播放器提供的歌词缓存路径无效。')
        assets['bridge.json'] = json.dumps({'version':1, 'stateFile':str(state_file)}, ensure_ascii=False).encode()
        manifest['bridge.json'] = hashlib.sha256(assets['bridge.json']).hexdigest()
        record = read_record(self.record_path)
        existed = self.destination.exists()
        if self.destination.is_symlink(): raise RuntimeError('小程序目录是符号链接，请先手动处理。')
        if existed and not record:
            metadata = self.destination/'metadata.json'
            if not metadata.exists() or json.loads(metadata.read_text()).get('uuid') != UUID:
                raise RuntimeError('同名目录包含其他文件，已保留，请先手动处理。')
        created = record.get('created', not existed)
        for name in assets:
            target = self.destination/asset_path(name)
            for parent in [target, *target.parents]:
                if parent == self.destination.parent: break
                if parent.is_symlink(): raise RuntimeError('小程序路径包含符号链接：'+name)
        # Save ownership before creating files so an interrupted first install
        # can be repaired on the next enable without claiming an unknown directory.
        record = dict(record, uuid=UUID, created=created, files=manifest, token=token)
        self._save(record)
        changed = False
        self.destination.mkdir(parents=True, exist_ok=True)
        for name, data in assets.items():
            target = self.destination/asset_path(name)
            if target.is_symlink(): raise RuntimeError('小程序资源是符号链接：'+name)
            if not target.exists() or target.read_bytes() != data:
                atomic_write(target, data)
                changed = True
        entries = list(self.settings.get_strv('enabled-applets'))
        previous_instances = {x.split(':')[4] for x in record.get('entries', []) if len(x.split(':')) > 4}
        owned = [x for x in entries if len(x.split(':')) > 4 and x.split(':')[3].lstrip('!') == UUID and x.split(':')[4] in previous_instances]
        present = any(len(x.split(':')) > 3 and x.split(':')[3].lstrip('!') == UUID for x in entries)
        warning = None
        if not present:
            panels = self.settings.get_strv('panels-enabled')
            panel = panel_id(panels)
            if panel is None:
                warning = '没有水平面板；小程序已安装，请添加水平面板后重新启用模组。'
            else:
                orders = [int(x.split(':')[2]) for x in entries if x.startswith(panel+':left:') and x.split(':')[2].isdigit()]
                used = [int(x.split(':')[4]) for x in entries if len(x.split(':')) > 4 and x.split(':')[4].isdigit()]
                instance = max(self.settings.get_int('next-applet-id'), max(used, default=-1)+1)
                entry = f'{panel}:left:{max(orders, default=-1)+1}:{UUID}:{instance}'
                owned.append(entry)
                # Persist intended ownership before enabling it.
                record['entries'] = owned
                self._save(record)
                write_setting(self.settings, 'set_int', 'next-applet-id', instance+1)
                write_setting(self.settings, 'set_strv', 'enabled-applets', entries+[entry])
        record['entries'] = owned
        self._save(record)
        if present and (changed or self.verify_applet and not self.verify_applet()):
            try: self.reload_applet()
            except Exception as error: warning = '小程序文件已更新，自动重新加载失败：'+str(error)
        loaded = None
        if warning is None and self.verify_applet:
            deadline = time.monotonic()+5
            while time.monotonic() < deadline:
                if self.verify_applet():
                    loaded = True
                    break
                time.sleep(.2)
            if not loaded:
                warning = '小程序已安装但 Cinnamon 尚未加载。请在系统设置的小程序中检查“盐词”，或重新登录桌面后启用。'
                loaded = False
        return {'installed': True, 'changed': changed, 'loaded':loaded, 'warning': warning}

    def disable(self, token, remove=False):
        record = read_record(self.record_path)
        # A delayed stop must not disable a replacement instance. Explicit deletion
        # still cleans this plugin ID after a process restart or interrupted exit.
        if not record: return {'removedEntries': 0}
        if record.get('token') != token and not remove:
            return {'removedEntries': 0}
        entries = list(self.settings.get_strv('enabled-applets'))
        owned = set(record.get('entries', []))
        remaining = [entry for entry in entries if entry not in owned]
        # If a user moved an auto-added applet, follow its instance ID, not its position.
        owned_instances = {entry.split(':')[4] for entry in owned if len(entry.split(':')) > 4}
        remaining = [entry for entry in remaining if not (
            len(entry.split(':')) > 4 and entry.split(':')[3].lstrip('!') == UUID and entry.split(':')[4] in owned_instances)]
        if remaining != entries: write_setting(self.settings, 'set_strv', 'enabled-applets', remaining)
        record['entries'] = []
        self._save(record)
        if remove and record.get('created') and not self.destination.is_symlink():
            for name, digest in record.get('files', {}).items():
                path = self.destination/asset_path(name)
                if path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                    path.unlink()
            # Preserve modified files, extra files, and all Cinnamon user preferences.
            if self.destination.exists() and not any(self.destination.iterdir()): self.destination.rmdir()
            if not self.destination.exists(): self.record_path.unlink(missing_ok=True)
        return {'removedEntries': len(entries)-len(remaining)}

    def _save(self, record):
        atomic_write(self.record_path, json.dumps(record, ensure_ascii=False, sort_keys=True).encode())


def xdg_path(name, fallback):
    value = os.environ.get(name, '')
    return Path(value) if value and Path(value).is_absolute() else Path.home()/fallback


def desktop_environment():
    return {key: value for key, value in os.environ.items()
            if not key.startswith('PYTHON') and key not in {
                'LD_LIBRARY_PATH', 'LD_PRELOAD', 'GI_TYPELIB_PATH', 'GIO_EXTRA_MODULES', 'GIO_MODULE_DIR'}}


class GdbusDesktop:
    """Use Cinnamon's own settings object; no Python GI or local schemas required."""
    def __init__(self, executable=None):
        self.executable = executable or ('/usr/bin/gdbus' if Path('/usr/bin/gdbus').is_file() else shutil.which('gdbus'))
        if not self.executable:
            raise InstallError('missing-gdbus', '缺少桌面通信工具 gdbus，请安装发行版的 GLib 命令行工具后重试。')

    def evaluate(self, script):
        try:
            result = subprocess.run([self.executable, 'call', '--session', '--dest', 'org.Cinnamon',
                '--object-path', '/org/Cinnamon', '--method', 'org.Cinnamon.Eval',
                json.dumps(script, ensure_ascii=False)], capture_output=True, text=True,
                timeout=5, env=desktop_environment(), check=True)
        except (OSError, subprocess.SubprocessError) as error:
            raise InstallError('desktop-unavailable', '无法连接 Cinnamon 桌面，请登录 Cinnamon 后，以同一用户启动播放器。') from error
        output = result.stdout.strip()
        if not output.startswith('(true, ') or not output.endswith(')'):
            raise RuntimeError('Cinnamon 未接受面板操作，请检查桌面会话或使用手动安装方式。')
        try:
            encoded = ast.literal_eval(output[len('(true, '):-1].strip())
            return json.loads(encoded) if encoded else None
        except (ValueError, SyntaxError, TypeError) as error:
            raise RuntimeError('Cinnamon 返回了无法解析的面板设置。') from error

    @staticmethod
    def check_key(key):
        if key not in {'enabled-applets', 'panels-enabled', 'next-applet-id'}:
            raise ValueError('Unsupported Cinnamon setting')

    def get_strv(self, key):
        self.check_key(key)
        value = self.evaluate('global.settings.get_strv('+json.dumps(key)+')')
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise RuntimeError('Cinnamon 面板配置格式不正确。')
        return value

    def get_int(self, key):
        self.check_key(key)
        value = self.evaluate('global.settings.get_int('+json.dumps(key)+')')
        if type(value) is not int: raise RuntimeError('Cinnamon 小程序编号格式不正确。')
        return value

    def set_strv(self, key, value):
        self.check_key(key)
        if self.evaluate('global.settings.set_strv('+json.dumps(key)+', '+json.dumps(value, ensure_ascii=False)+')') is not True:
            raise RuntimeError('Cinnamon 拒绝写入面板配置。')
        self.evaluate('imports.gi.Gio.Settings.sync(); true')
        return True

    def set_int(self, key, value):
        self.check_key(key)
        if self.evaluate('global.settings.set_int('+json.dumps(key)+', '+json.dumps(value)+')') is not True:
            raise RuntimeError('Cinnamon 拒绝更新小程序编号。')
        self.evaluate('imports.gi.Gio.Settings.sync(); true')
        return True

    def running(self):
        return self.evaluate('(function(){const a=imports.ui.appletManager; return typeof a.getRunningInstancesForUuid === "function" && a.getRunningInstancesForUuid("saltbar@local").some(x => x._saltlineReady === true);})()') is True

    def reload(self):
        self.evaluate('imports.ui.extension.reloadExtension("saltbar@local", imports.ui.extension.Type.APPLET); true')


def desktop_backend(gdbus=None):
    if gdbus is None:
        try:
            import gi
            from gi.repository import Gio, GLib
            schemas = Gio.SettingsSchemaSource.get_default()
            if schemas and schemas.lookup('org.cinnamon', True):
                settings = Gio.Settings.new('org.cinnamon')
                # The memory backend is used only by isolated lifecycle tests.
                if os.environ.get('GSETTINGS_BACKEND') == 'memory':
                    return settings, lambda: None, Gio.Settings.sync, None, 'gi-memory'
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                owner = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                    'NameHasOwner', GLib.Variant('(s)', ('org.Cinnamon',)), None, Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
                if not owner:
                    raise InstallError('desktop-unavailable', '当前没有运行 Cinnamon 桌面，请登录 Cinnamon 后再启用模组。')
                def evaluate(script):
                    ok, message = bus.call_sync('org.Cinnamon', '/org/Cinnamon', 'org.Cinnamon', 'Eval',
                        GLib.Variant('(s)', (script,)), None, Gio.DBusCallFlags.NONE, 5000, None).unpack()
                    if not ok: raise InstallError('desktop-refused', 'Cinnamon 拒绝执行面板操作，请从系统设置检查小程序。')
                    return json.loads(message) if message else None
                desktop = GdbusDesktop.__new__(GdbusDesktop)
                desktop.evaluate = evaluate
                return settings, desktop.reload, Gio.Settings.sync, desktop.running, 'gi'
        except (ImportError, ValueError):
            pass
        except InstallError:
            raise
        except Exception:
            # Some distributions ship gi without working Gio typelibs.
            pass
    desktop = GdbusDesktop(gdbus)
    desktop.get_strv('enabled-applets')
    return desktop, desktop.reload, lambda: None, desktop.running, 'gdbus'


def acquire_lock(lock):
    import fcntl
    deadline = time.monotonic()+3
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise InstallError('installer-busy', '另一个盐词安装任务正在运行，请稍后重新启用模组。')
            time.sleep(.1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['enable', 'disable', 'remove', 'diagnose'])
    parser.add_argument('--source', type=Path)
    parser.add_argument('--token')
    parser.add_argument('--state-file', type=Path)
    parser.add_argument('--gdbus', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.action != 'diagnose' and not args.token: parser.error('--token is required for installation actions')
    if sys.version_info < (3, 8): raise InstallError('python-too-old', '自动安装需要 Python 3.8 或更新版本。')
    settings, reload_applet, sync, verify, backend = desktop_backend(args.gdbus)
    if args.action == 'diagnose':
        print(json.dumps({'ok':True, 'backend':backend, 'python':sys.version.split()[0],
            'horizontalPanel':panel_id(settings.get_strv('panels-enabled')), 'loaded':verify() if verify else None,
            'dataHome':str(xdg_path('XDG_DATA_HOME','.local/share')), 'stateFile':str(args.state_file) if args.state_file else None}, ensure_ascii=False))
        return
    state = xdg_path('XDG_STATE_HOME', '.local/state')
    lock_dir = state/'saltplayer-barlyrics'
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir/'cinnamon-install.lock').open('a') as lock:
        acquire_lock(lock)
        integration = Integration(xdg_path('XDG_DATA_HOME', '.local/share'), state, settings, reload_applet, verify)
        result = integration.enable(args.source, args.token, args.state_file) if args.action == 'enable' else integration.disable(args.token, remove=args.action == 'remove')
        sync()
        result['backend'] = backend
        if result.get('warning'): print('WARNING: '+result['warning'])
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        import sys
        if isinstance(error, PermissionError):
            error = InstallError('write-permission', '无法写入当前用户的小程序或缓存目录，请检查目录权限；不要以管理员身份启动播放器。')
        print('SaltLine Cinnamon: '+str(error), file=sys.stderr)
        print(json.dumps({'ok':False,'error':getattr(error,'code','installation-failed'),'message':str(error)},ensure_ascii=False))
        sys.exit(1)
