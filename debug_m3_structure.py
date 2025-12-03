import sys
import os

# Add the m3addon directory to sys.path
current_dir = os.getcwd()
m3addon_path = os.path.join(current_dir, "m3addon")
if m3addon_path not in sys.path:
    sys.path.append(m3addon_path)

try:
    import m3
except ImportError as e:
    print(f"Error importing m3: {e}")
    # Fallback: try adding root and importing as package
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    try:
        from m3addon import m3
    except ImportError as e2:
        print(f"Error importing m3addon.m3: {e2}")
        sys.exit(1)

def analyze_m3(filepath):
    print(f"Analyzing: {filepath}")
    try:
        model = m3.loadModel(filepath)
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    model_name = getattr(model, "modelName", "Unknown")
    if hasattr(model_name, "value"):
        model_name = model_name.value
    print(f"Model Name: {model_name}")
    
    # 1. Map AnimIDs to Data Types in STCs
    # Map: (SequenceName, STC_Index) -> {AnimId: DataType}
    seq_anim_map = {}
    
    print(f"\n--- Sequences ({len(model.sequences)}) ---")
    if hasattr(model, 'sts'):
        print(f"Total STS: {len(model.sts)}")
    for i, seq in enumerate(model.sequences):
        stg = model.sequenceTransformationGroups[i]
        print(f"Sequence {i}: {seq.name} (Duration: {seq.animEndInMS - seq.animStartInMS}ms)")
        
        for stc_idx in stg.stcIndices:
            stc = model.sequenceTransformationCollections[stc_idx]
            # Check what animIds this STC provides
            for j, animId in enumerate(stc.animIds):
                animRef = stc.animRefs[j]
                animType = animRef >> 16
                animIndex = animRef & 0xffff
                
                type_names = ["SDEV", "SD2V", "SD3V", "SD4Q", "SDCC", "SDR3", "Unk7", "SDS6", "SDU6", "Unk10", "SDU3", "SDFG", "SDMB"]
                type_name = type_names[animType] if 0 <= animType < len(type_names) else f"Unknown({animType})"
                
                key = (seq.name, stc_idx)
                if key not in seq_anim_map:
                    seq_anim_map[key] = {}
                seq_anim_map[key][animId] = type_name

    # Check for Orphan STCs (STCs not used in any Sequence)
    print(f"\n--- STC Analysis ---")
    total_stcs = len(model.sequenceTransformationCollections)
    used_stcs = set()
    for stg in model.sequenceTransformationGroups:
        for idx in stg.stcIndices:
            used_stcs.add(idx)
            
    print(f"Total STCs: {total_stcs}")
    print(f"Used STCs: {len(used_stcs)}")
    
    if len(used_stcs) < total_stcs:
        print("Found Orphan STCs:")
        for idx in range(total_stcs):
            if idx not in used_stcs:
                stc = model.sequenceTransformationCollections[idx]
                stc_name = getattr(stc, "name", "Unknown")
                if hasattr(stc_name, "value"): stc_name = stc_name.value
                print(f"  STC {idx}: {stc_name} (AnimIDs: {len(stc.animIds)})")

    # 2. Check Bones
    print(f"\n--- Bones ({len(model.bones)}) ---")
    
    # We need bone names. m3import uses a UniqueNameFinder but we can just use raw names
    # Note: Bone names are References to CHAR, so we need to dereference them if possible, 
    # or they might already be strings if m3.py handles it.
    # Looking at structures.xml, name is Ref to CHAR. m3.py usually resolves this to a string.
    
    animated_bones_count = 0
    for i, bone in enumerate(model.bones):
        bone_name = bone.name
        if hasattr(bone_name, "value"): # If it's a wrapper
            bone_name = bone_name.value
            
        loc_anim_id = bone.location.header.animId
        rot_anim_id = bone.rotation.header.animId
        sca_anim_id = bone.scale.header.animId
        
        # Check if this bone is animated in ANY sequence
        is_animated = False
        found_in_seqs = []
        
        # Check location
        if loc_anim_id != 0xFFFFFFFF: # Assuming -1/maxint is 'no animation'
             for (seq_name, _), anim_map in seq_anim_map.items():
                 if loc_anim_id in anim_map:
                     found_in_seqs.append(f"{seq_name}(Loc:{anim_map[loc_anim_id]})")
                     is_animated = True

        # Check rotation
        if rot_anim_id != 0xFFFFFFFF:
             for (seq_name, _), anim_map in seq_anim_map.items():
                 if rot_anim_id in anim_map:
                     found_in_seqs.append(f"{seq_name}(Rot:{anim_map[rot_anim_id]})")
                     is_animated = True

        # Check scale
        if sca_anim_id != 0xFFFFFFFF:
             for (seq_name, _), anim_map in seq_anim_map.items():
                 if sca_anim_id in anim_map:
                     found_in_seqs.append(f"{seq_name}(Sca:{anim_map[sca_anim_id]})")
                     is_animated = True
                     
        if is_animated:
            print(f"Bone {i}: {bone_name} - Animated in: {', '.join(found_in_seqs[:5])}...")
            animated_bones_count += 1
        else:
            # Check if it has animIds that are just not in the map
            missing = []
            if loc_anim_id != 0xFFFFFFFF: missing.append(f"Loc({loc_anim_id})")
            if rot_anim_id != 0xFFFFFFFF: missing.append(f"Rot({rot_anim_id})")
            if sca_anim_id != 0xFFFFFFFF: missing.append(f"Sca({sca_anim_id})")
            if missing:
                print(f"Bone {i}: {bone_name} - Has AnimIDs but NOT in sequences: {', '.join(missing)}")

    print(f"\nTotal Animated Bones: {animated_bones_count} / {len(model.bones)}")
    
    # 3. Dump Bone_ROOT01 Animation Data in Detail
    root_bone_idx = -1
    for i, bone in enumerate(model.bones):
        b_name = bone.name
        if hasattr(b_name, "value"): b_name = b_name.value
        if "ROOT" in b_name or "Bone_ROOT01" == b_name:
            root_bone_idx = i
            print(f"\n--- Detailed Analysis for {b_name} ---")
            
            loc_anim_id = bone.location.header.animId
            print(f"Location AnimID: {loc_anim_id}")
            
            # Find this AnimID in STCs
            for (seq_name, stc_idx), anim_map in seq_anim_map.items():
                if loc_anim_id in anim_map:
                    stc = model.sequenceTransformationCollections[stc_idx]
                    anim_type_name = anim_map[loc_anim_id]
                    print(f"  Found in {seq_name} (STC {stc_idx}) as {anim_type_name}")
                    
                    # Try to get values
                    # Need to find index in stc.animIds
                    try:
                        idx = list(stc.animIds).index(loc_anim_id)
                        animRef = stc.animRefs[idx]
                        animType = animRef >> 16
                        animIndex = animRef & 0xffff
                        
                        # Assuming type SD3V (2)
                        if animType == 2: # SD3V
                            data = stc.sd3v[animIndex]
                            print(f"    Frames: {len(data.frames)}")
                            print(f"    Values: {len(data.keys)}")
                            for t, v in zip(data.frames, data.keys):
                                print(f"      t={t}: ({v.x}, {v.y}, {v.z})")
                    except Exception as e:
                        print(f"    Error extracting data: {e}")
            break


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else "VikingFighter.m3"
    analyze_m3(filename)
