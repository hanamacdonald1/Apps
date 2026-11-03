from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((4, 4, 252, 252), radius=65, fill='#e8a6bb')
# Draw H geometrically so builds do not depend on system fonts.
draw.rectangle((74, 57, 97, 199), fill='#201b28')
draw.rectangle((159, 57, 182, 199), fill='#201b28')
draw.rectangle((90, 116, 166, 140), fill='#201b28')
image.save(Path(__file__).parent / 'HanaAI.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
