"""Generate the small animated GraphRAG hero used in README.md."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT, FRAMES = 720, 260, 48
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "graphrag-hero.gif"


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def sphere_points(count=38):
    golden = math.pi * (3 - math.sqrt(5))
    points = []
    for index in range(count):
        y = 1 - 2 * (index + 0.5) / count
        radius = math.sqrt(1 - y * y)
        theta = golden * index
        points.append((math.cos(theta) * radius, y, math.sin(theta) * radius))
    return points


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nodes = sphere_points()
    links = []
    for index, point in enumerate(nodes):
        nearest = sorted(
            ((sum((point[k] - other[k]) ** 2 for k in range(3)), other_index)
             for other_index, other in enumerate(nodes) if other_index != index)
        )[:3]
        links.extend((min(index, other), max(index, other)) for _, other in nearest)
    links = sorted(set(links))
    frames = []
    for frame in range(FRAMES):
        image = Image.new("RGB", (WIDTH, HEIGHT))
        pixels = image.load()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                glow = max(0, 1 - math.sqrt(((x - 190) / 430) ** 2 + ((y - 120) / 280) ** 2))
                pixels[x, y] = (int(8 + 7 * glow), int(14 + 20 * glow), int(32 + 38 * glow))
        draw = ImageDraw.Draw(image, "RGBA")
        center_x, center_y, radius = 186, 130, 83
        angle = frame * 2 * math.pi / FRAMES
        projected = []
        for x, y, z in nodes:
            rx = x * math.cos(angle) + z * math.sin(angle)
            rz = -x * math.sin(angle) + z * math.cos(angle)
            perspective = 1 / (1.3 - rz * 0.28)
            projected.append((center_x + rx * radius * perspective, center_y + y * radius * perspective, rz))
        for first, second in links:
            x1, y1, z1 = projected[first]
            x2, y2, z2 = projected[second]
            alpha = int(28 + 108 * max(0, (z1 + z2 + 2) / 4))
            draw.line((x1, y1, x2, y2), fill=(41, 190, 255, alpha), width=1)
        for x, y, z in projected:
            size = 3.0 + max(0, z) * 2
            alpha = int(100 + (z + 1) * 75)
            draw.ellipse((x-size*2, y-size*2, x+size*2, y+size*2), fill=(15, 151, 255, alpha // 4))
            draw.ellipse((x-size/2, y-size/2, x+size/2, y+size/2), fill=(135, 231, 255, alpha))
        draw.ellipse((center_x-radius-7, center_y-radius-7, center_x+radius+7, center_y+radius+7), outline=(56, 154, 255, 55), width=1)
        draw.text((340, 76), "GraphRAG", font=font(42, True), fill=(242, 248, 255, 255))
        draw.text((343, 128), "YOUR KNOWLEDGE, CONNECTED", font=font(13, True), fill=(86, 202, 255, 255))
        draw.text((343, 164), "Ask across documents. Follow the evidence.", font=font(15), fill=(177, 194, 220, 255))
        draw.rounded_rectangle((343, 202, 510, 230), radius=14, fill=(16, 45, 73, 255), outline=(46, 136, 205, 170), width=1)
        draw.text((357, 208), "SEARCH  ·  GRAPH  ·  CITE", font=font(10, True), fill=(160, 225, 255, 255))
        frames.append(image.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    frames[0].save(OUTPUT, save_all=True, append_images=frames[1:], duration=75, loop=0, optimize=True)
    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
