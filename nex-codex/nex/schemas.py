from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .security import safe_https


class ProductInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default='', max_length=4000)
    category: Literal['template', 'bot']
    price: int = Field(default=0, ge=0, le=100000000)
    currency: str = Field(default='INR', pattern=r'^[A-Z]{3}$')
    thumbnail: str = Field(default='', max_length=2000)
    terms: str = Field(default='', max_length=4000)
    published: bool = False
    archived: bool = False
    available: bool = True
    delivery_kind: Literal['instructions', 'link', 'file'] = 'instructions'
    delivery_value: str = Field(default='', max_length=4000)
    claim_limit: int = Field(default=10, ge=1, le=1000)
    cooldown_seconds: int = Field(default=86400, ge=0, le=31536000)

    @model_validator(mode='after')
    def delivery(self):
        if self.thumbnail:
            safe_https(self.thumbnail)
        if self.delivery_kind == 'link':
            safe_https(self.delivery_value)
        if self.delivery_kind == 'file':
            from pathlib import PurePosixPath
            p = PurePosixPath(self.delivery_value)
            if p.is_absolute() or '..' in p.parts or '\\' in self.delivery_value or not self.delivery_value:
                raise ValueError('Use a relative product filename without traversal.')
        if self.published and not self.delivery_value:
            raise ValueError('Published products require delivery content.')
        return self


LEGACY_CONFIG_KEYS = frozenset(['ai_enabled', 'automod_action', 'automod_enabled', 'automod_exempt_roles', 'block_invites', 'blocked_domains', 'caps_percent', 'level_channel', 'level_rewards', 'leveling_enabled', 'mention_limit', 'referral_points', 'reviews_allow_free', 'rewards_enabled', 'security_enabled', 'security_exempt_users', 'security_threshold', 'security_window', 'self_roles', 'spam_count', 'spam_window', 'xp_cooldown'])


class GuildConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prefix: str = Field(default='!', min_length=1, max_length=5)
    shop_title: str = Field(default='NEX CODEX • The collection', min_length=1, max_length=120)
    shop_description: str = Field(default='Discover server templates and bot source code. Browse products, review terms, and order privately.', min_length=1, max_length=1000)
    shop_image: str = Field(default='', max_length=2000)
    emojis: dict[str, str] = Field(default_factory=dict, max_length=16)
    staff_roles: list[int] = Field(default_factory=list, max_length=20)
    payment_roles: list[int] = Field(default_factory=list, max_length=20)
    ticket_category: int | None = None
    log_channel: int | None = None
    shop_channel: int | None = None
    giveaway_channel: int | None = None
    restrict_rejoin: bool = False
    welcome_channel: int | None = None
    leave_channel: int | None = None
    auto_role: int | None = None
    welcome_message: str = Field(default='Welcome {user} to {server}!', max_length=1000)
    leave_message: str = Field(default='{name} left {server}.', max_length=1000)
    upi_id: str = Field(default='', max_length=100, pattern=r'^$|^[\w.\-]+@[\w.\-]+$')
    qr_url: str = Field(default='', max_length=2000)
    payee: str = Field(default='', max_length=100)
    currency: str = Field(default='INR', pattern=r'^[A-Z]{3}$')
    payment_instructions: str = Field(default='Pay the exact amount and upload your receipt. Staff will verify it manually.', max_length=1500)
    free_claim_limit: int = Field(default=10, ge=1, le=1000)
    free_claim_cooldown: int = Field(default=3600, ge=0, le=31536000)

    @field_validator('emojis')
    @classmethod
    def emoji_values(cls, values):
        from .utils.theme import validate_emojis
        return validate_emojis(values)

    @field_validator('qr_url', 'shop_image')
    @classmethod
    def qr(cls, v):
        return safe_https(v) if v else v

    @model_validator(mode='after')
    def discord_ids(self):
        ids = self.staff_roles + self.payment_roles
        ids += [x for x in (self.ticket_category,self.log_channel,self.shop_channel,self.giveaway_channel,self.welcome_channel,self.leave_channel,self.auto_role) if x is not None]
        if any(not 0 < value < 2**63 for value in ids):
            raise ValueError('Discord IDs must be positive 64-bit integers.')
        return self
