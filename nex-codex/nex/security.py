from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import ipaddress
import time
from collections import defaultdict, deque


class DomainError(ValueError):
    pass


@dataclass(frozen=True)
class Actor:
    user_id: int
    guild_id: int
    roles: frozenset[int] = frozenset()
    administrator: bool = False
    owner: bool = False

    def require(self, config: dict, capability='staff'):
        key = 'payment_roles' if capability == 'payment' else 'staff_roles'
        if not (self.owner or self.administrator or self.roles.intersection(config.get(key, []))):
            raise DomainError('You do not have permission for this action.')

    def require_owner(self):
        if not self.owner:
            raise DomainError("Only a bot owner configured in OWNER_IDS may manage products, shops or settings.")

    def require_admin(self):
        if not (self.owner or self.administrator):
            raise DomainError('Administrator permission required.')


def safe_https(value: str, *, attachment=False):
    p = urlparse(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Use a public HTTPS URL without credentials.')
    if p.hostname.lower() in ('localhost',) or p.hostname.lower().endswith(('.local', '.localhost')):
        raise ValueError('Private URLs are not allowed.')
    try:
        ip = ipaddress.ip_address(p.hostname)
    except ValueError:
        ip = None
    if ip and not ip.is_global:
        raise ValueError('Private URLs are not allowed.')
    if attachment and p.hostname.lower() not in ('cdn.discordapp.com', 'media.discordapp.net'):
        raise ValueError('Upload the screenshot as a Discord attachment.')
    return value


def product_path(root: Path, relative: str):
    if not relative or Path(relative).is_absolute():
        raise DomainError('Invalid product file.')
    resolved = (root.resolve() / relative).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise DomainError('Product file is unavailable.')
    if resolved.suffix.lower() not in ('.zip', '.json', '.txt', '.pdf', '.tar', '.gz'):
        raise DomainError('Unsupported product file type.')
    return resolved


class RateLimiter:
    """Bounded process-local limiter; deploy one web worker or add a shared limiter."""
    def __init__(self):
        self.events = defaultdict(deque)

    def check(self, key, limit=10, seconds=60):
        current = time.monotonic()
        if len(self.events) > 10000:
            self.events = defaultdict(deque, {k: v for k, v in self.events.items() if v and v[-1] > current - 3600})
        queue = self.events[key]
        while queue and queue[0] <= current - seconds:
            queue.popleft()
        if len(queue) >= limit:
            raise DomainError('Too many requests. Please try again later.')
        queue.append(current)


def check_hierarchy(guild, moderator, target, bot_member):
    if target.id in (guild.owner_id, moderator.id, bot_member.id):
        raise DomainError('This member cannot be targeted.')
    if moderator.id != guild.owner_id and moderator.top_role <= target.top_role:
        raise DomainError('Your role must be above the target member.')
    if bot_member.top_role <= target.top_role:
        raise DomainError('Move the bot role above the target member.')
