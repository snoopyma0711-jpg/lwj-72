from app.data.demo_data import init_demo_data
from app.services import wave_service
from app.database import db

init_demo_data()
record = wave_service.generate_waves(trigger='test')

print('波次概览:')
for wid, wave in sorted(db.waves.items()):
    print(f'  {wave.wave_id}: {wave.status.value}, {len(wave.store_ids)}家门店')
    for sid in wave.store_ids:
        store = db.stores[sid]
        print(f'    - {store.store_name} (优先级{store.priority})')

print()
pending = [r for r in db.requests.values() if r.status.value == 'pending']
print(f'待处理需求数: {len(pending)}')
for req in pending:
    store = db.stores[req.store_id]
    print(f'  - {store.store_name}: {len(req.items)}种商品')

print()
print('库存状态:')
for pid, inv in db.inventory.items():
    product = db.products[pid]
    pct = inv.available_quantity / inv.total_quantity * 100 if inv.total_quantity > 0 else 0
    status = "紧张" if pct < 30 else "充足"
    print(f'  {product.product_name}: 总{inv.total_quantity}, 锁定{inv.locked_quantity}, 可用{inv.available_quantity} ({status})')
