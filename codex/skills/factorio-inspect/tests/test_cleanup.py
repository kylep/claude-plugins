import pytest
pytestmark = pytest.mark.unit
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('cleanup',Path(__file__).resolve().parents[1]/'scripts/cleanup.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def entity(i,t,x,y,**kw):
 return dict(id=i,type=t,name=t,position=dict(x=x,y=y),bounds=dict(left_top=dict(x=x-.4,y=y-.4),right_bottom=dict(x=x+.4,y=y+.4)),direction=4,**kw)
def snapshot(extra=None):
 es=[entity('source','loader-1x1',-.5,.5,io='output',links={'outputs':['in']}),entity('in','underground-belt',.5,.5,io='input',underground='out'),entity('out','underground-belt',3.5,.5,io='output',underground='in',links={'outputs':['sink']}),entity('sink','loader-1x1',4.5,.5,io='input'),entity('dead','transport-belt',6.5,.5)]
 return {'entities':es+(extra or [])}
def test_prunes_dead_tail_and_exposes_clear_span():
 p=m.plan(snapshot(),[-2,-2,10,10]);assert len(p['dead_transport'])==1;assert len(p['surface_pairs'])==1;assert len(p['surface_pairs'][0]['cells'])==4
def test_obstacle_preserves_underground():
 assert not m.plan(snapshot([entity('pipe','pipe',1.5,.5)]),[-2,-2,10,10])['surface_pairs']
def test_inserter_pickup_preserves_underground():
 e=entity('arm','inserter',1.5,2.5,pickup={'x':1.5,'y':.5});assert not m.plan(snapshot([e]),[-2,-2,10,10])['surface_pairs']
def test_side_loading_preserves_underground():
 e=entity('side','transport-belt',1.5,-.5);e['direction']=8;assert not m.plan(snapshot([e]),[-2,-2,10,10])['surface_pairs']
def test_scoped_pair_is_never_half_removed():
 p=m.plan(snapshot(),[0,-2,2,10]);assert not p['dead_transport'];assert not p['surface_pairs']
