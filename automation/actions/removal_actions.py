import time
from automation.automation_config import AutomationSettings
from automation.exceptions import FastApplyError
from . import group_actions, texture_actions


def process_removals_full(manager, slots_data):
    manager.vision.log("\n--- Phase 1: Processing removals for a Full Apply/First Run ---")
    all_groups = sorted(list({s['group'] for s in slots_data if s['group']}))
    ui_slots_by_group = {}
    
    for s in slots_data:
        if s['group']:
            if s['group'] not in ui_slots_by_group:
                ui_slots_by_group[s['group']] = []
            ui_slots_by_group[s['group']].append(s)
    
    for group_name in ui_slots_by_group:
        ui_slots_by_group[group_name].sort(key=lambda s: s['slot_id'])
    
    for group_name in all_groups:
        manager._check_for_stop()
        manager.vision.log(f"\nScanning group for removal: '{group_name}'")
        slots_in_group = ui_slots_by_group.get(group_name, [])
        group_header, group_arrow = group_actions.find_and_expand_group(manager, group_name, slots_in_group)
        
        if not group_header:
            manager.vision.log(f"  - Could not find group '{group_name}'. Assuming it's empty.")
            continue
        web_textures = group_actions.get_textures_in_group(manager, group_header, group_arrow)
        
        if not web_textures:
            manager.vision.log("  - Group is empty in web app. No removals needed.")
            continue
        ui_slots_for_group = ui_slots_by_group.get(group_name, [])
        indices_to_keep = {i for i, slot in enumerate(ui_slots_for_group) if slot['mode'] == 'Ignored'}
        manager.vision.log(f"  - UI specifies {len(ui_slots_for_group)} slots for this group.")
        manager.vision.log(f"  - Will keep textures at web app positions: {indices_to_keep or 'None'}")
        coords_to_remove = []
        
        for i, web_texture in enumerate(web_textures):
            if i not in indices_to_keep:
                manager.vision.log(f"  - Marking texture at position {i} for removal. {web_texture['texture_item_coords']}")
                coords_to_remove.append(web_texture['texture_item_coords'])
        
        if coords_to_remove:
            manager.vision.log(f"\nExecuting {len(coords_to_remove)} removals for group '{group_name}'")
            
            for coords in reversed(coords_to_remove):
                manager._check_for_stop()
                texture_actions.remove_texture(manager, coords)
                time.sleep(AutomationSettings.POST_REMOVAL_DELAY)
        else:
            manager.vision.log("  - No removals needed for this group based on 'Ignored' slots.")


def process_removals_fast(manager, slots_data, old_texture_map):
    manager.vision.log("\n--- Phase 1: Processing removals for a Fast Apply ---")
    
    if not old_texture_map:
        manager.vision.log("  - No previous texture map found. Cannot perform Fast Apply removals safely. Skipping removals.")
        raise FastApplyError("No previous texture map available for Fast Apply.")
    groups_to_process = sorted(list(old_texture_map.keys()))
    removed_slots_by_group = {}
    
    for group_name in groups_to_process:
        manager._check_for_stop()
        previous_slot_ids = old_texture_map.get(group_name, [])
        needs_scan = any(
            (slot_data := next((s for s in slots_data if s['slot_id'] == slot_id), None)) is None or
            slot_data.get('group') != group_name or
            (slot_data['mode'] == 'Managed' and slot_data.get('is_updated', False))
            for slot_id in previous_slot_ids
        )
        
        if not needs_scan:
            manager.vision.log(f"\nSkipping removal scan for group '{group_name}': No updated or moved-out slots found.")
            continue
        manager.vision.log(f"\nScanning group for removal: '{group_name}'")
        slots_for_group = [s for s in slots_data if s.get('group') == group_name]
        group_header, group_arrow = group_actions.find_and_expand_group(manager, group_name, slots_for_group)
        
        if not group_header:
            manager.vision.log(f"  - Warning: Could not find group '{group_name}'. Skipping.")
            continue
        web_textures = group_actions.get_textures_in_group(manager, group_header, group_arrow)
        web_textures_coords = [t['texture_item_coords'] for t in web_textures]
        previous_slot_order = old_texture_map.get(group_name, [])
        
        if len(web_textures_coords) != len(previous_slot_order):
            manager.vision.log(f"  - WARNING: Mismatch between expected textures ({len(previous_slot_order)}) and found textures ({len(web_textures_coords)}) in group '{group_name}'. The user may have manually changed textures. Aborting removal for this group to be safe.")
            continue
        coords_to_remove = []
        slots_to_remove_ids = []
        
        for i, slot_id in enumerate(previous_slot_order):
            slot_data = next((s for s in slots_data if s['slot_id'] == slot_id), None)
            
            if not slot_data or slot_data.get('group') != group_name or (slot_data['mode'] == 'Managed' and slot_data.get('is_updated', False)):
                log_reason = "no longer in group" if not slot_data or slot_data.get('group') != group_name else "is Managed and updated"
                manager.vision.log(f"  - Slot {slot_id+1} {log_reason}. Marking for removal.")
                coords_to_remove.append(web_textures_coords[i])
                slots_to_remove_ids.append(slot_id)
        
        if coords_to_remove:
            manager.vision.log(f"\nExecuting {len(coords_to_remove)} removals for group '{group_name}'")
            
            for coords in reversed(coords_to_remove):
                manager._check_for_stop()
                texture_actions.remove_texture(manager, coords)
                time.sleep(AutomationSettings.POST_REMOVAL_DELAY)
            removed_slots_by_group[group_name] = slots_to_remove_ids
    return removed_slots_by_group
