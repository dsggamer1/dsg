from collections import defaultdict, deque
import time
import re
from urllib.parse import urlparse


class Automod:
    def __init__(self):
        self.history = defaultdict(lambda: deque(maxlen=30))

    def inspect(self, guild_id, user_id, content, mentions, cfg):
        clock = time.monotonic()
        if len(self.history) > 10000:
            self.history = defaultdict(lambda: deque(maxlen=30), {k: v for k, v in self.history.items() if v and clock-v[-1][0] < 300})
        history = self.history[(guild_id, user_id)]
        history.append((clock, content.casefold()))
        recent = [text for stamp, text in history if clock-stamp < cfg['spam_window']]
        flags = []
        if len(recent) >= cfg['spam_count']:
            flags.append('message burst')
        if content.strip() and sum(text == content.casefold() for text in recent) >= 3:
            flags.append('repeated messages')
        if mentions >= cfg['mention_limit']:
            flags.append('mention spam')
        if cfg['block_invites'] and re.search(r'(?:discord\.gg/|discord(?:app)?\.com/invite/)', content, re.I):
            flags.append('invite link')
        letters = [c for c in content if c.isalpha()]
        if len(letters) >= 20 and sum(c.isupper() for c in letters)/len(letters)*100 >= cfg['caps_percent']:
            flags.append('excessive capitals')
        for raw in re.findall(r'https?://[^\s<>]+', content):
            try:
                host = (urlparse(raw).hostname or '').lower()
            except ValueError:
                continue  # Malformed user text must not break the event listener.
            if any(host == domain or host.endswith('.'+domain) for domain in cfg['blocked_domains']):
                flags.append('blocked domain')
                break
        return flags
