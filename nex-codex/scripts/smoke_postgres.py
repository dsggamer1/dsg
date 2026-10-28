import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sqlalchemy import select,func
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from nex.db import Database
from nex.models import Base,Order,Entitlement
from nex.security import Actor,DomainError
from nex.services.core import Core
from nex.services.marketplace import Marketplace
import os
from sqlalchemy.engine import make_url
url=os.environ.get('NEX_POSTGRES_TEST_URL', '')
if not url or make_url(url).database != 'nex_test':
    raise SystemExit('Set NEX_POSTGRES_TEST_URL to a dedicated PostgreSQL database named nex_test. This creates synthetic test records.')
db=Database(url)
db.initialize()
admin=Actor(100,1000,administrator=True,owner=True)
buyer=Actor(200,1000)
Core(db).configure(admin,{'upi_id':'synthetic@example','qr_url':'https://example.com/synthetic-qr.png','payee':'Synthetic test fixture'})
market=Marketplace(db,Path('/tmp'))
product=market.save_product(admin,{'name':'PostgreSQL test product','category':'bot','published':True,'price':1000,'delivery_value':'Synthetic delivery'})
order=market.order(buyer,product.id,str(uuid.uuid4()))
market.submit_payment(buyer,order.id,'https://cdn.discordapp.com/attachments/1/2/test.png')
def approve(_):
    try:
        market.review_payment(admin,order.id,True)
        return True
    except DomainError:
        return False
with ThreadPoolExecutor(max_workers=4) as pool:
    assert sum(pool.map(approve,range(4))) == 1
assert market.delivery(buyer,order.id)['delivery_value']=='Synthetic delivery'
market.delivered(buyer,order.id)
with db.sessions() as s:
    assert s.get(Order,order.id).state=='delivered'
    assert s.scalar(select(func.count()).select_from(Entitlement).where(Entitlement.order_id==order.id))==1
for table in Base.metadata.sorted_tables:
    str(CreateTable(table).compile(dialect=postgresql.dialect()))
print('PostgreSQL 17 smoke passed: schema, configuration, paid order, 4 concurrent approvals (1 success), entitlement and delivery.')
db.engine.dispose()
