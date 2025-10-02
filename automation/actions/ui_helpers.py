import time
import numpy as np
from automation.automation_config import AutomationSettings
from automation.exceptions import UIVisibilityError


def find_image_with_cache(manager, template_name, cache_key, region=None, confidence=0.8):
    """
    Finds an image, prioritizing a cached region if available. If not found in cache,
    searches the wider region and updates the cache if found.
    """
    
    if cache_key in manager.ui_cache:
        cached_region = manager.ui_cache[cache_key]
        manager.vision.log(f"  - Searching for '{template_name}' in cached region: {cached_region}")
        location = manager.vision.find_image(template_name, region=cached_region, confidence=confidence)
        
        if location:
            return location
        manager.vision.log(f"  - Not found in cached region. Searching wider area.")
    manager.vision.log(f"  - Searching for '{template_name}' in wider region: {region or 'Full Screen'}")
    location = manager.vision.find_image(template_name, region=region, confidence=confidence)
    
    if location:
        cache_size = AutomationSettings.CACHE_REGION_SIZE
        new_cached_region = (
            int(location.x - cache_size / 2), int(location.y - cache_size / 2),
            cache_size, cache_size
        )
        manager.ui_cache[cache_key] = new_cached_region
        manager.vision.log(f"  - Found '{template_name}' and updated cache '{cache_key}' to {new_cached_region}")
    return location


def select_best_group_match(manager, matches):
    """
    Applies heuristics to a list of potential OCR matches to find the best one.
    """
    
    if not matches:
        return None
    predicted_x = None
    
    if manager.group_x_positions:
        predicted_x = np.median(manager.group_x_positions)
        manager.vision.log(f"  - Applying heuristics with predicted X-indentation: {predicted_x:.0f}")
    scored_matches = []
    
    for match in matches:
        final_score = match['score']
        bbox = match['bbox']
        
        if predicted_x is not None:
            x_diff = abs(bbox[0] - predicted_x)
            penalty = (x_diff / 50.0) * 0.1
            final_score -= penalty
            manager.vision.log(f"    - Candidate '{match['text']}' at x={bbox[0]}. X-diff penalty: {penalty:.2f}. New score: {final_score:.2f}")
        arrow_search_region = (int(bbox[0] + bbox[2]), int(bbox[1] - 5), 300, int(bbox[3] + 10))
        expanded_arrow = manager.vision.find_image('group_expanded.png', region=arrow_search_region, confidence=0.7)
        collapsed_arrow = manager.vision.find_image('group_collapsed.png', region=arrow_search_region, confidence=0.7)
        
        if expanded_arrow or collapsed_arrow:
            final_score += 0.5
            manager.vision.log(f"    - Candidate '{match['text']}' has an arrow nearby. Bonus applied. New score: {final_score:.2f}")
        
        if final_score > 0:
            scored_matches.append({'match': match, 'final_score': final_score})
    
    if not scored_matches:
        manager.vision.log("  - No candidates survived heuristic filtering.")
        return None
    sorted_matches = sorted(scored_matches, key=lambda x: x['final_score'], reverse=True)
    best_match_info = sorted_matches[0]
    
    if best_match_info['final_score'] < 0.7:
         manager.vision.log(f"  - Best candidate '{best_match_info['match']['text']}' has score {best_match_info['final_score']:.2f}, which is below threshold 0.7. Discarding.")
         return None
    manager.vision.log(f"  - Selected best group match '{best_match_info['match']['text']}' with final score {best_match_info['final_score']:.2f}")
    return best_match_info['match']


def wait_for_element(manager, template_name, timeout, start_time, cache_key=None, region=None, confidence=0.8):
    """
    Waits for a UI element to appear by repeatedly searching for it until a timeout is reached.
    Returns the element's coordinates or raises UIVisibilityError.
    """
    manager.vision.log(f"  - Waiting up to {timeout}s for '{template_name}' to appear...")
    
    while time.time() - start_time < timeout:
        manager._check_for_stop()
        
        if cache_key:
            location = find_image_with_cache(manager, template_name, cache_key, region=region, confidence=confidence)
        else:
            location = manager.vision.find_image(template_name, region=region, confidence=confidence)
        
        if location:
            manager.vision.log(f"  - Found '{template_name}' after {time.time() - start_time:.2f}s.")
            return location
        time.sleep(0.1)
    raise UIVisibilityError(f"Timed out after {timeout}s waiting for '{template_name}'.")
