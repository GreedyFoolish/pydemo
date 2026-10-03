from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/",
    tags=["default"],
    summary="Hello",
    description="默认路由",
)
def read_root():
    return {"Hello": "World"}
