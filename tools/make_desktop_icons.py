"""Generate the application's original monochrome waveform icon for installers."""
from pathlib import Path
from PIL import Image, ImageDraw

folder = Path(__file__).resolve().parents[1] / 'app' / 'assets'
folder.mkdir(exist_ok=True)
image = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((24, 24, 1000, 1000), radius=230, fill='#f7f7f5')
draw.ellipse((174, 174, 850, 850), fill='#111111')
for x, height in [(348, 120), (430, 250), (512, 390), (594, 230), (676, 140)]:
    draw.rounded_rectangle((x-15, 512-height//2, x+15, 512+height//2), radius=15, fill='white')
image.save(folder / 'icon.png')
image.save(folder / 'icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
image.save(folder / 'icon.icns')
