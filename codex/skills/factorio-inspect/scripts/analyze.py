#!/usr/bin/env python3
"""Summarize an export and trace directed item connections upstream of a recipe."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def inside(point, bounds):
    return (bounds['left_top']['x'] <= point['x'] <= bounds['right_bottom']['x'] and
            bounds['left_top']['y'] <= point['y'] <= bounds['right_bottom']['y'])


def analyze(snapshot, recipe=None, measurement=None):
    if snapshot.get('schema') != 1:
        raise ValueError('Unsupported snapshot schema')
    entities = snapshot['entities']
    nodes = {e['id']: e for e in entities}
    if len(nodes) != len(entities):
        raise ValueError('Duplicate entity identities; cannot reliably trace this export')
    previous, following = defaultdict(set), defaultdict(set)
    spatial = defaultdict(list)
    for e in entities:
        if e['type'] not in ('resource', 'tree', 'fish', 'item-entity'):
            b = e['bounds']
            for x in range(int(b['left_top']['x']//4), int(b['right_bottom']['x']//4)+1):
                for y in range(int(b['left_top']['y']//4), int(b['right_bottom']['y']//4)+1):
                    spatial[x, y].append(e)
    inferred = []

    def edge(a, b):
        if a and b:
            previous[b].add(a)
            following[a].add(b)

    def targets(e, point, field):
        if e.get(field):
            return [e[field]]
        if not point:
            return []
        hits = [x['id'] for x in spatial[int(point['x']//4), int(point['y']//4)]
                if x['id'] != e['id'] and inside(point, x['bounds'])]
        for hit in hits:
            inferred.append({'entity':e['id'], 'field':field, 'candidate':hit,
                             'method':'drop/pickup point overlaps entity bounds'})
        return hits

    for e in entities:
        i = e['id']
        for a in e.get('links', {}).get('inputs', []):
            edge(a, i)
        for b in e.get('links', {}).get('outputs', []):
            edge(i, b)
        if e['type'] == 'underground-belt' and e.get('io') == 'input':
            edge(i, e.get('underground'))
        if e['type'] in ('loader', 'loader-1x1'):
            if e.get('io') == 'input':
                edge(i, e.get('target'))
            else:
                edge(e.get('target'), i)
        if e['type'] == 'inserter':
            for a in targets(e, e.get('pickup'), 'source'):
                edge(a, i)
            for b in targets(e, e.get('drop'), 'target'):
                edge(i, b)
        if e['type'] == 'mining-drill':
            for b in targets(e, e.get('drop'), 'target'):
                edge(i, b)
    out = {'surface':snapshot['surface'], 'tick':snapshot['tick'],
           'area':snapshot.get('area'), 'entity_count':len(entities),
           'entity_types':dict(Counter(e['type'] for e in entities))}
    if recipe:
        selected = [e for e in entities if e.get('recipe', {}).get('name') == recipe]
        if not selected:
            raise ValueError(f'No machines found with recipe {recipe}')
        seen, todo = set(), [e['id'] for e in selected]
        while todo:
            i = todo.pop()
            if i not in seen:
                seen.add(i)
                todo.extend(previous[i])
        upstream = [nodes[i] for i in sorted(seen) if i in nodes]
        relevant = [e for e in upstream if e['type'] not in
                    ('transport-belt','underground-belt','splitter','inserter','loader','loader-1x1')]
        machines = []
        for e in relevant:
            row = {k:e[k] for k in ('id','name','type','position','status') if k in e}
            row['outgoing'] = sorted(following[e['id']])
            if e.get('recipe'):
                r = e['recipe']
                row['recipe'] = r['name']
                row['recipe_cycles_per_minute'] = 60*e['crafting_speed']/r['energy']
                row['productivity_bonus'] = e['productivity_bonus']
                if e['productivity_bonus'] == 0 and all(
                        p.get('probability',1)==1 and 'amount' in p for p in r['products']):
                    row['theoretical_products_per_minute'] = {
                        p['name']:p['amount']*row['recipe_cycles_per_minute'] for p in r['products']}
                else:
                    row['capacity_note'] = 'Evaluate productivity caps and probabilistic products separately'
            if e.get('resource'):
                row['resource'] = e['resource']
                row['base_mining_cycles_per_minute'] = (
                    60*e['mining_speed']*(1+e['speed_bonus'])/e['resource']['mining_time'])
                row['mining_note'] = 'Before force productivity, resource output multipliers, and power limits'
            machines.append(row)
        out['trace'] = {'recipe':recipe,'target_count':len(selected),'node_count':len(seen),
            'upstream_machines':machines, 'outside_export':sorted(seen-nodes.keys()),
            'geometric_edges':[v for v in inferred if v['entity'] in seen],
            'shared_branches': [{'id':i,'other_destinations':sorted(following[i]-seen)}
                                for i in sorted(seen) if following[i]-seen],
            'targets':[{'id':e['id'],'inputs':sorted(previous[e['id']]),
                        'outputs':sorted(following[e['id']])} for e in selected],
            'limits':['Graph is entity-level connectivity, not belt-lane routing or filter validation.',
                      'Fluid networks, trains, bots, circuit conditions and scripted transport need separate checks.',
                      'No downstream reachability to labs is implied by this upstream trace.']}
    if measurement:
        if measurement.get('schema') != 1 or measurement['elapsed_ticks'] <= 0:
            raise ValueError('Invalid measurement')
        ticks = measurement['elapsed_ticks']
        rows = []
        for m in measurement['machines']:
            if recipe and m['recipe'] != recipe:
                continue
            if sum(m['status_ticks'].values()) != ticks:
                raise ValueError('Incomplete tick-status accounting')
            e = nodes.get(m['id'])
            row = dict(m)
            if 'delta' in m and m['delta'] >= 0 and not m.get('recipe_changed'):
                row['completion_counter_per_minute'] = m['delta']*3600/ticks
                r = e.get('recipe', {}) if e else {}
                products = r.get('products', [])
                if (e and e.get('productivity_bonus') == 0 and len(products)==1
                        and products[0].get('amount')==1 and products[0].get('probability',1)==1):
                    row['verified_item_per_minute'] = row['completion_counter_per_minute']
                    row['item'] = products[0]['name']
            else:
                row['invalid'] = 'Destroyed, counter reset, or recipe changed during measurement'
            rows.append(row)
        totals = defaultdict(float)
        for row in rows:
            if 'verified_item_per_minute' in row:
                totals[row['item']] += row['verified_item_per_minute']
        out['measurement'] = {'elapsed_ticks':ticks, 'simulated_minutes':ticks/3600,
            'verified_items_per_minute':dict(totals),'machines':rows,
            'limits':'Only deterministic single-item recipes without productivity are converted from completion counters to item rates. Other counters remain explicitly raw.'}
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('snapshot',type=Path)
    p.add_argument('--recipe')
    p.add_argument('--measurement',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    result=analyze(json.loads(a.snapshot.read_text()),a.recipe,
                   json.loads(a.measurement.read_text()) if a.measurement else None)
    text=json.dumps(result,indent=2)+'\n'
    if a.output:
        a.output.write_text(text)
        print(a.output)
    else:
        print(text,end='')


if __name__=='__main__':
    main()
