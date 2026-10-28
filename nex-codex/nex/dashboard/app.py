from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
import json
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
from pydantic import ValidationError
from sqlalchemy import select, func, text
from ..config import settings
from ..db import Database
from ..models import Product, Order, Payment, Ticket, Audit, Review, Heartbeat, WebSession, now
from ..schemas import ProductInput, GuildConfig
from ..security import DomainError, RateLimiter
from ..services.core import Core
from ..services.marketplace import Marketplace
from ..services.community import Community
from .middleware import BodyLimitMiddleware
from .auth import session_for, require_session, guild_actor, csrf, begin_oauth, finish_oauth, digest

HERE = Path(__file__).parent


def create_app(cfg=None, database=None):
    cfg = cfg or settings()
    cfg.require_dashboard()
    db = database or Database(cfg.database_url)

    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        yield
        if database is None:
            db.engine.dispose()

    app = FastAPI(title='NEX CODEX', version='1.3.0', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.config, app.state.db = cfg, db
    app.state.core, app.state.market, app.state.community = Core(db), Marketplace(db, cfg.product_root), Community(db)
    app.state.limiter = RateLimiter()
    templates = Jinja2Templates(directory=HERE/'templates')
    app.mount('/static', StaticFiles(directory=HERE/'static'), name='static')

    app.add_middleware(BodyLimitMiddleware)

    @app.middleware('http')
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers.update({'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; script-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'", 'Cache-Control': 'no-store'})
        if cfg.cookie_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    def render(request, template, **data):
        user = session_for(request)
        return templates.TemplateResponse(request=request, name=template, context={'user': user, 'brand': 'NEX CODEX', 'public_url': cfg.public_url, 'guild_id': None, 'active': 'overview', 'is_owner': bool(user and user.user_id in cfg.owner_ids), 'can_configure': bool(user and user.user_id in cfg.owner_ids), **data})

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return templates.TemplateResponse(request=request, name='error.html', context={'user': session_for(request), 'error': str(exc), 'status': 400}, status_code=400)

    @app.exception_handler(ValidationError)
    async def validation_error(request, exc):
        errors = '; '.join('.'.join(str(v) for v in e['loc']) + ': ' + e['msg'] for e in exc.errors())
        return templates.TemplateResponse(request=request, name='error.html', context={'user': session_for(request), 'error': errors, 'status': 422}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return templates.TemplateResponse(request=request, name='error.html', context={'user': session_for(request), 'error': exc.detail, 'status': exc.status_code}, status_code=exc.status_code)

    @app.get('/health')
    def health():
        with db.sessions() as s:
            s.execute(text('SELECT 1'))
            bot = s.get(Heartbeat, 'bot')
            online = bool(bot and bot.updated_at > now()-timedelta(seconds=90))
        return {'service': 'NEX CODEX', 'database': 'ok', 'bot': 'online' if online else 'offline', 'version': '1.3.0'}

    @app.get('/auth/login')
    async def login(request: Request):
        url, state = begin_oauth(request)
        response = RedirectResponse(url, status_code=303)
        response.set_cookie('nex_oauth', state, max_age=600, httponly=True, secure=cfg.cookie_secure, samesite='lax')
        return response

    @app.get('/auth/callback')
    async def callback(request: Request, code: str = '', state: str = ''):
        token = await finish_oauth(request, code, state)
        response = RedirectResponse('/servers', status_code=303)
        response.set_cookie('nex_session', token, max_age=28800, httponly=True, secure=cfg.cookie_secure, samesite='lax')
        response.delete_cookie('nex_oauth')
        return response

    @app.post('/auth/logout')
    async def logout(request: Request):
        user = require_session(request)
        csrf(request, await request.form(), user)
        with db.transaction() as s:
            row = s.get(WebSession, user.token_hash)
            if row:
                s.delete(row)
        response = RedirectResponse('/', status_code=303)
        response.delete_cookie('nex_session')
        return response

    @app.get('/')
    def home(request: Request):
        products = app.state.market.browse()
        with db.sessions() as s:
            count = s.scalar(select(func.count()).select_from(Product).where(Product.published.is_(True), Product.archived.is_(False)))
        return render(request, 'home.html', products=products[:3], product_count=count)

    @app.get('/guide')
    def guide(request: Request):
        return render(request, 'guide.html', active='guide')

    @app.get('/servers')
    def servers(request: Request):
        user = require_session(request)
        return render(request, 'servers.html', guilds=user.guilds, active='servers')

    @app.get('/marketplace')
    def marketplace(request: Request, category: str = '', q: str = '', page: int = Query(1, ge=1, le=10000)):
        return render(request, 'marketplace.html', products=app.state.market.browse(category=category or None, query=q, page=page), category=category, query=q, page=max(1,page), active='marketplace')

    @app.get('/marketplace/{product_id}')
    def product(request: Request, product_id: str):
        with db.sessions() as s:
            p = s.get(Product, product_id)
            if not p or p.category not in ('template', 'source') or not p.published or p.archived:
                raise HTTPException(404, 'Product not found.')
            reviews = list(s.scalars(select(Review).where(Review.product_id == p.id, Review.hidden.is_(False)).order_by(Review.id.desc()).limit(10)))
            average = s.scalar(select(func.avg(Review.rating)).where(Review.product_id == p.id, Review.hidden.is_(False)))
        return render(request, 'product.html', product=p, reviews=reviews, average=average, active='marketplace')

    @app.get('/guild/{guild_id}')
    async def overview(request: Request, guild_id: int):
        a = await guild_actor(request, guild_id)
        a.require(app.state.core.config(guild_id))
        with db.sessions() as s:
            counts = {'products': s.scalar(select(func.count()).select_from(Product).where(Product.guild_id == guild_id)), 'orders': s.scalar(select(func.count()).select_from(Order).where(Order.guild_id == guild_id)), 'tickets': s.scalar(select(func.count()).select_from(Ticket).where(Ticket.guild_id == guild_id, Ticket.state.in_(['open','creating']))), 'reviews': s.scalar(select(func.count()).select_from(Order).where(Order.guild_id == guild_id, Order.state == 'payment_submitted'))}
            activity = list(s.scalars(select(Audit).where(Audit.guild_id == guild_id).order_by(Audit.id.desc()).limit(8)))
            orders = list(s.scalars(select(Order).where(Order.guild_id == guild_id).order_by(Order.created_at.desc()).limit(6)))
        return render(request, 'overview.html', guild_id=guild_id, can_configure=a.owner or a.administrator, counts=counts, activity=activity, orders=orders)

    @app.get('/guild/{guild_id}/settings')
    async def get_settings(request: Request, guild_id: int):
        (await guild_actor(request, guild_id)).require_admin()
        return render(request, 'settings.html', guild_id=guild_id, config=app.state.core.config(guild_id), can_configure=True, active='settings', saved=request.query_params.get('saved'))

    @app.post('/guild/{guild_id}/settings')
    async def save_settings(request: Request, guild_id: int):
        user = require_session(request)
        form = await request.form()
        csrf(request, form, user)
        a = await guild_actor(request, guild_id)
        a.require_admin()
        try:
            changes = json.loads(str(form.get('configuration', '{}')))
        except ValueError:
            raise DomainError('Configuration must be valid JSON.')
        if not isinstance(changes, dict):
            raise DomainError('Configuration must be a JSON object.')
        app.state.core.configure(a, changes)
        return RedirectResponse(f'/guild/{guild_id}/settings?saved=1', status_code=303)

    @app.get('/guild/{guild_id}/products')
    async def manage_products(request: Request, guild_id: int, page: int = Query(1, ge=1, le=10000)):
        a = await guild_actor(request, guild_id)
        a.require_owner()
        return render(request, 'manage_products.html', guild_id=guild_id, products=app.state.market.browse(guild_id= guild_id, page=page, staff=True), active='products', page=max(1,page))

    @app.get('/guild/{guild_id}/products/edit')
    async def edit_product(request: Request, guild_id: int, product_id: str = ''):
        a = await guild_actor(request, guild_id)
        a.require_owner()
        p = None
        if product_id:
            with db.sessions() as s:
                p = s.get(Product, product_id)
                if not p or p.guild_id != guild_id:
                    raise HTTPException(404, 'Product not found.')
        return render(request, 'edit_product.html', guild_id=guild_id, product=p, active='products')

    @app.post('/guild/{guild_id}/products')
    async def save_product(request: Request, guild_id: int):
        user = require_session(request)
        form = await request.form()
        csrf(request, form, user)
        a = await guild_actor(request, guild_id)
        data = {k: v for k, v in form.items() if k not in ('csrf', 'product_id')}
        for key in ('published', 'archived', 'available'):
            data[key] = form.get(key) == 'on'
        app.state.market.save_product(a, data, str(form.get('product_id', '')) or None)
        return RedirectResponse(f'/guild/{guild_id}/products', status_code=303)

    @app.get('/guild/{guild_id}/orders')
    async def my_orders(request: Request, guild_id: int, page: int = Query(1, ge=1, le=10000)):
        a = await guild_actor(request, guild_id)
        with db.sessions() as s:
            orders = list(s.scalars(select(Order).where(Order.guild_id == guild_id, Order.user_id == a.user_id).order_by(Order.created_at.desc()).offset((max(1,page)-1)*20).limit(20)))
        return render(request, 'orders.html', guild_id=guild_id, can_configure=a.owner or a.administrator, orders=orders, active='orders', page=max(1,page))

    @app.get('/guild/{guild_id}/download/{order_id}')
    async def download(request: Request, guild_id: int, order_id: str):
        a = await guild_actor(request, guild_id)
        app.state.limiter.check(('download', a.user_id), 10, 60)
        result = app.state.market.delivery(a, order_id)
        if result['delivery_kind'] == 'file':
            return FileResponse(result['path'], filename=result['path'].name, media_type='application/octet-stream', background=BackgroundTask(app.state.market.delivered, a, order_id))
        response = render(request, 'delivery.html', guild_id=guild_id, can_configure=a.owner or a.administrator, delivery=result, active='orders')
        response.background = BackgroundTask(app.state.market.delivered, a, order_id)
        return response

    @app.get('/guild/{guild_id}/payments')
    async def payments(request: Request, guild_id: int):
        a = await guild_actor(request, guild_id)
        a.require(app.state.core.config(guild_id), 'payment')
        with db.sessions() as s:
            rows = s.execute(select(Order, Payment).join(Payment, Payment.order_id == Order.id).where(Order.guild_id == guild_id, Payment.state == 'submitted', Order.state.in_(['payment_submitted','verification_required'])).order_by(Payment.created_at).limit(50)).all()
        return render(request, 'payments.html', guild_id=guild_id, can_configure=a.owner or a.administrator, rows=rows, active='payments')

    @app.post('/guild/{guild_id}/payments/{order_id}')
    async def payment_decision(request: Request, guild_id: int, order_id: str):
        user = require_session(request)
        form = await request.form()
        csrf(request, form, user)
        a = await guild_actor(request, guild_id)
        if form.get('decision') not in ('approve', 'reject'):
            raise DomainError('Choose approve or reject.')
        approve = form['decision'] == 'approve'
        if approve and form.get('verified') != 'on':
            raise DomainError('Independently verify the transaction before approving.')
        app.state.market.review_payment(a, order_id, approve, str(form.get('reason', '')))
        return RedirectResponse(f'/guild/{guild_id}/payments', status_code=303)

    @app.get('/api/products')
    def public_products(category: str = '', q: str = '', page: int = Query(1, ge=1, le=10000)):
        products = app.state.market.browse(category=category or None, query=q, page=page)
        return {'page': max(1, page), 'products': [{key: getattr(p, key) for key in ('id','guild_id','name','description','category','price','currency','thumbnail','terms','available')} for p in products]}

    @app.get('/api/guild/{guild_id}/orders')
    async def api_orders(request: Request, guild_id: int, page: int = Query(1, ge=1, le=10000)):
        a = await guild_actor(request, guild_id)
        with db.sessions() as s:
            rows = list(s.scalars(select(Order).where(Order.guild_id == guild_id, Order.user_id == a.user_id).order_by(Order.created_at.desc()).offset((max(1,page)-1)*20).limit(20)))
            return {'page': max(1,page), 'orders':[{'id':o.id,'name':o.snapshot['name'],'amount':o.amount,'currency':o.currency,'state':o.state,'created_at':o.created_at} for o in rows]}

    @app.get('/api/guild/{guild_id}/settings')
    async def api_settings(request: Request, guild_id: int):
        (await guild_actor(request, guild_id)).require_admin()
        return app.state.core.config(guild_id)

    return app
