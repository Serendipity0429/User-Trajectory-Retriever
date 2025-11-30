import random


def random_color_func(*args, **kwargs):
    """
    Returns a random color for each letter in the captcha.
    """
    # Using a range that avoids too light colors (so they are visible on white background)
    # Lowered the max value to 128 to ensure better contrast
    return "#%02X%02X%02X" % (
        random.randint(0, 128),
        random.randint(0, 128),
        random.randint(0, 128),
    )
