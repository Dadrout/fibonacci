"""Render ECON 301 slide 7 and photograph it badly (projector, angle, blur, noise)."""
import random
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

random.seed(7)
FONT = "/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf"
def font(size, bold=False):
    for path in (FONT, "/usr/share/fonts/google-noto/NotoSans-Regular.ttf", "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"):
        try:
            f = ImageFont.truetype(path, size)
            if bold:
                try: f.set_variation_by_name("Bold")
                except Exception: pass
            return f
        except OSError:
            continue
    return ImageFont.load_default()

W, H = 1600, 900
slide = Image.new("RGB", (W, H), "#ffffff")
d = ImageDraw.Draw(slide)
d.rectangle([0, 0, W, 120], fill="#1f3a68")
d.text((60, 30), "Heteroskedasticity", fill="white", font=font(60, True))
d.text((W - 360, 52), "ECON 301 · Week 6", fill="#dfe7f5", font=font(30))
bullets = [
    ("Homoskedasticity (MLR.5):  Var(uᵢ | xᵢ) = σ²", 0),
    ("Heteroskedasticity:  Var(uᵢ | xᵢ) = σᵢ²  — error variance changes with x", 0),
    ("OLS estimates are still unbiased and consistent", 0),
    ("BUT the usual standard errors are biased", 0),
    ("so t-tests, F-tests and confidence intervals are invalid", 1),
    ("Detect: residual plot, Breusch–Pagan test, White test", 0),
    ("Fix: heteroskedasticity-robust (White) standard errors, or WLS", 0),
]
y = 180
for text, level in bullets:
    x = 90 + level * 60
    d.ellipse([x, y + 22, x + 14, y + 36], fill="#1f3a68")
    d.text((x + 34, y), text, fill="#111111", font=font(40 if level == 0 else 36))
    y += 92
d.text((W - 80, H - 70), "7", fill="#555555", font=font(36))

# The photo: dark lecture hall, projected slide with keystone, camera tilt, blur, glare, noise.
photo = Image.new("RGB", (2000, 1500), "#26221f")
screen = slide.resize((1500, 844))
screen = screen.transform((1500, 844), Image.QUAD, (30, 0, 0, 844, 1500, 844, 1470, 0), Image.BICUBIC)
glare = Image.new("L", screen.size, 0)
ImageDraw.Draw(glare).ellipse([900, -200, 1700, 500], fill=70)
screen = Image.composite(Image.new("RGB", screen.size, "#ffffff"), screen, glare.filter(ImageFilter.GaussianBlur(120)))
photo.paste(screen, (250, 300))
photo = photo.rotate(-4.5, resample=Image.BICUBIC, fillcolor="#26221f")
photo = photo.filter(ImageFilter.GaussianBlur(2.6))
pixels = photo.load()
for _ in range(260000):
    x, y = random.randrange(2000), random.randrange(1500)
    r, g, b = pixels[x, y]
    n = random.randint(-28, 28)
    pixels[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
photo = photo.resize((1600, 1200))
photo.save(sys.argv[1], "JPEG", quality=72)
print("saved", sys.argv[1])
