#!/usr/bin/env python3
"""
The picture examples/hello_board draws on the computer, as DGX_HOST_SHOT writes the window of DGX (a PPM): its top
eighth blue, the rest white. Usage: host_shot.py SHOT.ppm
"""
import sys

BLUE = (0, 0, 255)
WHITE = (255, 255, 255)
BAR_PART = 8  # hello_board fills the top 1/8 of the display with blue


def main():
    magic, size, depth, pixels = open(sys.argv[1], "rb").read().split(b"\n", 3)
    width, height = map(int, size.split())
    if magic != b"P6" or depth != b"255" or len(pixels) != width * height * 3:
        raise SystemExit(f"{sys.argv[1]}: not a PPM of {width}x{height} with 8 bits a color")
    wrong = 0
    for y in range(height):
        expected = bytes(BLUE if y < height // BAR_PART else WHITE) * width
        wrong += sum(pixels[(y * width + x) * 3:(y * width + x) * 3 + 3] != expected[x * 3:x * 3 + 3] for x in range(width))
    if wrong:
        raise SystemExit(f"{sys.argv[1]}: {wrong} of {width * height} pixels are not those hello_board draws")
    print(f"{sys.argv[1]}: {width}x{height}, the blue bar and the white field of hello_board")


if __name__ == "__main__":
    main()
