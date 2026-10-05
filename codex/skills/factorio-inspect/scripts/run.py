#!/usr/bin/env python3
"""Inspect a Factorio 2.x scenario/save using an isolated headless instance."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

SKILL = Path(__file__).resolve().parents[1]
MOD = 'codex-factorio-inspect'
MAC = Path.home() / 'Library/Application Support'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def hashes(path):
    if path.is_file():
        return {path.name: digest(path)}
    return {str(p.relative_to(path)): digest(p)
            for p in sorted(path.rglob('*')) if p.is_file()}


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def lua(value):
    if value is None:
        return 'nil'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '{' + ','.join(lua(x) for x in value) + '}'
    return '{' + ','.join('[' + lua(k) + ']=' + lua(v) for k, v in value.items()) + '}'


def stop(process):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    total_started=time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--scenario', type=Path, help='Scenario folder')
    source.add_argument('--save', type=Path, help='Save ZIP')
    parser.add_argument('--run-dir', required=True, type=Path, help='New output directory; must not exist')
    parser.add_argument('--binary', type=Path, default=MAC / 'Steam/steamapps/common/Factorio/factorio.app/Contents/MacOS/factorio')
    parser.add_argument('--data', type=Path, help='Factorio read-data folder (auto-detected for macOS/Linux layouts)')
    parser.add_argument('--user-data', type=Path, default=MAC / 'factorio')
    parser.add_argument('--surface', default='nauvis')
    parser.add_argument('--area', type=float, nargs=4, metavar=('X1','Y1','X2','Y2'))
    parser.add_argument('--tiles', action='store_true', help='Include tiles; requires a bounded --area')
    parser.add_argument('--recipe', help='Recipe to measure; omit to measure all crafting machines in scope')
    parser.add_argument('--profile', choices=('snapshot','diagnostic','sustained'),
                        help='snapshot: no simulation interval; diagnostic: 1+1 min; sustained: 10+10 min')
    parser.add_argument('--warmup-ticks', type=int, help='Explicit warmup; overrides the selected profile')
    parser.add_argument('--measure-ticks', type=int, help='Explicit measured ticks; 0 = snapshot, 36000 = ten minutes')
    parser.add_argument('--speed', type=float, default=64, help='Simulation speed, default 64; does not shorten simulated intervals')
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    profiles={'snapshot':(0,0),'diagnostic':(3600,3600),'sustained':(36000,36000)}
    if not args.profile and args.measure_ticks and args.warmup_ticks is None:
        parser.error('Measurement requires --warmup-ticks (0 is allowed) or an explicit --profile')
    warmup,measure=profiles[args.profile or 'snapshot']
    args.warmup_ticks=warmup if args.warmup_ticks is None else args.warmup_ticks
    args.measure_ticks=measure if args.measure_ticks is None else args.measure_ticks
    if not math.isfinite(args.speed) or not math.isfinite(args.timeout):
        parser.error('Speed and timeout must be finite')
    if args.area and not all(math.isfinite(v) for v in args.area):
        parser.error('Area coordinates must be finite')
    if args.measure_ticks < 0 or args.warmup_ticks < 0 or not 0 < args.speed <= 64 or args.timeout <= 0:
        parser.error('Ticks must be nonnegative, speed in (0,64], timeout positive')
    if args.area and (args.area[0] >= args.area[2] or args.area[1] >= args.area[3]):
        parser.error('Area must have X1<X2 and Y1<Y2')
    if args.tiles and (not args.area or (args.area[2]-args.area[0])*(args.area[3]-args.area[1]) > 1000000):
        parser.error('Tile export requires an area of at most 1,000,000 tiles')
    src = (args.scenario or args.save).expanduser().resolve()
    binary = args.binary.expanduser().resolve()
    user = args.user_data.expanduser().resolve()
    root = args.run_dir.expanduser().resolve()
    if not binary.is_file() or not src.exists():
        parser.error('Binary or source does not exist')
    if args.scenario and not src.is_dir() or args.save and not src.is_file():
        parser.error('Scenario must be a directory; save must be a file')
    if root == src or src in root.parents or root == user or user in root.parents:
        parser.error('Run directory must be outside source and Factorio user-data')
    candidates = [binary.parent.parent / 'data', binary.parent.parent.parent / 'data']
    data = args.data.expanduser().resolve() if args.data else next((p for p in candidates if (p/'base/info.json').exists()), None)
    if not data:
        parser.error('Cannot find game data; supply --data')
    info = json.loads((data/'base/info.json').read_text())
    if not info['version'].startswith('2.'):
        parser.error('Bundled exporter targets Factorio 2.x; adapt for this version first')
    original = hashes(src)
    settings_before = {str(p): digest(p) for p in (user/'mods/mod-list.json', user/'mods/mod-settings.dat') if p.exists()}
    root.mkdir(parents=True, exist_ok=False)
    mods = root / 'mods'
    mods.mkdir()
    for p in (user/'mods').iterdir():
        if p.name.startswith(MOD):
            raise RuntimeError('Source mod directory already contains the inspection mod; use an uninstrumented source')
        if p.suffix in ('.json', '.dat'):
            shutil.copy2(p, mods/p.name)
        elif p.is_dir() or p.suffix=='.zip':
            (mods/p.name).symlink_to(p.resolve(), target_is_directory=p.is_dir())
    modlist = json.loads((mods/'mod-list.json').read_text())
    modlist['mods'].append({'name':MOD, 'enabled':True})
    save_json(mods/'mod-list.json',modlist)
    addon = mods/(MOD+'_0.1.0')
    shutil.copytree(SKILL/'assets/inspection-mod', addon)
    save_json(addon/'info.json', {'name':MOD,'version':'0.1.0','title':'Codex map inspection',
        'author':'Local inspection','factorio_version':'.'.join(info['version'].split('.')[:2]),'dependencies':['base']})
    cfg = {'surface':args.surface,'area':[args.area[:2],args.area[2:]] if args.area else None,
           'tiles':args.tiles,'recipe':args.recipe,'warmup_ticks':args.warmup_ticks,
           'measure_ticks':args.measure_ticks,'speed':args.speed}
    (addon/'inspection-config.lua').write_text('return ' + lua(cfg) + '\n')
    if args.scenario:
        dest=root/'scenarios/inspection-source'
        shutil.copytree(src,dest)
        launch=['--start-server-load-scenario','inspection-source']
    else:
        dest=root/'saves/source.zip'
        dest.parent.mkdir()
        shutil.copy2(src,dest)
        launch=['--start-server',str(dest)]
    config=root/'config.ini'
    config.write_text(f'[path]\nread-data={data}\nwrite-data={root}\n')
    server=json.loads((data/'server-settings.example.json').read_text())
    server.update({'name':'Local Factorio inspection','description':'Isolated analysis copy',
        'visibility':{'public':False,'lan':False},'require_user_verification':False,
        'auto_pause':False,'autosave_interval':0,'username':'','password':'','token':''})
    save_json(root/'server-settings.json',server)
    cmd=[str(binary),'--config',str(config),'--mod-directory',str(mods),*launch,
         '--server-settings',str(root/'server-settings.json'),'--bind','127.0.0.1:0','--disable-audio']
    manifest={'source':str(src),'source_sha256':original,'version':info['version'],
        'binary':str(binary),'config':cfg,'command':cmd,'exporter_sha256':hashes(addon),
        'input_settings_sha256':settings_before,'snapshot_note':'Initial export is the first inspection-mod tick after loading; scenario/mod initialization has run.',
        'test_changes':['Added separate inspection mod','Unpaused isolated save if needed','Changed simulation speed','Paused at completion'],
        'status':'running'}
    save_json(root/'manifest.json',manifest)
    output=root/'script-output/factorio-inspect'
    started=time.monotonic()
    phases={'preparation':started-total_started}
    phase_started=started
    phase='engine'
    proc=None
    failure=None
    try:
        with (root/'console.log').open('w') as log:
            proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
            # A saved map may be paused. This changes only the disposable run.
            proc.stdin.write(b'/c game.tick_paused=false\n')
            proc.stdin.flush()
            next_report=started+30
            while True:
                if (output/'error.json').exists():
                    raise RuntimeError((output/'error.json').read_text())
                if (output/'done.json').exists():
                    break
                if proc.poll() is not None:
                    raise RuntimeError(f'Factorio exited {proc.returncode}; see {root / "console.log"}')
                if time.monotonic()-started>args.timeout:
                    raise TimeoutError(f'Inspection exceeded {args.timeout}s; see console.log')
                if time.monotonic()>=next_report:
                    print(f'Factorio inspection running: {int(time.monotonic()-started)}s',flush=True)
                    next_report+=30
                time.sleep(0.2)
            phases['engine']=time.monotonic()-phase_started
            phase='validation'; phase_started=time.monotonic()
            required=['initial','final','done'] + (['baseline','measurement'] if args.measure_ticks else [])
            # Parse each file once without retaining all large snapshots.
            final=None; m=None
            for name in required:
                obj=json.loads((output/(name+'.json')).read_text())
                if obj.get('schema')!=1:
                    raise RuntimeError(f'Unexpected schema in {name}')
                if name=='final': final=obj
                if name=='measurement': m=obj
                if name=='done': manifest['snapshot_work']=obj
            if args.measure_ticks:
                if m['elapsed_ticks']!=args.measure_ticks or not m['machines']:
                    raise RuntimeError('Incomplete measurement')
                if any(sum(x['status_ticks'].values())!=args.measure_ticks for x in m['machines']):
                    raise RuntimeError('Incomplete status sampling')
            manifest['active_mods']=final['active_mods']
            manifest['active_mod_sha256']={}
            for name, version in final['active_mods'].items():
                for path in (mods/(name+'_'+version+'.zip'),mods/(name+'_'+version),mods/name):
                    if path.exists():
                        manifest['active_mod_sha256'][name]=hashes(path)
                        break
            manifest['status']='complete'
    except BaseException as e:
        failure=e
        manifest['status']='failed';manifest['error']=str(e)
    finally:
        phases[phase]=time.monotonic()-phase_started
        shutdown_started=time.monotonic()
        if proc:
            stop(proc)
            proc.stdin.close()
        phases['shutdown']=time.monotonic()-shutdown_started
        verify_started=time.monotonic()
        manifest['source_unchanged']=hashes(src)==original
        manifest['input_settings_unchanged']=all(digest(Path(p))==v for p,v in settings_before.items())
        phases['preservation_check']=time.monotonic()-verify_started
        milestones={}
        for line in (root/'console.log').read_text().splitlines():
            match=re.match(r'\s*(\d+\.\d+)\s',line)
            if not match: continue
            for key, marker in [('in_game','to(InGame)'),('initial_ready','FACTORIO_INSPECT_INITIAL_READY'),
                                ('measurement_started','FACTORIO_INSPECT_MEASUREMENT_STARTED'),
                                ('done','FACTORIO_INSPECT_DONE')]:
                if marker in line: milestones[key]=float(match.group(1))
        manifest['engine_log_seconds']=milestones
        manifest['phase_seconds']={k:round(v,4) for k,v in phases.items()}
        # Preserve the old engine-to-shutdown metric for comparisons.
        manifest['wall_seconds']=round(time.monotonic()-started,2)
        manifest['total_seconds']=round(time.monotonic()-total_started,2)
        save_json(root/'manifest.json',manifest)
    if not manifest['source_unchanged'] or not manifest['input_settings_unchanged']:
        raise RuntimeError('Source or user mod settings changed during run; inspect manifest')
    if failure:
        raise failure
    print(json.dumps({'status':'complete','run_dir':str(root),'exports':str(output),
                      'source_unchanged':True,'total_seconds':manifest['total_seconds'],
                      'phase_seconds':manifest['phase_seconds']}))


if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print(f'ERROR: {e}',file=sys.stderr)
        sys.exit(1)
