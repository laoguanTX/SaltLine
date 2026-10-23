#!/usr/bin/env python3
"""Manage only SaltLine's applet files and panel entries, for the current user."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile

UUID = 'saltbar@local'


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
    def __init__(self, data_home, state_home, settings, reload_applet):
        self.destination = Path(data_home)/'cinnamon/applets'/UUID
        self.record_path = Path(state_home)/'saltplayer-barlyrics/cinnamon-install.json'
        self.settings = settings
        self.reload_applet = reload_applet

    def enable(self, source, token):
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
            panel = next((p.split(':')[0] for p in panels if p.split(':')[-1] in ('top', 'bottom')), None)
            if panel is None:
                warning = '没有水平面板；小程序已安装，请添加水平面板后重新启用模组。'
            else:
                panel = 'panel'+panel
                orders = [int(x.split(':')[2]) for x in entries if x.startswith(panel+':left:')]
                used = [int(x.split(':')[4]) for x in entries if len(x.split(':')) > 4 and x.split(':')[4].isdigit()]
                instance = max(self.settings.get_int('next-applet-id'), max(used, default=-1)+1)
                entry = f'{panel}:left:{max(orders, default=-1)+1}:{UUID}:{instance}'
                owned.append(entry)
                # Persist intended ownership before enabling it.
                record['entries'] = owned
                self._save(record)
                self.settings.set_int('next-applet-id', instance+1)
                self.settings.set_strv('enabled-applets', entries+[entry])
        record['entries'] = owned
        self._save(record)
        if changed and present:
            try: self.reload_applet()
            except Exception as error: warning = '小程序文件已更新，自动重新加载失败：'+str(error)
        return {'installed': True, 'changed': changed, 'warning': warning}

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
        if remaining != entries: self.settings.set_strv('enabled-applets', remaining)
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['enable', 'disable', 'remove'])
    parser.add_argument('--source', type=Path)
    parser.add_argument('--token', required=True)
    args = parser.parse_args()
    import fcntl
    import gi
    from gi.repository import Gio, GLib
    state = xdg_path('XDG_STATE_HOME', '.local/state')
    lock_dir = state/'saltplayer-barlyrics'
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir/'cinnamon-install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        schemas = Gio.SettingsSchemaSource.get_default()
        if not schemas or not schemas.lookup('org.cinnamon', True): raise RuntimeError('没有安装 Cinnamon 设置架构')
        settings = Gio.Settings.new('org.cinnamon')
        def reload_applet():
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            ok, message = bus.call_sync('org.Cinnamon', '/org/Cinnamon', 'org.Cinnamon', 'Eval',
                GLib.Variant('(s)', ('imports.ui.extension.reloadExtension("saltbar@local", imports.ui.extension.Type.APPLET); true',)),
                None, Gio.DBusCallFlags.NONE, 5000, None).unpack()
            if not ok: raise RuntimeError(message)
        integration = Integration(xdg_path('XDG_DATA_HOME', '.local/share'), state, settings, reload_applet)
        result = integration.enable(args.source, args.token) if args.action == 'enable' else integration.disable(args.token, remove=args.action == 'remove')
        Gio.Settings.sync()
        if result.get('warning'): print('WARNING: '+result['warning'])
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        import sys
        print('SaltLine Cinnamon: '+str(error), file=sys.stderr)
        sys.exit(1)
