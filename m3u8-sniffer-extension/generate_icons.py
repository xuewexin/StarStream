"""生成 16/48/128 尺寸的简单 PNG 图标"""
import struct
import zlib
import os

def create_png(width, height, filepath):
    """创建一个纯色 PNG，中心带白色三角播放符号"""
    # RGBA 像素数据
    pixels = []
    for y in range(height):
        row = []
        for x in range(width):
            # 深蓝紫色背景
            r, g, b, a = 0x4A, 0x3A, 0xD5, 0xFF
            # 中心白色三角形 (play button)
            cx, cy = width * 0.48, height * 0.5
            tri_size = min(width, height) * 0.28
            dx, dy = x - cx, y - cy
            # 三角形判定 (指向右侧的播放三角)
            if abs(dy) < tri_size and dx > -tri_size * 0.3 and dx < tri_size * 0.7:
                if abs(dy) < tri_size * (1 - (dx + tri_size * 0.3) / (tri_size)):
                    r, g, b = 0xFF, 0xFF, 0xFF
            row.extend([r, g, b, a])
        pixels.append(bytes([0] + row))  # PNG filter byte

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', zlib.crc32(chunk) & 0xFFFFFFFF)

    raw = b''.join(pixels)
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA

    png = b'\x89PNG\r\n\x1a\n'
    png += make_chunk(b'IHDR', ihdr)
    png += make_chunk(b'IDAT', zlib.compress(raw))
    png += make_chunk(b'IEND', b'')

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(png)

icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
for size in [16, 48, 128]:
    create_png(size, size, os.path.join(icons_dir, f'icon{size}.png'))
    print(f"Created icon{size}.png ({size}x{size})")
