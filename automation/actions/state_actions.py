def compute_new_texture_map_from_ui(manager, slots_data):
    new_map = {}
    slots_by_group = {}
    
    for s in slots_data:
        if s['group'] and s['mode'] in ['Managed', 'Ignored']:
            if s['group'] not in slots_by_group:
                slots_by_group[s['group']] = []
            slots_by_group[s['group']].append(s)
    
    for group_name, slots in slots_by_group.items():
        sorted_slots = sorted(slots, key=lambda x: x['slot_id'])
        new_map[group_name] = [s['slot_id'] for s in sorted_slots]
    manager.vision.log(f"Computed new texture map from UI state: {new_map}")
    return new_map


def compute_new_texture_map_from_ops(manager, old_map, removed_by_group, uploaded_by_group):
    new_map = {}
    all_groups = set(old_map.keys()) | set(uploaded_by_group.keys())
    
    for group_name in all_groups:
        old_order = old_map.get(group_name, [])
        removed_slots = set(removed_by_group.get(group_name, []))
        uploaded_slots = uploaded_by_group.get(group_name, [])
        survivors = [slot_id for slot_id in old_order if slot_id not in removed_slots]
        new_order = survivors + uploaded_slots
        
        if new_order:
            new_map[group_name] = new_order
    manager.vision.log(f"Computed new texture map from operations: {new_map}")
    return new_map
