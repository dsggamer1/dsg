from functools import lru_cache
from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ignore retired environment keys when upgrading an existing host.
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    discord_token: str = ''
    database_url: str = 'sqlite:///./nex.db'
    owner_ids: list[int] = Field(default_factory=list)
    default_prefix: str = Field(default='!', min_length=1, max_length=5)
    auto_load_emojis: bool = True
    sync_commands: bool = True
    command_guild_ids: list[int] = Field(default_factory=list, max_length=25)
    product_root: Path = Path('private/products')

    @model_validator(mode='after')
    def valid_discord_ids(self):
        if any(not 0 < value < 2**63 for value in self.command_guild_ids + self.owner_ids):
            raise ValueError('Discord IDs must be positive 64-bit integers.')
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
