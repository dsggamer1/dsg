from datetime import timedelta
import importlib
import secrets
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from nex.config import Settings
from nex.dashboard.app import create_app
from nex.dashboard.auth import digest, guild_actor, finish_oauth
from nex.models import WebSession, OAuthState, now
from nex.security import Actor


@pytest.fixture
def web(db,tmp_path):
    cfg=Settings(_env_file=None,session_secret='synthetic-test-secret-'*3,database_url=str(db.engine.url),product_root=tmp_path,discord_token='synthetic-bot-token',owner_ids=[100])
    app=create_app(cfg,db)
    with TestClient(app) as client:
        yield app,client


def login(app,client,db,user_id=200):
    token=secrets.token_urlsafe(32)
    with db.transaction() as s:
        s.add(WebSession(token_hash=digest(app,token),user_id=user_id,username='Synthetic user',guilds=[{'id':'1000','name':'Synthetic guild'}],csrf='synthetic-csrf',expires_at=now()+timedelta(hours=1)))
    client.cookies.set('nex_session',token)


def test_public_pages_and_real_empty_states(web):
    app,c=web
    for url in ('/','/marketplace','/marketplace?category=source','/guide','/health'):
        response=c.get(url)
        assert response.status_code==200
        assert response.headers['x-content-type-options']=='nosniff'
        assert 'frame-ancestors' in response.headers['content-security-policy']
    assert c.get('/health').json()['bot']=='offline'
    assert 'Good things are on the way' in c.get('/marketplace').text


@pytest.mark.parametrize('url',['/servers','/guild/1000','/guild/1000/settings','/guild/1000/products','/guild/1000/orders','/guild/1000/payments','/guild/1000/download/unknown'])
def test_protected_pages_require_login(web,url):
    assert web[1].get(url).status_code==401


def test_oauth_requires_configuration_and_valid_state(web):
    app,c=web
    assert c.get('/auth/login').status_code==503
    assert c.get('/auth/callback?code=bogus&state=bogus').status_code==400


def test_csrf_and_logout_invalidation(web,db):
    app,c=web
    login(app,c,db)
    assert c.post('/auth/logout',data={'csrf':'wrong'}).status_code==403
    assert c.post('/guild/1000/settings',data={'configuration':'{}'}).status_code==403
    assert c.get('/servers').status_code==200
    c.post('/auth/logout',data={'csrf':'synthetic-csrf'})
    assert c.get('/servers').status_code==401


def test_staff_pages_and_writes_with_mocked_live_membership(web,db,core,monkeypatch):
    app,c=web
    login(app,c,db,100)
    module=importlib.import_module('nex.dashboard.app')
    monkeypatch.setattr(module,'guild_actor',AsyncMock(return_value=Actor(100,1000,administrator=True,owner=True)))
    for url in ('/guild/1000','/guild/1000/settings','/guild/1000/products','/guild/1000/products/edit','/guild/1000/orders','/guild/1000/payments'):
        r=c.get(url)
        assert r.status_code==200, (url,r.text)
    assert c.post('/guild/1000/settings',data={'csrf':'synthetic-csrf','configuration':'{"prefix":"?"}'}).status_code==200
    assert core.config(1000)['prefix']=='?'
    response=c.post('/guild/1000/products',data={'csrf':'synthetic-csrf','name':'Dashboard test','category':'template','price':'0','currency':'INR','delivery_kind':'instructions','delivery_value':'Synthetic instructions','published':'on','available':'on'})
    assert response.status_code==200
    assert 'Dashboard test' in c.get('/marketplace').text


def test_regular_member_cannot_manage(web,db,core,monkeypatch):
    app,c=web
    login(app,c,db)
    module=importlib.import_module('nex.dashboard.app')
    monkeypatch.setattr(module,'guild_actor',AsyncMock(return_value=Actor(200,1000)))
    for path in ('settings','products','payments'):
        assert c.get('/guild/1000/'+path).status_code==400
    assert c.post('/guild/1000/settings',data={'csrf':'synthetic-csrf','configuration':'{"staff_roles":[55]}'}).status_code==400
    assert core.config(1000)['staff_roles']==[20]


def test_xss_escaped_and_private_delivery_not_public(web,db,market,owner,monkeypatch):
    app,c=web
    p=market.save_product(owner,{'name':'<script>alert(1)</script>','category':'source','published':True,'delivery_value':'PRIVATE_DELIVERY_SENTINEL'})
    response=c.get('/marketplace/'+p.id)
    assert response.status_code==200
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;' in response.text
    assert 'PRIVATE_DELIVERY_SENTINEL' not in response.text


async def test_live_permission_resolver_uses_membership_roles(web,db,monkeypatch):
    app,c=web
    login(app,c,db)
    request=SimpleNamespace(app=app,cookies={'nex_session':c.cookies.get('nex_session')})
    auth=importlib.import_module('nex.dashboard.auth')
    async def fake_get(client,path,authorization):
        assert authorization=='Bot synthetic-bot-token'
        if path.endswith('/members/200'):
            return {'roles':['30']}
        if path.endswith('/roles'):
            return [{'id':'1000','permissions':'0'},{'id':'30','permissions':'8'}]
        return {'owner_id':'1'}
    monkeypatch.setattr(auth,'discord_get',fake_get)
    a=await guild_actor(request,1000)
    assert a.administrator and a.roles==frozenset({30})
    monkeypatch.setattr(auth,'discord_get',AsyncMock(side_effect=HTTPException(403,'Not a member')))
    with pytest.raises(HTTPException):
        await guild_actor(request,1000)


async def test_oauth_state_single_use_and_cookie_flags(web,db,monkeypatch):
    app,c=web
    state='synthetic-state'
    with db.transaction() as s:
        s.add(OAuthState(token_hash=digest(app,state),expires_at=now()+timedelta(minutes=1)))
    c.cookies.set('nex_oauth',state)
    auth=importlib.import_module('nex.dashboard.auth')
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs):
            return httpx.Response(200,json={'access_token':'synthetic-access'},request=httpx.Request('POST','https://discord.com'))
    monkeypatch.setattr(auth.httpx,'AsyncClient',lambda **kwargs:FakeClient())
    async def fake_get(client,path,authorization):
        return [{'id':'1000','name':'Test'}] if path.endswith('/guilds') else {'id':'200','username':'Test'}
    monkeypatch.setattr(auth,'discord_get',fake_get)
    r=c.get('/auth/callback?code=synthetic&state='+state,follow_redirects=False)
    assert r.status_code==303
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=lax' in r.headers['set-cookie']
    assert c.get('/auth/callback?code=synthetic&state='+state).status_code==400


def test_session_expiry(web,db):
    app,c=web
    login(app,c,db)
    from sqlalchemy import select
    with db.transaction() as s:
        s.scalar(select(WebSession)).expires_at=now()-timedelta(seconds=1)
    assert c.get('/servers').status_code==401


def test_request_body_bound_and_public_api_redaction(web,market,owner):
    app,c=web
    assert c.post('/auth/logout',content=b'x'*65537).status_code==413
    p=market.save_product(owner,{'name':'API product','category':'source','published':True,'delivery_value':'SECRET_DELIVERY'})
    payload=c.get('/api/products').json()
    assert payload['products'][0]['id']==p.id
    assert 'SECRET_DELIVERY' not in str(payload)
    assert c.get('/api/guild/1000/orders').status_code==401
    assert c.get('/api/guild/1000/settings').status_code==401


def test_hosting_removed_and_pagination_bounded(web):
    app,c=web
    for path in ('/hosting','/guild/1000/hosting'):
        assert c.get(path).status_code==404
    assert c.post('/guild/1000/hosting/unknown',data={}).status_code==404
    for path in ('/marketplace','/api/products'):
        assert c.get(path+'?page=9999999999999999999999999').status_code==422
    assert '>Hosting<' not in c.get('/').text


def test_protected_file_delivery_and_refund(web,db,market,owner,buyer,tmp_path,monkeypatch):
    from nex.models import Order
    app,c=web
    (tmp_path/'product.zip').write_bytes(b'synthetic source archive')
    p=market.save_product(owner,{'name':'Private source','category':'source','published':True,'delivery_kind':'file','delivery_value':'product.zip'})
    order=market.order(buyer,p.id,'file-test')
    login(app,c,db)
    module=importlib.import_module('nex.dashboard.app')
    monkeypatch.setattr(module,'guild_actor',AsyncMock(return_value=Actor(999,1000)))
    assert c.get(f'/guild/1000/download/{order.id}').status_code==400
    monkeypatch.setattr(module,'guild_actor',AsyncMock(return_value=buyer))
    response=c.get(f'/guild/1000/download/{order.id}')
    assert response.status_code==200 and response.content==b'synthetic source archive'
    with db.sessions() as s:
        assert s.get(Order,order.id).state=='delivered'
    # Missing files never become successful deliveries.
    (tmp_path/'product.zip').unlink()
    assert c.get(f'/guild/1000/download/{order.id}').status_code==400
    # Paid refunds revoke future access even if the file is restored.
    paid=market.save_product(owner,{'name':'Paid archive','category':'source','price':100,'published':True,'delivery_value':'private instructions'})
    paid_order=market.order(buyer,paid.id,'paid-file-test')
    market.submit_payment(buyer,paid_order.id,'https://cdn.discordapp.com/attachments/synthetic.png')
    market.review_payment(owner,paid_order.id,True)
    market.change_order(owner,paid_order.id,'manually_refunded','External refund checked')
    assert c.get(f'/guild/1000/download/{paid_order.id}').status_code==400


@pytest.mark.parametrize('who',[Actor(101,1000,administrator=True),Actor(102,1000,frozenset({20,30}))])
def test_admin_and_staff_cannot_bypass_product_ownership(web,db,core,paid,monkeypatch,who):
    app,c=web
    login(app,c,db,who.user_id)
    module=importlib.import_module('nex.dashboard.app')
    monkeypatch.setattr(module,'guild_actor',AsyncMock(return_value=who))
    for path in ('products','products/edit','products/edit?product_id='+paid.id):
        response=c.get('/guild/1000/'+path)
        assert response.status_code==400
        assert 'Only a bot owner' in response.text
    expected=200 if who.administrator else 400
    assert c.get('/guild/1000/settings').status_code==expected
    assert c.get('/api/guild/1000/settings').status_code==expected
    assert c.post('/guild/1000/settings',data={'csrf':'synthetic-csrf','configuration':'{"prefix":"?"}'}).status_code==expected
    assert core.config(1000)['prefix']==('?' if who.administrator else '!')
    assert c.post('/guild/1000/products',data={'csrf':'synthetic-csrf','product_id':paid.id,'name':'Unauthorized source','category':'source','price':'0','delivery_value':'x'}).status_code==400
    assert core.config(1000)['staff_roles']==[20]
    # Payment review access remains available to the configured reviewer/admin.
    assert c.get('/guild/1000/payments').status_code==200
    overview=c.get('/guild/1000').text
    assert ('Configure server' in overview)==who.administrator
    assert 'Manage products' not in overview


def test_premium_routes_removed(web):
    assert web[1].get('/guild/1000/premium').status_code==404
    assert web[1].post('/guild/1000/premium').status_code==404
