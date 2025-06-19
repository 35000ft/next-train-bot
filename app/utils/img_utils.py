import base64
import mimetypes

from PIL import Image


def image_to_base64(image_path) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string


def crop_bottom_blank(image_path, save_path=None, bg_color=(255, 255, 255), tolerance=10):
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    pixels = img.load()

    def is_blank_row(y):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r == 0 and g == 0 and b == 0:
                return True
            if abs(r - bg_color[0]) > tolerance or abs(g - bg_color[1]) > tolerance or abs(b - bg_color[2]) > tolerance:
                return False
        return True

    crop_bottom = height
    for y in reversed(range(height)):
        if not is_blank_row(y):
            crop_bottom = y + 1
            break

    cropped = img.crop((0, 0, width, crop_bottom))

    if save_path:
        cropped.save(save_path)
    return cropped
