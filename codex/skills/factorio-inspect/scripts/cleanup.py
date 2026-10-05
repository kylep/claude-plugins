#!/usr/bin/env python3
"""Plan transport cleanup from an engine export; does not edit the map."""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
D={0:(0,-1),4:(1,0),8:(0,1),12:(-1,0)}
T={'transport-belt','underground-belt','splitter','loader','loader-1x1'}
def plan(snapshot,area):
 es={e['id']:e for e in snapshot['entities']}
 selected={i for i,e in es.items() if e['type'] in T and area[0]<=e['position']['x']<area[2] and area[1]<=e['position']['y']<area[3]}
 f=defaultdict(set);b=defaultdict(set)
 def edge(a,z):
  if a and z:f[a].add(z);b[z].add(a)
 for e in es.values():
  for a in e.get('links',{}).get('inputs',[]):edge(a,e['id'])
  for z in e.get('links',{}).get('outputs',[]):edge(e['id'],z)
  if e['type']=='underground-belt' and e.get('io')=='input':edge(e['id'],e.get('underground'))
 roots={i for i in selected if es[i]['type'] in ['loader','loader-1x1'] and es[i].get('io')=='output'}
 sinks={i for i in selected if es[i]['type'] in ['loader','loader-1x1'] and es[i].get('io')=='input'}
 reserved=set();occupied={};grid={}
 for e in es.values():
  if e['type'] not in ['resource','explosion','item-entity']:
   q=e['bounds'];lo=q['left_top'];hi=q['right_bottom']
   for x in range(math.floor(lo['x']),math.floor(hi['x'])+1):
    for y in range(math.floor(lo['y']),math.floor(hi['y'])+1):
     if lo['x']<=x+.5<=hi['x'] and lo['y']<=y+.5<=hi['y']:occupied[x+.5,y+.5]=e;grid[x+.5,y+.5]=e
  for field in ['pickup','drop']:
   if e.get(field):reserved.add((math.floor(e[field]['x'])+.5,math.floor(e[field]['y'])+.5))
  if e['type']=='inserter' and e.get('source') in selected:sinks.add(e['source'])
 for e in es.values():
  if e['type']=='mining-drill' and e.get('drop'):
   q=e['drop'];v=grid.get((math.floor(q['x'])+.5,math.floor(q['y'])+.5))
   if v and v['id'] in selected:roots.add(v['id'])
 for i in selected:
  if any(z not in selected for z in f[i]):sinks.add(i)
  if any(z not in selected for z in b[i]):roots.add(i)
 def reach(seed,g):
  seen=set(seed);todo=list(seed)
  while todo:
   for z in g[todo.pop()]&selected:
    if z not in seen:seen.add(z);todo.append(z)
  return seen
 live=reach(roots,f)&reach(sinks,b);dead=selected-live
 # Preserve an entire pair when only one endpoint is in scope.
 for i in list(dead):
  if es[i]['type']=='underground-belt':
   other=es[i].get('underground')
   if other not in dead:dead.discard(i)
 row=lambda e:dict(name=e['name'],x=e['position']['x'],y=e['position']['y'])
 conversions=[]
 for i in sorted(selected-dead):
  e=es[i]
  if e['type']!='underground-belt' or e.get('io')!='input' or e.get('underground') not in selected-dead:continue
  z=es[e['underground']];x,y=e['position']['x'],e['position']['y'];xx,yy=z['position']['x'],z['position']['y'];dx,dy=D[e['direction']]
  length=round(abs(xx-x)+abs(yy-y))
  if z['direction']!=e['direction'] or z.get('io')!='output' or (xx,yy)!=(x+dx*length,y+dy*length):continue
  gap=[(x+dx*k,y+dy*k) for k in range(1,length)]
  if any(p in occupied or p in reserved for p in gap):continue
  # Exposing a surface belt must not create a new side-loading connection.
  cells=[(x+dx*k,y+dy*k) for k in range(length+1)];bad=False
  for px,py in cells:
   for nd,(nx,ny) in D.items():
    if nd==e['direction'] or nd==(e['direction']+8)%16:continue
    n=occupied.get((px+nx,py+ny))
    if n and n['type'] in T and n.get('io')!='input' and n['direction']==(nd+8)%16:bad=True
  if bad:continue
  conversions.append(dict(input=row(e),output=row(z),direction=e['direction'],cells=cells))
  for p in cells:occupied[tuple(p)]=dict(type='transport-belt',direction=e['direction'],io=None)
 return dict(dead_transport=[row(es[i]) for i in sorted(dead)],surface_pairs=conversions,retained_transport=len(selected)-len(dead))
def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('snapshot',type=Path);a.add_argument('--area',type=float,nargs=4,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
 result=plan(json.loads(args.snapshot.read_text()),args.area);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:len(v) if isinstance(v,list) else v for k,v in result.items()}))
if __name__=='__main__':main()
