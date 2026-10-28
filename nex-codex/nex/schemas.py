from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .security import safe_https


class ProductInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default='', max_length=4000)
    category: Literal['template', 'source', 'hosting']
    price: int = Field(default=0, ge=0, le=100000000)
    currency: str = Field(default='INR', pattern=r'^[A-Z]{3}$')
    thumbnail: str = Field(default='', max_length=2000)
    terms: str = Field(default='', max_length=4000)
    published: bool = False
    archived: bool = False
    available: bool = True
    delivery_kind: Literal['instructions', 'link', 'file', 'hosting'] = 'instructions'
    delivery_value: str = Field(default='', max_length=4000)
    claim_limit: int = Field(default=10, ge=1, le=1000)
    cooldown_seconds: int = Field(default=86400, ge=0, le=31536000)
    duration_days: int = Field(default=30, ge=1, le=3650)
    capacity: str = Field(default='', max_length=200)

    @model_validator(mode='after')
    def delivery(self):
        if self.thumbnail:
            safe_https(self.thumbnail)
        if self.category == 'hosting' and self.delivery_kind != 'hosting':
            raise ValueError('Hosting products require hosting delivery.')
        if self.category != 'hosting' and self.delivery_kind == 'hosting':
            raise ValueError('Hosting delivery requires a hosting product.')
        if self.delivery_kind == 'link':
            safe_https(self.delivery_value)
        if self.delivery_kind == 'file':
            from pathlib import PurePosixPath
            p = PurePosixPath(self.delivery_value)
            if p.is_absolute() or '..' in p.parts or '\\' in self.delivery_value or not self.delivery_value:
                raise ValueError('Use a relative product filename without traversal.')
        if self.published and self.delivery_kind != 'hosting' and not self.delivery_value:
            raise ValueError('Published products require delivery content.')
        return self


class GuildConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prefix: str = Field(default='!', min_length=1, max_length=5)
    staff_roles: list[int] = Field(default_factory=list, max_length=20)
    payment_roles: list[int] = Field(default_factory=list, max_length=20)
    ticket_category: int | None = None
    log_channel: int | None = None
    welcome_channel: int | None = None
    leave_channel: int | None = None
    auto_role: int | None = None
    self_roles: list[int] = Field(default_factory=list, max_length=20)
    welcome_message: str = Field(default='Welcome {user} to {server}!', max_length=1000)
    leave_message: str = Field(default='{name} left {server}.', max_length=1000)
    upi_id: str = Field(default='', max_length=100, pattern=r'^$|^[\w.\-]+@[\w.\-]+$')
    qr_url: str = Field(default='', max_length=2000)
    payee: str = Field(default='', max_length=100)
    currency: str = Field(default='INR', pattern=r'^[A-Z]{3}$')
    payment_instructions: str = Field(default='Pay the exact amount and upload your receipt. Staff will verify it manually.', max_length=1500)
    automod_enabled: bool = False
    automod_action: Literal['log', 'delete'] = 'log'
    automod_exempt_roles: list[int] = Field(default_factory=list, max_length=20)
    spam_count: int = Field(default=6, ge=3, le=30)
    spam_window: int = Field(default=8, ge=3, le=60)
    mention_limit: int = Field(default=8, ge=3, le=100)
    block_invites: bool = False
    caps_percent: int = Field(default=85, ge=50, le=100)
    blocked_domains: list[str] = Field(default_factory=list, max_length=100)
    security_enabled: bool = False
    security_threshold: int = Field(default=4, ge=2, le=30)
    security_window: int = Field(default=30, ge=10, le=300)
    security_exempt_users: list[int] = Field(default_factory=list, max_length=100)
    leveling_enabled: bool = False
    xp_cooldown: int = Field(default=60, ge=15, le=3600)
    level_channel: int | None = None
    level_rewards: dict[str, int] = Field(default_factory=dict)
    rewards_enabled: bool = False
    referral_points: int = Field(default=10, ge=0, le=10000)
    reviews_allow_free: bool = True
    free_claim_limit: int = Field(default=10, ge=1, le=1000)
    free_claim_cooldown: int = Field(default=3600, ge=0, le=31536000)
    ai_enabled: bool = False

    @field_validator('qr_url')
    @classmethod
    def qr(cls, v):
        return safe_https(v) if v else v

    @field_validator('blocked_domains')
    @classmethod
    def domains(cls, values):
        import re
        if any(not re.fullmatch(r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', v) for v in values):
            raise ValueError('Enter plain domain names.')
        return [v.lower() for v in values]

    @model_validator(mode='after')
    def discord_ids(self):
        ids = self.staff_roles + self.payment_roles + self.self_roles + self.automod_exempt_roles + self.security_exempt_users + list(self.level_rewards.values())
        ids += [x for x in (self.ticket_category,self.log_channel,self.welcome_channel,self.leave_channel,self.auto_role,self.level_channel) if x is not None]
        if any(not 0 < value < 2**63 for value in ids):
            raise ValueError('Discord IDs must be positive 64-bit integers.')
        if any(not key.isdecimal() or not 1 <= int(key) <= 10000 for key in self.level_rewards):
            raise ValueError('Reward levels must be integers from 1 to 10000.')
        return self
