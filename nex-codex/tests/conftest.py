from pathlib import Path
import pytest
from nex.db import Database
from nex.config import Settings
from nex.security import Actor
from nex.services.core import Core
from nex.services.marketplace import Marketplace
from nex.services.community import Community


@pytest.fixture
def db(tmp_path):
    database = Database('sqlite:///' + str(tmp_path/'test.db'))
    database.initialize()
    yield database
    database.engine.dispose()


@pytest.fixture
def owner():
    return Actor(100, 1000, administrator=True, owner=True)


@pytest.fixture
def buyer():
    return Actor(200, 1000)


@pytest.fixture
def core(db, owner):
    service = Core(db)
    service.configure(owner, {'staff_roles': [20], 'free_claim_cooldown': 0})
    return service


@pytest.fixture
def market(db, core, tmp_path):
    return Marketplace(db, tmp_path)


@pytest.fixture
def paid(market, owner):
    return market.save_product(owner, {'name': 'Test source', 'category': 'bot', 'price': 49900, 'published': True, 'delivery_kind': 'instructions', 'delivery_value': 'Synthetic delivery instructions'})


@pytest.fixture
def free(market, owner):
    return market.save_product(owner, {'name': 'Test template', 'category': 'template', 'price': 0, 'published': True, 'delivery_kind': 'instructions', 'delivery_value': 'Synthetic template instructions', 'cooldown_seconds': 0})
