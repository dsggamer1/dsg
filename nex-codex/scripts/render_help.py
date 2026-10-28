"""Rebuild bundled UI artwork (optional build tool: Pillow; not needed to run the bot)."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'nex' / 'assets' / 'help'
ICONS = ROOT / 'nex' / 'assets' / 'emojis'
FONT_ROOT = Path('/usr/share/fonts/truetype/dejavu')
WIDTH, HEIGHT = 900, 660
PAGES = {
 'home': ('Command center', 'A little more connection. A lot more possibility.', [
  ('welcome','Welcome & leave','A warm hello. A thoughtful goodbye.'),
  ('ticket','Private tickets','Support that stays personal.'),
  ('gift','Giveaways','Something worth coming together for.'),
  ('bell','Announcements','Your voice, beautifully delivered.'),
  ('product','Templates & code','Your next great server starts here.'),
  ('settings','Server setup','Owner & administrator controls.')]),
 'utility': ('Make yourself at home', 'Welcome people in. Keep your community in the loop.', [
  ('welcome','Welcome messages','Channels, templates & live previews.'),
  ('leave','Leave messages','A farewell in your server style.'),
  ('support','Say','Clean messages. Mentions suppressed.'),
  ('bell','Broadcast','Branded announcements, sent by staff.'),
  ('settings','Configuration','Saved settings. Owner / admin access.'),
  ('info','Connection check','Prefixes, commands & permissions.')]),
 'commerce': ('Open your collection', 'From first look to private delivery, all in one place.', [
  ('browser','Server templates','Find a new home for your community.'),
  ('code','Bot source code','Start building your next idea.'),
  ('cart','Shop & checkout','Browse, confirm & track your order.'),
  ('ticket','Private tickets','Support with your order attached.'),
  ('rupee','Manual QR / UPI','A real person verifies each payment.'),
  ('download','Protected delivery','Available to entitled customers.')]),
 'community': ('Make someone\'s day', 'A prize, a little anticipation, a moment to share.', [
  ('gift','Create a giveaway','Staff choose the prize & duration.'),
  ('user','Enter with a click','One saved entry per member.'),
  ('clock','Set the countdown','Scheduled draws survive restarts.'),
  ('award','Pick the winners','Random selection from saved entries.'),
  ('loading','Reroll','Staff can draw again after it ends.'),
  ('clipboard','Keep the history','Entries & outcomes stay recorded.')]),
}
NAV = [('home','Home','logo'),('utility','Community','welcome'),('commerce','Shop & tickets','cart'),('community','Giveaways','gift')]


def font(size, bold=False):
 return ImageFont.truetype(str(FONT_ROOT / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)


def icon(name,size):
 with Image.open(ICONS / f'nex_{name}.png') as im:
  return im.convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)


def background():
 # Low-resolution radial lighting, upscaled to keep the optional build lightweight.
 small=Image.new('RGB',(225,165)); p=small.load()
 for y in range(165):
  for x in range(225):
   cyan=math.exp(-(((x-220)/120)**2+((y-12)/75)**2))
   blue=math.exp(-(((x-10)/150)**2+((y-145)/90)**2))
   p[x,y]=(int(8+3*cyan+8*blue),int(13+30*cyan+8*blue),int(27+37*cyan+40*blue))
 return small.resize((WIDTH,HEIGHT),Image.Resampling.BICUBIC).convert('RGBA')


def render(key,index):
 t=index/16*math.tau
 im=background(); d=ImageDraw.Draw(im)
 d.rounded_rectangle((18,18,881,641),radius=30,outline=(44,78,105),width=1)
 im.alpha_composite(icon('logo',40),(40,37))
 d.text((94,42),'NEX CODEX',font=font(21,True),fill=(190,235,249))
 d.rounded_rectangle((729,42,857,73),radius=15,fill=(17,43,63),outline=(43,100,125))
 d.ellipse((744,54,751,61),fill=(62,211,228))
 d.text((773,47),f'{list(PAGES).index(key)+1:02} / 04',font=font(15,True),fill=(124,226,239))
 title,subtitle,cards=PAGES[key]
 d.text((40,98),title,font=font(42,True),fill=(226,247,255))
 d.text((42,158),subtitle,font=font(17),fill=(152,184,207))
 d.line((42,199,857,199),fill=(37,68,91))
 for n,(glyph,label,description) in enumerate(cards):
  x,y=40+(n%2)*420,223+(n//2)*92
  active=n==int(index/16*6)
  d.rounded_rectangle((x,y,x+400,y+78),radius=18,fill=(20,39,59),outline=(50,147,178) if active else (39,64,87),width=2 if active else 1)
  im.alpha_composite(icon(glyph,48),(x+13,y+15))
  d.text((x+76,y+13),label,font=font(19,True),fill=(212,239,249))
  d.text((x+76,y+43),description,font=font(13),fill=(148,178,199))
 # Restrained moving light particles: no flashing or copied third-party artwork.
 overlay=Image.new('RGBA',im.size); od=ImageDraw.Draw(overlay)
 for n in range(15):
  x=32+(n*157+index*1.4)%832
  y=28+(n*83)%592
  alpha=int(45+35*(math.sin(t+n)+1)/2)
  od.ellipse((x,y,x+2,y+2),fill=(103,218,251,alpha))
 im=Image.alpha_composite(im,overlay)
 d=ImageDraw.Draw(im)
 d.rounded_rectangle((40,512,859,550),radius=12,fill=(15,35,53),outline=(34,65,86))
 d.line((55,524,55,537),fill=(56,207,239),width=3)
 d.text((69,522),'Choose a category in the dropdown below to explore commands.',font=font(14),fill=(173,205,225))
 d.rounded_rectangle((40,570,859,626),radius=18,fill=(12,28,45),outline=(37,68,91))
 for n,(target,label,glyph) in enumerate(NAV):
  x=53+n*200
  selected=target==key
  if selected:d.rounded_rectangle((x,578,x+190,618),radius=12,fill=(25,66,90),outline=(51,163,198))
  im.alpha_composite(icon(glyph,28),(x+10,584))
  d=ImageDraw.Draw(im)
  d.text((x+48,588),label,font=font(14,True),fill=(168,234,249) if selected else (127,157,182))
 return im.convert('RGB')


def main():
 DEST.mkdir(parents=True,exist_ok=True)
 for key in PAGES:
  frames=[render(key,i) for i in range(16)]
  # One shared palette prevents shimmer in text and static UI elements.
  palette=frames[0].quantize(colors=128)
  indexed=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
  path=DEST/f'{key}.gif'
  indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=150,loop=0,optimize=True,disposal=1)
  assert path.stat().st_size < 4*1024*1024
  print(key,path.stat().st_size,'bytes')


if __name__=='__main__':
 main()
