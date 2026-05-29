import argparse
import struct
from pathlib import Path

from PIL import Image


def image_to_cur(
    input_path: str,
    output_path: str | None = None,
    size: int = 48,
    hotspot_x: int | None = None,
    hotspot_y: int | None = None,
):
    img = Image.open(input_path).convert("RGBA")
    img = img.resize((size, size), Image.LANCZOS)

    if hotspot_x is None:
        hotspot_x = 0
    if hotspot_y is None:
        hotspot_y = 0

    hotspot_x = max(0, min(hotspot_x, size - 1))
    hotspot_y = max(0, min(hotspot_y, size - 1))

    # Build BMP/DIB image data (BITMAPINFOHEADER + pixel data + AND mask)
    pixels = img.load()

    # XOR mask: BGRA pixel rows, bottom-to-top
    xor_data = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            r, g, b, a = pixels[x, y]
            xor_data += struct.pack("BBBB", b, g, r, a)

    # AND mask: 1-bit per pixel, bottom-to-top, rows padded to 4 bytes
    row_bytes = (size + 31) // 32 * 4
    and_data = bytearray()
    for y in range(size - 1, -1, -1):
        row = bytearray(row_bytes)
        for x in range(size):
            _, _, _, a = pixels[x, y]
            if a < 128:
                row[x // 8] |= 0x80 >> (x % 8)
        and_data += row

    # BITMAPINFOHEADER (40 bytes)
    bih = struct.pack(
        "<IiiHHIIiiII",
        40,             # header size
        size,           # width
        size * 2,       # height (doubled: XOR + AND)
        1,              # color planes
        32,             # bits per pixel
        0,              # compression (BI_RGB)
        len(xor_data) + len(and_data),  # image size
        0,              # x pixels per meter
        0,              # y pixels per meter
        0,              # colors used
        0,              # important colors
    )

    image_data = bih + xor_data + and_data

    # Build .cur file
    header_size = 6
    entry_size = 16
    data_offset = header_size + entry_size

    cur_data = bytearray()

    # ICONDIR header
    cur_data += struct.pack("<HHH", 0, 2, 1)

    # ICONDIRENTRY
    w = size if size < 256 else 0
    h = size if size < 256 else 0
    cur_data += struct.pack(
        "<BBBBHHII",
        w,
        h,
        0,
        0,
        hotspot_x,
        hotspot_y,
        len(image_data),
        data_offset,
    )

    cur_data += image_data

    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".cur"))

    Path(output_path).write_bytes(cur_data)
    print(f"Created: {output_path}")
    print(f"  Size: {size}x{size}, Hotspot: ({hotspot_x}, {hotspot_y})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert an image to a .cur cursor file")
    parser.add_argument("input", help="Input image file (PNG, JPG, etc.)")
    parser.add_argument("-o", "--output", help="Output .cur file (default: same name as input)")
    parser.add_argument("-s", "--size", type=int, default=64, help="Cursor size in pixels (default: 48)")
    parser.add_argument("-x", "--hotspot-x", type=int, default=0, help="Hotspot X position (default: 0)")
    parser.add_argument("-y", "--hotspot-y", type=int, default=0, help="Hotspot Y position (default: 0)")
    args = parser.parse_args()

    image_to_cur(args.input, args.output, args.size, args.hotspot_x, args.hotspot_y)
