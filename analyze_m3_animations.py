import sys
import os
sys.path.append(os.path.join(os.getcwd(), "m3addon"))

import m3

def analyze_m3(filepath):
    print(f"Analyzing {filepath}...")
    try:
        model = m3.loadModel(filepath)
    except Exception as e:
        print(f"Failed to load: {e}")
        return

    print(f"Model loaded.")
    print(f"  Model Name: {getattr(model, 'modelName', 'Unknown')}")
    print(f"  Flags: {hex(getattr(model, 'flags', 0))}")
    # Check if sequences is a list or Reference
    seqs = getattr(model, 'sequences', None)
    print(f"  Sequences field type: {type(seqs)}")
    if isinstance(seqs, list):
        print(f"  Sequences count: {len(seqs)}")
        for i, s in enumerate(seqs):
             print(f"    Seq {i}: {getattr(s, 'name', 'Unnamed')}")
    else:
        print(f"  Sequences content: {seqs}")

    stcs = getattr(model, 'sequenceTransformationCollections', [])
    type_counts = {}
    
    for stc in stcs:
        if not hasattr(stc, 'animRefs'):
            continue
            
        for ref in stc.animRefs:
            anim_type = ref >> 16
            type_counts[anim_type] = type_counts.get(anim_type, 0) + 1
            
    print("Animation Reference Types found:")
    type_names = {
        0: "SDEV (Events)",
        1: "SD2V (Vec2)",
        2: "SD3V (Vec3)",
        3: "SD4Q (Quat)",
        4: "SDCC (Color)",
        5: "SDR3 (Real)",
        6: "UnknownRef8",
        7: "SDS6 (Short6)",
        8: "SDU6 (UByte6)",
        9: "UnknownRef11",
        10: "SDU3 (UByte3)",
        11: "SDFG (Flags)",
        12: "SDMB (Bounds?)"
    }
    
    for t, count in sorted(type_counts.items()):
        name = type_names.get(t, f"Unknown({t})")
        print(f"  Type {t} ({name}): {count} occurrences")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "CommandCenter.m3"
    analyze_m3(target)
