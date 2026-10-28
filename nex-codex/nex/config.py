from functools import lru_cache
from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    discord_token: str = ''
    discord_client_id: str = ''
    discord_client_secret: str = ''
    discord_redirect_uri: str = 'http://localhost:8000/auth/callback'
    public_url: str = 'http://localhost:8000'
    database_url: str = 'sqlite:///./nex.db'
    session_secret: str = ''
    cookie_secure: bool = False
    owner_ids: list[int] = Field(default_factory=list)
    default_prefix: str = Field(default='!', min_length=1, max_length=5)
    sync_commands: bool = True
    command_guild_ids: list[int] = Field(default_factory=list, max_length=25)
    product_root: Path = Path('private/products')
    ai_api_key: str = ''
    ai_base_url: str = 'https://api.openai.com/v1'
    ai_model: str = ''

    @model_validator(mode='after')
    def secure_public_deployment(self):
        if any(not 0 < value < 2**63 for value in self.command_guild_ids + self.owner_ids):
            raise ValueError('Discord IDs must be positive 64-bit integers.')
        if self.public_url.startswith('https://') and not self.cookie_secure:
            raise ValueError('HTTPS deployments require COOKIE_SECURE=true')
        return self

    def require_dashboard(self):
        if len(self.session_secret) < 32:
            raise RuntimeError('Set SESSION_SECRET to at least 32 random characters')


@lru_cache
def settings() -> Settings:
    return Settings()
