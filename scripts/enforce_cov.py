import sys, xml.etree.ElementTree as ET, pathlib
file = pathlib.Path(sys.argv[1])
threshold = float(sys.argv[2])
percent = float(ET.parse(file).getroot().attrib['line-rate']) * 100
print(f"total coverage: {percent:.1f}% (required {threshold}%)")
sys.exit(0 if percent >= threshold else 1)