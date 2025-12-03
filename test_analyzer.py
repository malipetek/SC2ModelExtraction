from m3_analyzer import M3Analyzer
import os

m3_path = "VikingFighter.m3"
if os.path.exists(m3_path):
    print(f"Analyzing {m3_path}...")
    with open(m3_path, "rb") as f:
        data = f.read()
    
    analyzer = M3Analyzer()
    deps = analyzer.get_dependencies(data)
    print("Found dependencies:")
    for d in deps:
        print(d)
else:
    print(f"{m3_path} not found.")
