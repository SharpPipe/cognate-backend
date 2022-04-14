import random
import colorsys


def random_colour(with_alpha=False):
    # Generate random HSV colour, ranges given by Mart
    h = random.random()
    s = 0.6 + random.random() * 0.15
    v = 0.7 + random.random() * 0.1
    rgb = colorsys.hsv_to_rgb(h, s, v)
    hex_value = '%02x%02x%02x' % (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
    if with_alpha:
        hex_value += "".join([random.choice("0123456789abcdef") for _ in range(2)])
    return hex_value
