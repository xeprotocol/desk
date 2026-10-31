"""The XE mark, once. The header and footer draw it as inline SVG; the social cards raster it with Pillow.

Keeping the path here means the two can never drift. The SVG path is absolute-coordinate M/L/H/V/C/Z only,
which is all the small flattener in og.py understands; if the mark is ever redrawn with other commands,
extend the flattener or the cards will come out wrong.
"""

MARK_VIEWBOX = (30.001, 32.0)

MARK_PATH = (
    "M14.3896 10.3809C16.3506 12.3011 18.9859 13.3769 21.7305 13.377H30V18.623H21.7305"
    "C18.9859 18.6231 16.3506 19.6989 14.3896 21.6191L3.78809 32H0V28.29L8.72266 19.748"
    "C10.8236 17.6907 10.8236 14.3093 8.72266 12.252L0 3.70996V0H3.78809L14.3896 10.3809Z"
    "M30.001 31.9961H16.3398V30.2471C16.3401 28.3157 17.9064 26.75 19.8379 26.75H30.001V31.9961Z"
    "M30.001 0V5.24609H19.8379C17.9064 5.24609 16.34 3.68051 16.3398 1.74902V0H30.001Z"
)

# Colours shared with site.css (dark theme). Kept as tuples for Pillow.
BG = (10, 10, 10)
PANEL = (23, 23, 23)
TEXT_HIGH = (255, 255, 255)
TEXT_MEDIUM = (207, 207, 207)
TEXT_LOW = (152, 152, 152)
STROKE_STRONG = (58, 58, 58)
BRAND = (255, 105, 0)
BRAND_FILL = (196, 79, 0)
NEGATIVE = (255, 90, 79)
LIVE = (14, 204, 95)
