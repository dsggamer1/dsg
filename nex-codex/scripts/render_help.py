"""Rebuild bundled UI artwork (optional build tool: Pillow; not needed to run the bot)."""
from pathlib import Path
import math
import ast
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'nex' / 'assets' / 'help'
ICONS = ROOT / 'nex' / 'assets' / 'emojis'
FONT_ROOT = Path('/usr/share/fonts/truetype/dejavu')
WIDTH, HEIGHT = 900, 820
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
  ('shield','Private orders','Personal support. Owner-released delivery.'),
  ('download','Protected delivery','Available to entitled customers.')]),
 'community': ('Make someone\'s day', 'A prize, a little anticipation, a moment to share.', [
  ('gift','Create a giveaway','Staff choose the prize & duration.'),
  ('user','Enter with a click','One saved entry per member.'),
  ('clock','Set the countdown','Scheduled draws survive restarts.'),
  ('award','Pick the winners','Random selection from saved entries.'),
  ('loading','Reroll','Staff can draw again after it ends.'),
  ('clipboard','Keep the history','Entries & outcomes stay recorded.')]),
}
PAGES['moderation'] = ('Moderation & roles', 'Clear controls. Accountable decisions.', [('ban','Kick & ban','Confirmation and role hierarchy.'),('warning','Warnings','Persistent cases and timestamps.'),('clock','Timeout','Minutes, or 0 to remove.'),('user','Give & take roles','Safe roles below your hierarchy.'),('leave','Rejoin restriction','Optional; owner/admin setup.'),('clipboard','Case history','Saved moderator and reason.')])
NAV = [('home','Home','logo'),('utility','Community','welcome'),('commerce','Shop & tickets','cart'),('community','Giveaways','gift'),('moderation','Moderation','shield')]


def font(size, bold=False):
 return ImageFont.truetype(str(FONT_ROOT / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)


def icon(name,size):
 with Image.open(ICONS / f'nex_{name}.png') as im:
  return im.convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)


FRAMES = 32
ACCENTS = {'home': (56, 207, 239), 'utility': (65, 219, 207), 'commerce': (95, 165, 255), 'community': (133, 166, 255), 'moderation': (94, 185, 235)}
HEROES = {
 'moderation': ('Keep it welcoming.', 'Keep it fair.', 'Moderation, roles and opt-in rejoin controls.'),
 'home': ('A better place', 'to belong.', 'Your community. Your collection. Your NEX CODEX.'),
 'utility': ('Make every', 'hello count.', 'Welcome people in. Share what matters.'),
 'commerce': ('Your next idea', 'starts here.', 'Templates. Source code. A place to start building.'),
 'community': ('A little surprise.', 'A shared moment.', 'Give your community something to look forward to.'),
}


def background(key):
 small = Image.new('RGB', (225, 165)); pixels = small.load()
 accent = ACCENTS[key]
 for y in range(165):
  for x in range(225):
   light = math.exp(-(((x-193)/76)**2 + ((y-40)/67)**2))
   indigo = math.exp(-(((x-3)/138)**2 + ((y-150)/78)**2))
   pixels[x,y] = (int(6+accent[0]*.08*light+8*indigo), int(11+accent[1]*.12*light+7*indigo), int(24+accent[2]*.15*light+25*indigo))
 return small.resize((WIDTH,HEIGHT),Image.Resampling.BICUBIC).convert('RGBA')


def render(key,index):
 phase=index/FRAMES*math.tau
 accent=ACCENTS[key]
 im=background(key)
 glow=Image.new('RGBA',im.size); gd=ImageDraw.Draw(glow)
 radius=100+math.sin(phase)*4
 gd.ellipse((733-radius,177-radius,733+radius,177+radius),fill=(*accent,48))
 glow=glow.filter(ImageFilter.GaussianBlur(44))
 im=Image.alpha_composite(im,glow); d=ImageDraw.Draw(im)
 # Fine grid, recessed border and a floating brand header.
 for x in range(40,880,40): d.line((x,90,x,550),fill=(20,31,48))
 for y in range(110,550,40): d.line((28,y,872,y),fill=(20,31,48))
 d.rounded_rectangle((16,16,883,803),radius=28,outline=(43,70,91),width=1)
 d.line((43,16,857,16),fill=(*accent,180),width=1)
 im.alpha_composite(icon('logo',40),(35,31))
 d.text((87,35),'NEX CODEX',font=font(23,True),fill=(222,244,255))
 d.text((89,64),'YOUR COMMUNITY, CONNECTED',font=font(9,True),fill=(122,165,191))
 d.rounded_rectangle((746,36,859,70),radius=16,fill=(15,33,52),outline=(49,85,108))
 d.text((773,43),f'{list(PAGES).index(key)+1:02} / 05',font=font(15,True),fill=accent)
 # Hero: intentionally generous text sizes; live command text sits outside the GIF.
 line1,line2,subtitle=HEROES[key]
 d.text((38,102),'THE NEX CODEX COMMAND CENTER',font=font(11,True),fill=accent)
 d.text((35,122),line1,font=font(45,True),fill=(235,248,255))
 d.text((35,174),line2,font=font(45,True),fill=accent)
 d.text((39,237),subtitle,font=font(15),fill=(154,185,208))
 # Orbital emblem and traveling pinpoints form a seamless, non-flashing loop.
 d.ellipse((662,106,804,248),outline=(42,88,115),width=1)
 d.ellipse((650,94,816,260),outline=(25,56,80),width=1)
 d.arc((656,100,810,254),int(index/FRAMES*360),int(index/FRAMES*360)+72,fill=accent,width=3)
 for offset in (0, math.pi):
  px=733+83*math.cos(phase+offset); py=177+83*math.sin(phase+offset)
  d.ellipse((px-3,py-3,px+3,py+3),fill=accent)
 im.alpha_composite(icon('logo',94),(686,130))
 d=ImageDraw.Draw(im)
 # A warm highlight gently passes over the cards; no rapid card switching.
 for n,(glyph,label,description) in enumerate(PAGES[key][2]):
  x,y=35+(n%2)*420,282+(n//2)*86
  pulse=(1+math.cos(phase-n*.8))/2
  border=tuple(int(a+(b-a)*pulse*.42) for a,b in zip((36,64,87),accent))
  d.rounded_rectangle((x,y,x+410,y+74),radius=17,fill=(16,32,51),outline=border,width=1)
  d.line((x+19,y+1,x+389,y+1),fill=(43,69,91))
  d.rounded_rectangle((x+12,y+13,x+60,y+61),radius=14,fill=(11,25,42))
  im.alpha_composite(icon(glyph,44),(x+14,y+15)); d=ImageDraw.Draw(im)
  d.text((x+76,y+11),label,font=font(20,True),fill=(215,239,251))
  d.text((x+76,y+43),description,font=font(13),fill=(149,179,202))
 # Quiet drifting particles use closed paths, so the last frame loops cleanly.
 for n in range(12):
  px=38+(n*137)%820+3*math.sin(phase+n)
  py=92+(n*67)%470+3*math.cos(phase+n)
  d.ellipse((px,py,px+1,py+1),fill=(75,130,159))
 # Command labels come from the actual registered command definitions.
 files={'home':['utility','commerce','community','moderation'],'utility':['utility'],'commerce':['commerce'],'community':['community'],'moderation':['moderation']}[key]
 labels=[]
 for module in files:
  tree=ast.parse((ROOT/'nex/cogs'/f'{module}.py').read_text())
  for node in ast.walk(tree):
   if not isinstance(node,ast.AsyncFunctionDef):continue
   for deco in node.decorator_list:
    if isinstance(deco,ast.Call) and isinstance(deco.func,ast.Attribute) and deco.func.attr=='hybrid_command':
     extras=next((ast.literal_eval(kw.value) for kw in deco.keywords if kw.arg=='extras'),{})
     if extras.get('owner_only') or extras.get('admin_only'):continue
     name=next((kw.value.value for kw in deco.keywords if kw.arg=='name'),node.name)
     labels.append('/'+name)
 labels=sorted(labels)
 d.text((38,548),'COMMAND INDEX  /  Setup commands appear below for authorized users',font=font(11,True),fill=accent)
 columns=4 if key=='home' else 3
 for n,label in enumerate(labels):
  x=40+(n%columns)*(820//columns);y=574+(n//columns)*15
  d.text((x,y),label,font=font(13,True),fill=(176,209,229))
 d.rounded_rectangle((35,748,864,795),radius=16,fill=(10,24,40),outline=(36,63,85))
 for n,(target,label,glyph) in enumerate(NAV):
  x=43+n*164
  selected=target==key
  if selected:d.rounded_rectangle((x,755,x+158,788),radius=11,fill=(21,52,74),outline=accent)
  im.alpha_composite(icon(glyph,23),(x+5,760));d=ImageDraw.Draw(im)
  d.text((x+34,763),label,font=font(11,True),fill=(187,231,250) if selected else (116,150,177))
 return im.convert('RGB')


def main():
 DEST.mkdir(parents=True,exist_ok=True)
 for key in PAGES:
  frames=[render(key,i) for i in range(FRAMES)]
  # Build a shared palette from several phases to keep typography stable.
  sample=Image.new('RGB',(WIDTH*4,HEIGHT))
  for n,i in enumerate((0,8,16,24)): sample.paste(frames[i],(n*WIDTH,0))
  palette=sample.quantize(colors=256)
  indexed=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
  path=DEST/f'{key}.gif'
  indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=100,loop=0,optimize=True,disposal=1)
  assert path.stat().st_size < 4*1024*1024
  print(key,path.stat().st_size,'bytes')


if __name__=='__main__':
 main()
