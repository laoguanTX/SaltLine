#!/usr/bin/env python3
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import os
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('installer',ROOT/'plugin/src/main/resources/cinnamon-installer.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
UUID=module.UUID

class Settings:
    def __init__(self):
        self.values={'enabled-applets':['panel1:left:0:menu@cinnamon.org:0'], 'panels-enabled':['1:0:bottom'], 'next-applet-id':1}
    def get_strv(self,key):return list(self.values[key])
    def set_strv(self,key,value):self.values[key]=list(value);return True
    def get_int(self,key):return self.values[key]
    def set_int(self,key,value):self.values[key]=value;return True

class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.source=self.root/'source'
        self.source.mkdir()
        self.settings=Settings()
        self.reloads=[]
        self.integration=module.Integration(self.root/'data',self.root/'state',self.settings,lambda:self.reloads.append(True))
        self.assets({'metadata.json':json.dumps({'uuid':UUID,'version':'1.2.0'}).encode(),'applet.js':b'example'})
    def tearDown(self):self.temp.cleanup()
    def assets(self,files):
        manifest={}
        for name,data in files.items():
            path=self.source/'applet'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            manifest[name]=hashlib.sha256(data).hexdigest()
        (self.source/'assets.json').write_text(json.dumps(manifest))
    def owned(self):return [x for x in self.settings.get_strv('enabled-applets') if UUID in x]
    def test_install_reenable_disable_remove(self):
        self.integration.enable(self.source,'one')
        self.assertEqual(len(self.owned()),1)
        self.integration.enable(self.source,'one')
        self.assertEqual(len(self.owned()),1)
        self.assertEqual(self.reloads,[])
        self.integration.disable('one')
        self.assertEqual(self.owned(),[])
        self.assertTrue(self.integration.destination.exists())
        self.integration.enable(self.source,'two')
        self.integration.disable('one') # late stop from old plugin
        self.assertEqual(len(self.owned()),1)
        self.integration.disable('two',remove=True)
        self.assertEqual(self.owned(),[])
        self.assertFalse(self.integration.destination.exists())
        self.assertEqual(self.settings.get_strv('enabled-applets'),['panel1:left:0:menu@cinnamon.org:0'])
    def test_delete_after_restart_of_disabled_plugin(self):
        self.integration.enable(self.source,'one')
        self.integration.disable('one')
        self.integration.disable('new-plugin-instance',remove=True)
        self.assertFalse(self.integration.destination.exists())
    def test_delete_after_interrupted_player_exit(self):
        self.integration.enable(self.source,'old-process')
        self.integration.disable('new-process',remove=True)
        self.assertEqual(self.owned(),[])
        self.assertFalse(self.integration.destination.exists())
    def test_repair_interrupted_first_install(self):
        manifest=json.loads((self.source/'assets.json').read_text())
        self.integration._save({'uuid':UUID,'created':True,'files':manifest,'token':'interrupted','entries':[]})
        self.integration.destination.mkdir(parents=True)
        (self.integration.destination/'applet.js').write_text('partial')
        self.integration.enable(self.source,'repair')
        self.assertEqual((self.integration.destination/'applet.js').read_bytes(),b'example')
        self.assertEqual(len(self.owned()),1)
    def test_full_lifecycle_without_python_gi(self):
        fake = self.root/'gdbus'
        state = self.root/'desktop.json'
        state.write_text(json.dumps(self.settings.values))
        fake.write_text("""#!/usr/bin/python3 -S
import json,os,sys
from pathlib import Path
path=Path(os.environ['FAKE_GDBUS_STATE'])
settings=json.loads(path.read_text())
script=json.loads(sys.argv[-1])
if script.startswith('global.settings.'):
    method,arguments=script[len('global.settings.'):].split('(',1)
    args=json.loads('['+arguments[:-1]+']')
    if method.startswith('get_'): result=settings[args[0]]
    else:
        settings[args[0]]=args[1]
        path.write_text(json.dumps(settings))
        result=True
else: result=True
print('(true, '+repr(json.dumps(result,ensure_ascii=False))+')')
""")
        fake.chmod(0o755)
        env=dict(os.environ, XDG_DATA_HOME=str(self.root/'data'), XDG_STATE_HOME=str(self.root/'state'),
                 FAKE_GDBUS_STATE=str(state), PYTHONHOME='/missing-steam-python', PYTHONPATH='/missing-python-modules')
        def run(action):
            command=['/usr/bin/python3','-I','-S',str(ROOT/'plugin/src/main/resources/cinnamon-installer.py'),
                     action,'--source',str(self.source),'--token','no-gi','--gdbus',str(fake)]
            result=subprocess.run(command,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        report=run('diagnose')
        self.assertEqual(report['backend'],'gdbus')
        self.assertFalse(self.integration.destination.exists())
        self.assertFalse(self.integration.record_path.exists())
        run('enable'); run('enable')
        entries=json.loads(state.read_text())['enabled-applets']
        self.assertEqual(sum(UUID in x for x in entries),1)
        run('disable')
        self.assertFalse(any(UUID in x for x in json.loads(state.read_text())['enabled-applets']))
        run('enable'); run('remove')
        self.assertFalse(self.integration.destination.exists())
    def test_gdbus_reply_validation_and_error_message(self):
        desktop=module.GdbusDesktop('/usr/bin/gdbus')
        for output in ["(false, '{}')", '(true, bad-data)', '(true, 4)']:
            with patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,output,'')):
                with self.assertRaises(RuntimeError):desktop.get_strv('enabled-applets')
        with patch.object(module.subprocess,'run',side_effect=subprocess.TimeoutExpired('gdbus',5)):
            with self.assertRaisesRegex(RuntimeError,'Cinnamon 桌面'):desktop.get_strv('enabled-applets')
    def test_desktop_environment_preserves_bus_and_removes_launcher_libraries(self):
        with patch.dict(os.environ,{'PYTHONHOME':'custom','LD_LIBRARY_PATH':'custom','DBUS_SESSION_BUS_ADDRESS':'session','XDG_DATA_HOME':'user-data'}):
            env=module.desktop_environment()
            self.assertNotIn('PYTHONHOME',env)
            self.assertNotIn('LD_LIBRARY_PATH',env)
            self.assertEqual(env['DBUS_SESSION_BUS_ADDRESS'],'session')
            self.assertEqual(env['XDG_DATA_HOME'],'user-data')
    def test_cache_route_unicode_and_cleanup(self):
        state_file=self.root/'播放器 单独缓存'/'state.json'
        self.integration.enable(self.source,'one',state_file)
        config=json.loads((self.integration.destination/'bridge.json').read_text())
        self.assertEqual(config,{'version':1,'stateFile':str(state_file)})
        self.integration.disable('one',remove=True)
        self.assertFalse(self.integration.destination.exists())
    def test_invalid_cache_route_does_not_install(self):
        with self.assertRaises(module.InstallError):self.integration.enable(self.source,'one','relative/state.json')
        self.assertFalse(self.integration.destination.exists())
    def test_primary_monitor_and_malformed_entries(self):
        self.settings.values['panels-enabled']=['broken','2:1:bottom','3:0:top']
        self.settings.values['enabled-applets'] += ['panel3:left:invalid:old@local:21','unrelated:bad']
        self.integration.enable(self.source,'one')
        self.assertTrue(self.owned()[0].startswith('panel3:left:'))
        self.assertIn('unrelated:bad',self.settings.values['enabled-applets'])
    def test_readonly_panel_settings_are_not_reported_as_success(self):
        original=self.settings.get_strv('enabled-applets')
        self.settings.set_strv=lambda key,value:False
        with self.assertRaisesRegex(module.InstallError,'面板设置不可写'):self.integration.enable(self.source,'one')
        self.assertEqual(self.settings.get_strv('enabled-applets'),original)
    def test_load_failure_reports_manual_recovery(self):
        self.integration.verify_applet=lambda:False
        with patch.object(module.time,'monotonic',side_effect=[0,6]):
            result=self.integration.enable(self.source,'one')
        self.assertFalse(result['loaded'])
        self.assertIn('小程序已安装',result['warning'])
    def test_old_failed_instance_is_reloaded_on_enable(self):
        self.integration.enable(self.source,'one')
        readiness=iter([False,True])
        self.integration.verify_applet=lambda:next(readiness)
        result=self.integration.enable(self.source,'two')
        self.assertTrue(result['loaded'])
        self.assertEqual(len(self.reloads),1)
    def test_busy_install_has_bounded_wait(self):
        import fcntl
        path=self.root/'lock'
        with path.open('w') as first,path.open('r') as second:
            fcntl.flock(first,fcntl.LOCK_EX)
            with patch.object(module.time,'monotonic',side_effect=[0,4]):
                with self.assertRaisesRegex(module.InstallError,'另一个盐词'):module.acquire_lock(second)
    def test_manual_install_and_layout_preserved(self):
        self.integration.destination.mkdir(parents=True)
        (self.integration.destination/'metadata.json').write_text(json.dumps({'uuid':UUID}))
        manual='panel1:right:8:'+UUID+':99'
        self.settings.values['enabled-applets'].append(manual)
        self.integration.enable(self.source,'one')
        self.assertEqual(self.owned(),[manual])
        self.assertEqual(len(self.reloads),1)
        self.integration.disable('one',remove=True)
        self.assertEqual(self.owned(),[manual])
        self.assertTrue((self.integration.destination/'applet.js').exists())
    def test_moved_automatic_applet_removed_by_instance(self):
        self.integration.enable(self.source,'one')
        original=self.owned()[0]
        moved=original.replace('panel1:left:1:','panel2:right:4:')
        self.settings.values['enabled-applets'].remove(original)
        self.settings.values['enabled-applets'].append(moved)
        self.integration.enable(self.source,'two')
        self.assertEqual(self.owned(),[moved])
        self.integration.disable('two')
        self.assertEqual(self.owned(),[])
    def test_modified_file_and_settings_preserved(self):
        self.integration.enable(self.source,'one')
        modified=self.integration.destination/'applet.js';modified.write_text('custom edit')
        extra=self.integration.destination/'notes.txt';extra.write_text('user data')
        self.integration.disable('one',remove=True)
        self.assertEqual(modified.read_text(),'custom edit')
        self.assertTrue(extra.exists())
    def test_no_horizontal_panel_installs_without_changing_layout(self):
        self.settings.values['panels-enabled']=['1:0:left']
        result=self.integration.enable(self.source,'one')
        self.assertIsNotNone(result['warning'])
        self.assertEqual(self.owned(),[])
    def test_invalid_assets_no_partial_install(self):
        (self.source/'applet/applet.js').write_text('tampered')
        with self.assertRaises(RuntimeError):self.integration.enable(self.source,'one')
        self.assertFalse(self.integration.destination.exists())
        self.assertEqual(self.owned(),[])
    def test_traversal_rejected(self):
        (self.source/'assets.json').write_text(json.dumps({'../escape':'bad'}))
        with self.assertRaises(RuntimeError):self.integration.enable(self.source,'one')
        self.assertFalse(self.integration.destination.exists())
    def test_symlink_preserved(self):
        target=self.root/'unrelated';target.mkdir()
        self.integration.destination.parent.mkdir(parents=True)
        self.integration.destination.symlink_to(target,target_is_directory=True)
        with self.assertRaises(RuntimeError):self.integration.enable(self.source,'one')
        self.assertEqual(list(target.iterdir()),[])
    def test_version_update_reload_keeps_instance(self):
        self.integration.enable(self.source,'one');original=self.owned()
        self.assets({'metadata.json':json.dumps({'uuid':UUID,'version':'1.3.0'}).encode(),'applet.js':b'updated'})
        result=self.integration.enable(self.source,'two')
        self.assertTrue(result['changed'])
        self.assertEqual(self.owned(),original)
        self.assertEqual(len(self.reloads),1)
        self.assertEqual((self.integration.destination/'applet.js').read_bytes(),b'updated')

if __name__=='__main__':unittest.main()
