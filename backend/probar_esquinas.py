import sys
from PIL import Image, ImageDraw
from album import decode
from album.scanning import Scanner
from album.exceptions import DocumentNotFound
 
image = decode(open(sys.argv[1], "rb").read())
try:
    corners = Scanner().detect_corners(image)
    print("esquinas:", corners)
    debug = Image.fromarray(image)
    draw = ImageDraw.Draw(debug)
    draw.line([tuple(p) for p in corners] + [tuple(corners[0])], fill=(255, 0, 0), width=3)
    debug.save("debug_esquinas.png")
    print("Guardado debug_esquinas.png")
except DocumentNotFound as exc:
    print("No detecté la hoja:", exc)