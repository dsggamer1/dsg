"""Optional Pillow build tool. The shipped PNGs require no runtime image library."""
from PIL import Image, ImageDraw
from render_help import ROOT, background, icon, font, ACCENTS

CARDS = {
    'help': ('home', 'logo', 'Your community, connected.', 'WELCOME TO NEX CODEX', 'HELP  /  SHOP  /  SUPPORT'),
    'shop': ('commerce', 'cart', 'Find your next beginning.', 'THE NEX CODEX COLLECTION', 'TEMPLATES  /  SOURCE CODE'),
    'product': ('commerce', 'product', 'Made for your next idea.', 'PRODUCT SPOTLIGHT', 'EXPLORE  /  CONFIRM  /  RECEIVE'),
    'ticket': ('home', 'ticket', 'A little help. A human touch.', 'PRIVATE SUPPORT', 'YOUR SPACE TO ASK'),
    'giveaway': ('community', 'gift', 'Something worth sharing.', 'COMMUNITY GIVEAWAY', 'ONE COMMUNITY  /  ONE MOMENT'),
    'welcome': ('utility', 'welcome', 'You belong here.', 'WELCOME TO THE COMMUNITY', 'MAKE YOURSELF AT HOME'),
    'leave': ('utility', 'leave', 'Until we meet again.', 'A COMMUNITY FAREWELL', 'THANKS FOR BEING HERE'),
    'broadcast': ('home', 'bell', 'Something to share.', 'COMMUNITY ANNOUNCEMENT', 'FROM YOUR SERVER TEAM'),
    'settings': ('utility', 'settings', 'Make it yours.', 'YOUR NEX CODEX WORKSPACE', 'SET UP  /  CREATE  /  CONNECT'),
}


def main():
    dest=ROOT/'nex/assets/cards';dest.mkdir(parents=True,exist_ok=True)
    for key,(palette,symbol,title,kicker,footer) in CARDS.items():
        im=background(palette).crop((0,0,900,230));d=ImageDraw.Draw(im);accent=ACCENTS[palette]
        d.rounded_rectangle((12,12,887,217),radius=25,outline=(43,70,91),width=1)
        d.line((40,12,860,12),fill=accent,width=2)
        for x in range(620,880,30):d.line((x,30,x,200),fill=(25,42,61))
        d.ellipse((728,43,862,177),outline=accent,width=1)
        im.alpha_composite(icon(symbol,108),(741,56))
        d.text((36,34),'NEX CODEX',font=font(15,True),fill=(224,244,255))
        d.text((36,70),kicker,font=font(11,True),fill=accent)
        d.text((33,94),title,font=font(32,True),fill=(232,246,255))
        d.rounded_rectangle((36,158,650,191),radius=10,fill=(17,37,53),outline=(35,68,86))
        d.text((50,168),footer,font=font(10,True),fill=(149,186,206))
        im.convert('RGB').save(dest/f'{key}.png',optimize=True)
        print(key,(dest/f'{key}.png').stat().st_size)


if __name__=='__main__':main()
