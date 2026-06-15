from datetime import datetime, timedelta

from app.database import db
from app.models import Store, Product, InventoryItem


def init_demo_data():
    stores = [
        Store(store_id="STORE-001", store_name="星巴克国贸店", priority=1),
        Store(store_id="STORE-002", store_name="星巴克三里屯店", priority=2),
        Store(store_id="STORE-003", store_name="星巴克望京店", priority=3),
        Store(store_id="STORE-004", store_name="星巴克五道口店", priority=4),
        Store(store_id="STORE-005", store_name="星巴克中关村店", priority=5),
        Store(store_id="STORE-006", store_name="星巴克西单店", priority=2),
    ]
    for s in stores:
        db.add_store(s)

    products = [
        Product(product_id="PROD-001", product_name="阿拉比卡咖啡豆", unit="袋"),
        Product(product_id="PROD-002", product_name="全脂牛奶", unit="箱"),
        Product(product_id="PROD-003", product_name="燕麦奶", unit="箱"),
        Product(product_id="PROD-004", product_name="香草糖浆", unit="瓶"),
        Product(product_id="PROD-005", product_name="焦糖糖浆", unit="瓶"),
        Product(product_id="PROD-006", product_name="纸杯(大)", unit="包"),
        Product(product_id="PROD-007", product_name="纸杯(中)", unit="包"),
        Product(product_id="PROD-008", product_name="杯盖", unit="包"),
    ]
    for p in products:
        db.add_product(p)

    inventory = [
        InventoryItem(product_id="PROD-001", total_quantity=30),
        InventoryItem(product_id="PROD-002", total_quantity=45),
        InventoryItem(product_id="PROD-003", total_quantity=20),
        InventoryItem(product_id="PROD-004", total_quantity=35),
        InventoryItem(product_id="PROD-005", total_quantity=30),
        InventoryItem(product_id="PROD-006", total_quantity=60),
        InventoryItem(product_id="PROD-007", total_quantity=70),
        InventoryItem(product_id="PROD-008", total_quantity=100),
    ]
    for inv in inventory:
        db.set_inventory(inv)

    demo_requests = [
        ("STORE-001", {
            "PROD-001": 10, "PROD-002": 15, "PROD-003": 8,
            "PROD-004": 5, "PROD-006": 12, "PROD-008": 20
        }),
        ("STORE-002", {
            "PROD-001": 8, "PROD-002": 12, "PROD-003": 6,
            "PROD-005": 7, "PROD-007": 10, "PROD-008": 15
        }),
        ("STORE-003", {
            "PROD-001": 12, "PROD-002": 10, "PROD-004": 8,
            "PROD-006": 15, "PROD-007": 18
        }),
        ("STORE-004", {
            "PROD-001": 6, "PROD-003": 10, "PROD-005": 5,
            "PROD-006": 8, "PROD-008": 12
        }),
        ("STORE-005", {
            "PROD-002": 20, "PROD-003": 5, "PROD-004": 10,
            "PROD-007": 12, "PROD-008": 18
        }),
        ("STORE-006", {
            "PROD-001": 9, "PROD-002": 14, "PROD-003": 7,
            "PROD-005": 6, "PROD-006": 10, "PROD-007": 8, "PROD-008": 14
        }),
    ]

    base_time = datetime.now() - timedelta(minutes=30)
    for i, (store_id, items) in enumerate(demo_requests):
        req_id = db.next_request_id()
        from app.models import ReplenishmentRequest, RequestStatus
        req = ReplenishmentRequest(
            request_id=req_id,
            store_id=store_id,
            items=items,
            status=RequestStatus.PENDING,
            created_at=base_time + timedelta(minutes=i * 3),
            updated_at=base_time + timedelta(minutes=i * 3)
        )
        db.add_request(req)

    return {
        "stores": len(stores),
        "products": len(products),
        "inventory_items": len(inventory),
        "requests": len(demo_requests),
    }
