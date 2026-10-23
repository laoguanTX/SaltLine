#!/usr/bin/env python3
"""Install the Cinnamon applet for this user; optionally add to the panel."""
import argparse
import os
from pathlib import Path
import shutil

UUID = 'saltbar@local'
ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--enable', action='store_true', help='同时添加到首个水平面板左侧')
parser.add_argument('--remove', action='store_true', help='移除面板小程序及其启用项')
args = parser.parse_args()
data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))
dest = data / 'cinnamon/applets' / UUID
if args.remove or args.enable:
    import gi
    from gi.repository import Gio
    settings = Gio.Settings.new('org.cinnamon')
    entries = list(settings.get_strv('enabled-applets'))
if args.remove:
    settings.set_strv('enabled-applets', [x for x in entries if x.split(':')[3] != UUID])
    Gio.Settings.sync()
    if dest.exists(): shutil.rmtree(dest)
    print('已移除 SaltLine 面板小程序。播放器插件请在模组管理中删除。')
else:
    shutil.copytree(ROOT/'cinnamon'/UUID, dest, dirs_exist_ok=True)
    print(f'已安装：{dest}')
    if args.enable and not any(UUID in x.split(':') for x in entries):
        panels = settings.get_strv('panels-enabled')
        panel = next((x.split(':')[0] for x in panels if x.split(':')[-1] in ('top','bottom')), None)
        if panel is None: raise SystemExit('没有水平面板，请在 Cinnamon 小程序设置中手动添加。')
        instance = settings.get_int('next-applet-id')
        panel_name = 'panel' + panel
        orders = [int(x.split(':')[2]) for x in entries if x.startswith(panel_name+':left:')]
        entries.append(f'{panel_name}:left:{max(orders, default=-1)+1}:{UUID}:{instance}')
        settings.set_int('next-applet-id', instance+1)
        settings.set_strv('enabled-applets', entries)
        Gio.Settings.sync()
        print('已添加到面板；可在面板编辑模式中拖动位置。')
