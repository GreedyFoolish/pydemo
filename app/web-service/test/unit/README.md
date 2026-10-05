# 单元测试覆盖说明

> 运行命令：`make test-unit` 或 `pytest test/unit/ -v`
> 当前共 **179** 个测试用例，全部通过。

---

## 1. Schema 校验（`test/unit/schema/`）

验证 Pydantic DTO 的字段约束、默认值、类型转换、循环引用处理。

### `test_product_schema.py` — Product 相关 DTO

| 被测类 | 覆盖内容 |
|--------|---------|
| `ProductCreate` | name 必填 + 长度边界（1~200）、description 默认为空串（0~2000）、brand 可选（1~100）、category_ids 默认为空列表、extra 字段忽略 |
| `ProductUpdate` | 所有字段可选支持部分更新、校验规则与 Create 一致 |
| `ProductResponse` | 必填字段完整性、brand 默认 None、description 默认空串、`from_attributes=True` 从 ORM 对象构造、extra 字段忽略 |
| `ProductResponseDetail` | categories 和 skus 关联列表默认为空、携带关联对象时类型正确 |

### `test_category_schema.py` — Category 相关 DTO

| 被测类 | 覆盖内容 |
|--------|---------|
| `CategoryCreate` | name 必填 + 长度边界（1~50）、description 默认为空串（0~2000） |
| `CategoryUpdate` | 所有字段可选、校验规则与 Create 一致 |
| `CategoryResponse` | 必填字段完整性、description 默认空串、`from_attributes=True` |
| `CategoryResponseDetail` | products 关联列表默认为空、前向引用 `list["ProductResponse"]` 正常解析、`model_rebuild()` 无异常 |

### `test_sku_schema.py` — Sku 相关 DTO

| 被测类 | 覆盖内容 |
|--------|---------|
| `SkuCreate` | product_id > 0、sku_code 长度边界（1~50）、price 精度约束（gt=0, max_digits=12, decimal_places=2）、stock ≥ 0 且默认 0、attrs 必须为 dict、image_url 长度边界（1~500） |
| `SkuUpdate` | 所有字段可选、price/stock/sku_code 校验规则与 Create 一致 |
| `SkuResponse` | Decimal price 精确传递、`from_attributes=True`、stock 默认 0 |
| `SkuResponseDetail` | product 关联默认 None、前向引用 `"ProductResponse | None"` 正常解析 |

---

## 2. 异常处理（`test/unit/exception/`）

验证 BusinessException 构造、ErrorCode 映射、消息提取、全局异常处理器输出格式。

### `test_base.py` — BusinessException 与 ErrorCode

| 测试组 | 覆盖内容 |
|--------|---------|
| 构造函数 | 仅 error_code（message fallback 到 default_message）、显式 message 覆盖、detail 传递、original_error 包装、所有关键字参数组合 |
| `__str__` 格式化 | 无 original_error 时 `[code] message`、有 original_error 时追加 `caused by: 类型: 消息` |
| ErrorCode 属性 | 10 个常用 ErrorCode 的 code / http_status 三元组拆解正确 |
| ErrorCode `__str__` | 返回 code 字符串（如 `str(ErrorCode.NOT_FOUND) == "404001"`） |

### `test_mapping.py` — resolve_error_code 三层查找

| 查找层级 | 覆盖内容 |
|---------|---------|
| BusinessException | 直接返回自身 error_code |
| HTTPException | 12 种状态码精细映射（400/401/403/404/405/409/422/429/500/502/503/504）、未知状态码回退 BAD_REQUEST |
| 其他异常 MRO 遍历 | RequestValidationError → VALIDATION_ERROR、IntegrityError → DB_ERROR、SQLAlchemyError → DB_ERROR、自定义异常 → INTERNAL_ERROR 兜底、普通 ValueError → INTERNAL_ERROR |
| 映射表完整性 | 所有 HTTP 状态码条目可查、IntegrityError 在 SQLAlchemyError 之前（具体 → 通用）、EXCEPTION_ERROR_CODE_MAP 包含 Exception 兜底 |

### `test_extractors.py` — extract_message / extract_detail

| 异常类型 | 覆盖内容 |
|---------|---------|
| HTTPException（str detail） | 直接返回 detail 字符串 |
| HTTPException（dict/detail） | 转 JSON 字符串保留结构 |
| HTTPException（list detail） | 转 JSON 字符串 |
| HTTPException（detail=None） | 使用 ErrorCode.default_message 兜底 |
| RequestValidationError | 拼接多字段错误 `loc: msg; loc: msg`、根级错误（loc 为空）直接返回 msg、空 errors 使用 fallback |
| 其他异常 | `str(exc)` 提取、空 str 使用 fallback |
| extract_detail | HTTPException 返回 `status_code=xxx`、携带 headers 时追加、非 HTTP 异常返回空串 |

### `test_handlers.py` — exception_handler 统一响应

| 输入异常 | 覆盖内容 |
|---------|---------|
| BusinessException | 响应体 `{code, data: null, message, request_id}` 格式正确、status_code 取自 error_code.http_status、X-Request-ID header 正确、携带 original_error 不影响响应 |
| HTTPException | 经 resolve_error_code + extract_message 生成完整响应 |
| RequestValidationError | status_code=422、message 为拼接后的字段错误信息 |
| 通用异常（ValueError） | status_code=500、message 为 str(exc) |
| request.state 缺失 request_id | getattr fallback 返回空串，不抛异常 |

---

## 3. OpenAPI Schema 转换（`test/unit/test_openapi.py`）

### UnifiedResponse 模型
- 成功响应 / 错误响应（data=null）/ data 为列表 / 必填字段校验 / data 可为 null

### 包装函数
- `_wrap_schema_in_unified_response`：原始 schema 为 $ref 引用、内联定义、null 类型时正确包装
- `_wrap_content_schema`：单媒体类型 / 多媒体类型 / 无 schema 键跳过 / 就地修改不抛异常
- `_should_wrap`：仅 `/api/` 前缀路径返回 True，`/docs`、`/openapi.json` 等返回 False
- `_wrap_error_response`：错误响应 data 固定为 null schema，与成功响应区分

### 完整转换 `_transform_openapi_schema`
- `/api/` 路径的 200 响应包装进 UnifiedResponse
- `/api/` 路径的 4xx/5xx 响应使用 error schema（data=null）
- 非 `/api/` 路径保持原样
- 204 No Content 跳过
- 非 HTTP 方法键（如 parameters）不被修改
- 空 paths / 无 content 的响应不抛异常

### setup_custom_openapi 注册流程
- 覆盖 app.openapi 方法
- 自定义 app.openapi() 返回已包装的 dict
- `/api/` 路径被包装、非 `/api/` 路径不被包装
- app.openapi_schema 缓存避免重复计算
- 显式传入 title/version/description 覆盖 app 默认值、未传时 fallback 到 app 属性
