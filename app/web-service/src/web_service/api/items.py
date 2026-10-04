from fastapi import APIRouter
from web_service.scheme.item import Item

router = APIRouter(prefix="/items")


@router.get("/{item_id}", tags=["items"])
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@router.put("/{item_id}", tags=["items"])
def update_item(item_id: int, item: Item):
    return {"item_name": item.name, "item_id": item_id}
