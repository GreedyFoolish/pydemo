"""Service 层功能演示脚本，按步骤验证泛型 BaseService + 子类的核心用法。

对应业务场景：分类 → 产品（关联分类）→ SKU（关联产品）的完整 CRUD 链路。

运行前提：需要 PostgreSQL 数据库且已执行 alembic upgrade head 创建表。
    uv run --package web-service python test/test_service.py

与参考 main.py 的差异：
    - 使用泛型 BaseService 统一接口（create / update / delete / get_by_id / list_paged）
    - 返回 None 的查询方法（get_by_id / get_detail）
    - create 内部已 flush + refresh，拿到自增 ID 和 server_default 字段
"""

import asyncio
from decimal import Decimal

from sqlalchemy import delete, text
from web_service.core.database import get_session_factory
from web_service.model.association import product_category
from web_service.model.category import Category
from web_service.model.product import Product
from web_service.model.sku import Sku
from web_service.schema.category import CategoryCreate, CategoryUpdate
from web_service.schema.product import ProductCreate, ProductUpdate
from web_service.schema.sku import SkuCreate, SkuUpdate
from web_service.service.category import CategoryService
from web_service.service.product import ProductService
from web_service.service.sku import SkuService


async def main():
    async with get_session_factory()() as session:
        # ========== 0. 清理旧数据，保证幂等 ==========
        print("========== 0. 清理旧数据 ==========")
        await session.execute(delete(Sku))
        await session.execute(delete(product_category))
        await session.execute(delete(Product))
        await session.execute(delete(Category))
        # PostgreSQL 重置序列（让下一条自增 ID 从 1 开始）
        for seq in ("sku_id_seq", "product_id_seq", "category_id_seq"):
            await session.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))
        await session.flush()
        print("旧数据已清理\n")

        # ========== 1. 创建分类 ==========
        print("========== 1. 创建分类 ==========")
        category_svc = CategoryService(session)

        c1 = await category_svc.create(
            CategoryCreate(name="电子产品", description="手机、电脑等")
        )
        c2 = await category_svc.create(CategoryCreate(name="图书"))
        c3 = await category_svc.create(CategoryCreate(name="服装"))

        assert c1.id == 1, f"c1.id 应为 1，实际 {c1.id}"
        # Category 只有 IDMixin，没有 TimestampMixin，所以没有 created_at
        print(f"[{c1.id}] {c1.name} ({c1.description})")
        print(f"[{c2.id}] {c2.name}")
        print(f"[{c3.id}] {c3.name}")
        print()

        # ========== 2. 分页查询分类（list_paged） ==========
        print("========== 2. 分页查询分类 ==========")
        page = await category_svc.list_paged(page=1, page_size=10)
        assert page.total == 3, f"总数应为 3，实际 {page.total}"
        assert page.total_pages == 1, f"总页数应为 1，实际 {page.total_pages}"
        print(f"共 {page.total} 条, {page.total_pages} 页, 当前页 {page.page}")
        for cat in page.items:
            print(f"  [{cat.id}] {cat.name}")
        print()

        # ========== 3. 创建产品并关联分类 ==========
        print("========== 3. 创建产品并关联分类 ==========")
        product_svc = ProductService(session)

        p1 = await product_svc.create(
            ProductCreate(
                name="iPhone 16",
                description="苹果最新款手机",
                brand="Apple",
                category_ids=[c1.id],
            )
        )
        p2 = await product_svc.create(
            ProductCreate(
                name="MacBook Pro",
                description="苹果笔记本电脑",
                brand="Apple",
                category_ids=[c1.id],
            )
        )
        p3 = await product_svc.create(
            ProductCreate(
                name="Python入门教程",
                description="零基础学Python",
                brand="人民邮电出版社",
                category_ids=[c2.id],
            )
        )

        assert p1.id == 1
        assert p1.created_at is not None
        print(f"[{p1.id}] {p1.name} ({p1.brand}) created_at={p1.created_at}")
        print(f"[{p2.id}] {p2.name}")
        print(f"[{p3.id}] {p3.name}")
        print()

        # ========== 4. 创建 SKU（外键 product_id 校验） ==========
        print("========== 4. 创建 SKU ==========")
        sku_svc = SkuService(session)

        s1 = await sku_svc.create(
            SkuCreate(
                product_id=p1.id,
                sku_code="IP16-128-BLK",
                price=Decimal("6999.00"),
                stock=100,
                attrs={"颜色": "黑色", "存储": "128G"},
                image_url="/images/ip16-blk.jpg",
            )
        )
        s2 = await sku_svc.create(
            SkuCreate(
                product_id=p1.id,
                sku_code="IP16-256-WHT",
                price=Decimal("7999.00"),
                stock=50,
                attrs={"颜色": "白色", "存储": "256G"},
                image_url="/images/ip16-wht.jpg",
            )
        )
        s3 = await sku_svc.create(
            SkuCreate(
                product_id=p2.id,
                sku_code="MBP14-M3-16G",
                price=Decimal("12999.00"),
                stock=30,
                attrs={"尺寸": "14寸", "芯片": "M3", "内存": "16G"},
                image_url="/images/mbp14.jpg",
            )
        )

        assert s1.id == 1
        assert s1.product_id == p1.id
        print(f"[{s1.id}] {s1.sku_code} ¥{s1.price} 库存:{s1.stock} attrs={s1.attrs}")
        print(f"[{s2.id}] {s2.sku_code} ¥{s2.price}")
        print(f"[{s3.id}] {s3.sku_code} ¥{s3.price}")
        print()

        # ========== 5. 查询 + 详情 ==========
        print("========== 5. 查询 + 详情 ==========")

        # get_by_id：返回 ORM 或 None
        found = await category_svc.get_by_id(c1.id)
        assert found is not None
        print(f"get_by_id 找到: [{found.id}] {found.name}")

        not_found = await category_svc.get_by_id(999)
        assert not_found is None
        print("get_by_id(999) → None")

        # get_detail：返回带关联的 Response DTO 或 None
        # 注意：需要用全新的 session（identity map 干净）才能正确展示 selectinload 预加载的关联
        # 在同一个 session 里，旧的 identity map 实例会被返回，关联状态可能与 flush 后的内存状态一致
        detail = await product_svc.get_detail(p1.id)
        assert detail is not None
        print(
            f"ProductDetail: [{detail.id}] {detail.name} "
            f"分类数={len(detail.categories)} SKU数={len(detail.skus)}"
        )
        for sku in detail.skus:
            print(f"    SKU: {sku.sku_code} | ¥{sku.price} | 库存:{sku.stock}")

        category_detail = await category_svc.get_detail(c1.id)
        assert category_detail is not None
        print(
            f"CategoryDetail: [{category_detail.id}] {category_detail.name} "
            f"产品数={len(category_detail.products)}"
        )
        for prod in category_detail.products:
            print(f"    产品: [{prod.id}] {prod.name}")
        print()

        # ========== 6. 更新 SKU 库存 ==========
        print("========== 6. 更新 SKU 库存 ==========")
        before_stock = s1.stock
        updated = await sku_svc.update(s1.id, SkuUpdate(stock=80))
        assert updated.stock == 80
        # Sku 只有 IDMixin，没有 TimestampMixin，所以没有 updated_at
        print(f"{s1.sku_code} 库存: {before_stock} → {updated.stock}")
        print()

        # ========== 7. 更新产品（含关联分类变更） ==========
        print("========== 7. 更新产品（含关联分类变更） ==========")
        before_desc = p2.description
        updated_product = await product_svc.update(
            p2.id,
            ProductUpdate(
                description="2024款MacBook Pro M3芯片 笔记本电脑",
                category_ids=[c2.id, c3.id],  # 换到图书+服装
            ),
        )
        assert updated_product.description != before_desc
        print(f"描述: {before_desc[:20]}... → {updated_product.description}")

        # 验证关联已变更
        new_detail = await product_svc.get_detail(p2.id)
        assert new_detail is not None
        assert len(new_detail.categories) == 2
        category_names = [c.name for c in new_detail.categories]
        print(f"分类已变更为: {category_names}")
        print()

        # ========== 8. 更新分类 ==========
        print("========== 8. 更新分类 ==========")
        updated_cat = await category_svc.update(
            c3.id, CategoryUpdate(description="男装、女装、童装等")
        )
        print(f"[{c3.id}] 描述已更新: {updated_cat.description}")
        print()

        # ========== 9. count + list + filters ==========
        print("========== 9. count + list + filters ==========")
        total = await category_svc.count()
        print(f"全部分类数: {total}")

        # 按字段过滤 list
        filtered = await sku_svc.list(product_id=p1.id)
        print(f"product_id={p1.id} 的 SKU 数: {len(filtered)}")

        # list_paged 按 brand 过滤产品
        apple_products = await product_svc.list_paged(brand="Apple", page_size=10)
        print(f"brand=Apple 的产品数: {apple_products.total}")
        for item in apple_products.items:
            print(f"  [{item.id}] {item.name}")
        print()

        # ========== 10. 不存在的记录 ==========
        print("========== 10. 不存在的记录 ==========")
        none1 = await product_svc.get_by_id(999)
        print(f"Product get_by_id(999): {none1}")

        none2 = await category_svc.get_detail(999)
        print(f"Category get_detail(999): {none2}")
        print()

        # ========== 11. 删除 ==========
        print("========== 11. 删除 ==========")
        await sku_svc.delete(s3.id)
        print(f"SKU [{s3.id}] 已删除")

        # 验证已删除
        after = await sku_svc.get_by_id(s3.id)
        assert after is None
        print(f"get_by_id({s3.id}) → None")
        print()

        # ========== 12. 事务提交 ==========
        await session.commit()
        print("========== 全部 12 个步骤测试通过 ==========")


if __name__ == "__main__":
    asyncio.run(main())
