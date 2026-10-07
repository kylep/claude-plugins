-- Separate mod: never replace another mod's or the scenario's event handlers.
local cfg = require('inspection-config')
local prefix = 'factorio-inspect/'
local fresh_run = true
local snapshot_tick, snapshot_json
local snapshot_builds, snapshot_reuses = 0, 0
local function write(name, value)
  helpers.write_file(prefix .. name .. '.json', helpers.table_to_json(value), false)
end
local status_names = {}
for name, value in pairs(defines.entity_status) do status_names[value] = name end
local function key(e)
  if not e or not e.valid then return nil end
  return e.unit_number and tostring(e.unit_number) or
    (e.name .. '@' .. e.position.x .. ',' .. e.position.y)
end
local function contents(inv) return inv and inv.get_contents() or {} end
local craft = {['assembling-machine']=true, furnace=true}
local belt = {['transport-belt']=true, ['underground-belt']=true,
  splitter=true, ['loader-1x1']=true, loader=true}
local function record(e)
  local v = {id=key(e), name=e.name, type=e.type, position=e.position,
    bounds=e.bounding_box, direction=e.direction, force=e.force.name,
    quality=e.quality.name, status=status_names[e.status], energy=e.energy}
  if craft[e.type] then
    local r = e.get_recipe()
    v.recipe = r and {name=r.name, energy=r.energy, products=r.products,
      ingredients=r.ingredients, enabled=r.enabled}
    v.crafting_speed=e.crafting_speed
    v.productivity_bonus=e.productivity_bonus
    v.products_finished=e.products_finished
    v.modules=contents(e.get_module_inventory())
    v.input=contents(e.get_inventory(e.type=='furnace' and
      defines.inventory.furnace_source or defines.inventory.assembling_machine_input))
    v.output=contents(e.get_output_inventory())
  elseif e.type=='mining-drill' then
    v.mining_speed=e.prototype.mining_speed
    v.speed_bonus=e.speed_bonus
    v.productivity_bonus=e.productivity_bonus
    v.drop=e.drop_position
    v.target=key(e.drop_target)
    local r=e.mining_target
    v.resource=r and {name=r.name, amount=r.amount,
      mining_time=r.prototype.mineable_properties.mining_time}
  elseif e.type=='resource' then
    v.amount=e.amount
  elseif e.type=='inserter' then
    v.pickup=e.pickup_position; v.drop=e.drop_position
    v.source=key(e.pickup_target); v.target=key(e.drop_target)
    v.stack_override=e.inserter_stack_size_override
    v.hand=e.held_stack.valid_for_read and
      {name=e.held_stack.name,count=e.held_stack.count} or nil
  elseif e.type=='container' or e.type=='logistic-container' then
    v.contents=contents(e.get_inventory(defines.inventory.chest))
  elseif e.type=='lab' then
    v.contents=contents(e.get_inventory(defines.inventory.lab_input))
  end
  if belt[e.type] then
    v.belt_speed=e.prototype.belt_speed
    v.links={inputs={}, outputs={}}
    for side, entities in pairs(e.belt_neighbours) do
      for _, b in pairs(entities) do table.insert(v.links[side],key(b)) end
    end
    v.lanes={}
    for i=1,e.get_max_transport_line_index() do
      v.lanes[i]=e.get_transport_line(i).get_contents()
    end
    if e.type=='underground-belt' then
      v.underground=key(e.neighbours); v.io=e.belt_to_ground_type
    elseif e.type=='loader-1x1' or e.type=='loader' then
      v.io=e.loader_type; v.target=key(e.loader_container)
    end
  end
  return v
end
local function surface()
  return assert(game.surfaces[cfg.surface], 'Missing surface: '..cfg.surface)
end
local function entities()
  return surface().find_entities_filtered{area=cfg.area}
end
local function snapshot(name)
  -- Two names can describe the exact same state within one callback.
  -- Reuse bytes only within that tick; do not retain stale map state.
  if snapshot_tick == game.tick then
    helpers.write_file(prefix .. name .. '.json', snapshot_json, false)
    snapshot_reuses = snapshot_reuses + 1
    return
  end
  local s=surface()
  local out={schema=1,tick=game.tick,surface=s.name,area=cfg.area,
    active_mods=script.active_mods,map_gen_settings=s.map_gen_settings,
    game_speed=game.speed,speed_before_inspection=storage.speed_before_inspection,
    tick_paused=game.tick_paused,
    entities={},chunks={},forces={}}
  for c in s.get_chunks() do out.chunks[#out.chunks+1]={x=c.x,y=c.y} end
  for _, f in pairs(game.forces) do
    out.forces[f.name]={mining_productivity=f.mining_drill_productivity_bonus}
  end
  for _,e in pairs(entities()) do out.entities[#out.entities+1]=record(e) end
  if cfg.tiles then
    out.tiles={}
    for _,t in pairs(s.find_tiles_filtered{area=cfg.area}) do
      out.tiles[#out.tiles+1]={name=t.name,position=t.position}
    end
  end
  snapshot_json=helpers.table_to_json(out)
  snapshot_tick=game.tick
  snapshot_builds=snapshot_builds+1
  helpers.write_file(prefix .. name .. '.json', snapshot_json, false)
end
local function done()
  snapshot('final')
  write('done',{schema=1,tick=game.tick,snapshot_builds=snapshot_builds,
    snapshot_reuses=snapshot_reuses})
  game.tick_paused=true
  log('FACTORIO_INSPECT_DONE')
  script.on_event(defines.events.on_tick,nil)
end
local function selected(e)
  if not craft[e.type] then return false end
  local r=e.get_recipe()
  return r and (not cfg.recipe or r.name==cfg.recipe)
end
local function start_measurement()
  storage.start_tick=game.tick; storage.targets={}; storage.measurements={}
  for _,e in pairs(entities()) do
    if selected(e) then
      local id=key(e)
      storage.targets[id]=e
      storage.measurements[id]={id=id,name=e.name,position=e.position,
        recipe=e.get_recipe().name,before=e.products_finished,status_ticks={}}
    end
  end
  assert(next(storage.targets), 'No crafting machines match the measurement scope')
  snapshot('baseline')
  log('FACTORIO_INSPECT_MEASUREMENT_STARTED')
end
local function step()
  if snapshot_tick and snapshot_tick~=game.tick then
    snapshot_tick=nil; snapshot_json=nil
  end
  if fresh_run then
    storage.speed_before_inspection=game.speed
    storage.started=nil; storage.start_tick=nil
    storage.targets=nil; storage.measurements=nil
    fresh_run=false
  end
  if not storage.started then
    storage.started=game.tick
    game.speed=cfg.speed
    snapshot('initial')
    log('FACTORIO_INSPECT_INITIAL_READY')
    if cfg.measure_ticks==0 then done(); return end
  end
  if not storage.start_tick then
    if game.tick-storage.started>=cfg.warmup_ticks then start_measurement() end
    return
  end
  for id,e in pairs(storage.targets) do
    local v=storage.measurements[id]
    local s=e.valid and (status_names[e.status] or 'unknown') or 'destroyed'
    v.status_ticks[s]=(v.status_ticks[s] or 0)+1
    if e.valid then
      local recipe=e.get_recipe()
      if not recipe or recipe.name~=v.recipe then v.recipe_changed=true end
    end
  end
  if game.tick-storage.start_tick>=cfg.measure_ticks then
    local rows={}
    for id,e in pairs(storage.targets) do
      local v=storage.measurements[id]
      if e.valid then v.after=e.products_finished; v.delta=v.after-v.before end
      rows[#rows+1]=v
    end
    write('measurement',{schema=1,start_tick=storage.start_tick,end_tick=game.tick,
      elapsed_ticks=game.tick-storage.start_tick,machines=rows})
    done()
  end
end
script.on_event(defines.events.on_tick,function()
  local ok,err=pcall(step)
  if not ok then
    write('error',{message=tostring(err),tick=game.tick})
    game.tick_paused=true
    log('FACTORIO_INSPECT_ERROR: '..tostring(err))
    script.on_event(defines.events.on_tick,nil)
  end
end)
