import argparse
from pathlib import Path

from PIL import Image

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a WebP image to PNG")
    parser.add_argument("input", help="Input .webp file")
    parser.add_argument("-o", "--output", help="Output .png file (default: same name as input)")
    args = parser.parse_args()

    output = args.output or str(Path(args.input).with_suffix(".png"))
    Image.open(args.input).save(output, format="PNG")
    print(f"Created: {output}")
