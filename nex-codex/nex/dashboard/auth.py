from datetime import timedelta
import hashlib
import hmac
import secrets
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException, Request
from ..models import WebSession, OAuthState, now
from ..security import Actor, DomainError

DISCORD_API = 'https://discord.com/api/v10'


def digest(app, token):
    return hmac.new(app.state.config.session_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def session_for(request: Request):
    token = request.cookies.get('nex_session', '')
    if not token:
        return None
    with request.app.state.db.sessions() as s:
        row = s.get(WebSession, digest(request.app, token))
        return row if row and row.expires_at > now() else None


def require_session(request):
    session = session_for(request)
    if not session:
        raise HTTPException(401, 'Sign in with Discord to continue.')
    return session


def csrf(request, form, session):
    supplied = str(form.get('csrf', ''))
    if not supplied or not secrets.compare_digest(supplied, session.csrf):
        raise HTTPException(403, 'Invalid request token. Reload the page and try again.')
    request.app.state.limiter.check(('write', session.user_id), 30, 60)


async def discord_get(client, path, authorization):
    response = await client.get(DISCORD_API + path, headers={'Authorization': authorization})
    if response.status_code != 200:
        raise HTTPException(403, 'Discord could not verify your access. Check membership, bot installation and permissions.')
    return response.json()


async def guild_actor(request: Request, guild_id: int):
    user = require_session(request)
    cfg = request.app.state.config
    request.app.state.limiter.check(('guild_access', user.user_id), 60, 60)
    if not cfg.discord_token:
        raise HTTPException(503, 'The bot connection is not configured.')
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            guild = await discord_get(client, f'/guilds/{guild_id}', f'Bot {cfg.discord_token}')
            member = await discord_get(client, f'/guilds/{guild_id}/members/{user.user_id}', f'Bot {cfg.discord_token}')
            roles = await discord_get(client, f'/guilds/{guild_id}/roles', f'Bot {cfg.discord_token}')
    except httpx.HTTPError as exc:
        raise HTTPException(503, 'Discord is unavailable. Access could not be verified.') from exc
    ids = {int(r) for r in member.get('roles', [])}
    permissions = 0
    for role in roles:
        if int(role['id']) in ids | {guild_id}:
            permissions |= int(role['permissions'])
    return Actor(user.user_id, guild_id, frozenset(ids), bool(permissions & 8) or int(guild['owner_id']) == user.user_id, user.user_id in cfg.owner_ids)


def begin_oauth(request):
    cfg = request.app.state.config
    if not cfg.discord_client_id or not cfg.discord_client_secret:
        raise HTTPException(503, 'Discord OAuth is not configured. Follow the README setup instructions.')
    request.app.state.limiter.check(('oauth', request.client.host), 10, 60)
    state = secrets.token_urlsafe(32)
    with request.app.state.db.transaction() as s:
        s.add(OAuthState(token_hash=digest(request.app, state), expires_at=now()+timedelta(minutes=10)))
    url = 'https://discord.com/oauth2/authorize?' + urlencode({'client_id': cfg.discord_client_id, 'redirect_uri': cfg.discord_redirect_uri, 'response_type': 'code', 'scope': 'identify guilds', 'state': state, 'prompt': 'consent'})
    return url, state


async def finish_oauth(request, code, state):
    cookie = request.cookies.get('nex_oauth', '')
    if not state or not cookie or not secrets.compare_digest(cookie, state):
        raise HTTPException(400, 'OAuth state validation failed.')
    with request.app.state.db.transaction() as s:
        row = s.get(OAuthState, digest(request.app, state))
        if not row or row.expires_at <= now():
            raise HTTPException(400, 'OAuth state expired or already used.')
        s.delete(row)
    cfg = request.app.state.config
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(DISCORD_API+'/oauth2/token', data={'client_id': cfg.discord_client_id, 'client_secret': cfg.discord_client_secret, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': cfg.discord_redirect_uri})
            if response.status_code != 200:
                raise HTTPException(400, 'Discord sign-in failed. Start a new sign-in.')
            token = response.json()['access_token']
            user = await discord_get(client, '/users/@me', 'Bearer '+token)
            guilds = await discord_get(client, '/users/@me/guilds', 'Bearer '+token)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(503, 'Discord sign-in is unavailable.') from exc
    session_token = secrets.token_urlsafe(48)
    with request.app.state.db.transaction() as s:
        old = request.cookies.get('nex_session')
        if old:
            previous = s.get(WebSession, digest(request.app, old))
            if previous:
                s.delete(previous)
        s.add(WebSession(token_hash=digest(request.app, session_token), user_id=int(user['id']), username=user['username'], guilds=[{'id': str(g['id']), 'name': g['name']} for g in guilds], csrf=secrets.token_urlsafe(32), expires_at=now()+timedelta(hours=8)))
    return session_token
