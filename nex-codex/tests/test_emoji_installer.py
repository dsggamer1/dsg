"""Guild emoji API calls are mocked; IDs are synthetic fixtures."""
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
import pytest
from sqlalchemy import select
from nex.models import Audit
from nex.security import Actor, DomainError
from nex.services.emojis import ASSET_ROOT, EMOJI_ASSETS, EmojiInstaller


class Emoji:
    def __init__(self,name,ident):
        self.name,self.id=name,ident
        self.animated,self.roles,self.available=False,[],True
    def __str__(self):
        return f'<:{self.name}:{self.id}>'


def guild(available=50):
    existing=[]
    async def create(**kwargs):
        assert kwargs['image'].startswith(b'\x89PNG\r\n\x1a\n')
        value=Emoji(kwargs['name'],123456789012345678+len(existing))
        existing.append(value)
        return value
    return SimpleNamespace(id=1000,emoji_limit=available,me=SimpleNamespace(guild_permissions=discord.Permissions(create_expressions=True)),fetch_emojis=AsyncMock(side_effect=lambda:list(existing)),create_custom_emoji=AsyncMock(side_effect=create))


def test_bundled_assets_are_valid_bounded_pngs():
    paths=list(ASSET_ROOT.glob('*.png'))
    assert len(paths)==49
    for path in paths:
        data=path.read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n' and len(data)<256*1024
        assert struct.unpack('>II',data[16:24])==(128,128)
    assert all((ASSET_ROOT/f'nex_{name}.png').is_file() for name in EMOJI_ASSETS.values())


@pytest.mark.parametrize('who',[Actor(100,1000,owner=True),Actor(101,1000,administrator=True)])
async def test_upload_records_returned_ids_and_restart_reuses(core,db,who):
    server=guild()
    result=await EmojiInstaller(core).install(who,server)
    assert result=={'created':14,'reused':0,'mapped':14,'failure':None}
    cfg=core.config(1000)['emojis']
    assert cfg['welcome']=='<:nex_welcome:123456789012345678>'
    assert set(cfg)==set(EMOJI_ASSETS)
    result=await EmojiInstaller(core).install(who,server)
    assert result=={'created':0,'reused':14,'mapped':14,'failure':None}
    assert server.create_custom_emoji.await_count==14
    with db.sessions() as s:
        assert s.scalar(select(Audit).where(Audit.action=='emojis.install')).details['complete']


async def test_upload_full_server_partial_failure_and_retry(core,owner):
    server=guild(available=2)
    result=await EmojiInstaller(core).install(owner,server)
    assert result['created']==2 and result['mapped']==2 and 'no free' in result['failure']
    assert len(core.config(1000)['emojis'])==2
    server.emoji_limit=50
    result=await EmojiInstaller(core).install(owner,server)
    assert result['created']==12 and result['reused']==2 and not result['failure']
    assert server.create_custom_emoji.await_count==14


async def test_discord_failure_never_claims_complete(core,owner):
    server=guild()
    server.create_custom_emoji.side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='Forbidden'),'Missing permission')
    result=await EmojiInstaller(core).install(owner,server)
    assert result['failure'] and result['mapped']==0 and result['created']==0
    assert core.config(1000)['emojis']=={}


@pytest.mark.parametrize('case',['staff','member','wrong-guild','missing-permission'])
async def test_installer_denies_before_discord_mutation(core,owner,case):
    server=guild()
    who=owner
    if case=='staff': who=Actor(102,1000,frozenset({20,30}))
    if case=='member': who=Actor(200,1000)
    if case=='wrong-guild': server.id=999
    if case=='missing-permission': server.me.guild_permissions=discord.Permissions.none()
    with pytest.raises(DomainError):
        await EmojiInstaller(core).install(who,server)
    server.fetch_emojis.assert_not_awaited()
    server.create_custom_emoji.assert_not_awaited()
