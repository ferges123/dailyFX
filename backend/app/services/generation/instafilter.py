from io import BytesIO
import random

from PIL import Image
import pilgram

AVAILABLE_FILTERS = [
    "_1977", "aden", "brannan", "brooklyn", "clarendon", "earlybird", "gingham",
    "hudson", "inkwell", "kelvin", "lark", "lofi", "maven", "mayfair", "moon",
    "nashville", "perpetua", "reyes", "rise", "slumber", "stinson", "toaster",
    "valencia", "walden", "willow", "xpro2"
]

AVAILABLE_FILTER_OPTIONS = [{"label": value, "value": value} for value in ["random", *AVAILABLE_FILTERS]]

def apply_instafilter(image_bytes: bytes, filter_name: str = "random") -> tuple[bytes, str]:
    """
    Applies an Instagram-like filter to the given image bytes using the pilgram library.
    If filter_name is 'random', a random filter from the available list is chosen.
    Returns (filtered_bytes, actual_filter_name).
    """
    if filter_name == "random":
        filter_name = random.choice(AVAILABLE_FILTERS)
        
    if filter_name.startswith("_"):
        filter_func = getattr(pilgram, filter_name, None)
    else:
        filter_func = getattr(pilgram, filter_name.lower(), None)
        
    if filter_func is None:
        raise ValueError(f"Filter '{filter_name}' is not supported by pilgram.")

    from PIL import ImageOps
    img = Image.open(BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img) or img
    img = img.convert("RGB")
    
    # Downscale to max 3840px to prevent huge CPU execution times and file sizes
    if max(img.size) > 3840:
        img.thumbnail((3840, 3840), Image.Resampling.LANCZOS)
        
    filtered_img = filter_func(img)
    
    out_io = BytesIO()
    filtered_img.save(out_io, format="PNG")
    return out_io.getvalue(), filter_name
