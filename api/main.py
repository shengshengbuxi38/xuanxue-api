"""
玄学命理 API — FastAPI 路由层
仅做薄壳包装，所有核心逻辑直接复用 modules/ 中的现有代码。
"""
import os
import sys
import logging
from typing import Optional
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

# ── 路径配置：同时支持 "uvicorn api.main:app" 和 "cd api && uvicorn main:app" ──
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
for p in (_HERE, _PROJECT_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=False)

# ── 直接复用现有模块（零修改） ──
from modules.bazi_calc import get_bazi, bazi_to_text, get_two_bazi_match
from modules.geo_data import get_provinces, get_cities, get_districts, get_longitude
from modules.ai_analyzer import (
    analyze_bazi, deep_analysis, predict_events, match_bazi, divination,
)
from modules.knowledge_base import KnowledgeBase
from modules.bazi_db import CATEGORIES

from database import (
    get_conn, init_db, get_user_by_username, create_user,
    get_user_id_by_name, get_record_count, get_records_by_user,
    add_record_db, update_record_db, delete_record_db, get_record_by_id_db,
    log_action, add_feedback, FEEDBACK_CATEGORIES,
    add_prediction, get_predictions_by_user, delete_prediction,
    PREDICTION_TYPES,
)
from auth import (
    hash_password, verify_password,
    create_access_token, decode_access_token,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════
# Pydantic 请求/响应模型
# ═══════════════════════════════════════

class BaziInput(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    gender: int = Field(..., ge=0, le=1)  # 1=男 0=女
    longitude: Optional[float] = None


class BaziMatchInput(BaseModel):
    person1: BaziInput
    person2: BaziInput
    match_type: str = "婚配"


class DivinationInput(BaseModel):
    numbers: str = Field(..., min_length=1)
    question: str = ""


class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=6, max_length=64)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RecordInput(BaseModel):
    name: str = Field(..., min_length=1)
    category: str
    gender: int = Field(..., ge=0, le=1)
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    longitude: Optional[float] = None
    province: str = ""
    city: str = ""
    district: str = ""


class RecordUpdateInput(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    gender: Optional[int] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    longitude: Optional[float] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None


class FeedbackInput(BaseModel):
    category: str = "建议"
    content: str = Field(..., min_length=1, max_length=1000)


class PredictionInput(BaseModel):
    type: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    detail: str = ""


# ═══════════════════════════════════════
# 认证依赖
# ═══════════════════════════════════════

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """从 JWT 中提取用户名，失败返回 401"""
    try:
        payload = decode_access_token(credentials.credentials)
        return payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的 token",
        )


# ═══════════════════════════════════════
# 应用生命周期
# ═══════════════════════════════════════

_kb = KnowledgeBase()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    books_dir = os.path.join(_PROJECT_ROOT, "data", "books")
    try:
        count = _kb.build_index(books_dir)
        logger.info("知识库索引完成，共 %d 个文档片段", count)
    except UnicodeDecodeError as e:
        logger.warning("知识库部分文件编码异常，跳过: %s", e)
    yield


app = FastAPI(title="玄学命理 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════
# 认证接口
# ═══════════════════════════════════════

@app.post("/api/auth/register", response_model=TokenResponse)
def register(user: UserRegister):
    conn = get_conn()
    try:
        if get_user_by_username(conn, user.username):
            raise HTTPException(status_code=400, detail="用户名已存在")
        create_user(conn, user.username, hash_password(user.password))
        token = create_access_token({"sub": user.username})
        return TokenResponse(access_token=token)
    finally:
        conn.close()


@app.post("/api/auth/login", response_model=TokenResponse)
def login(user: UserLogin):
    conn = get_conn()
    try:
        db_user = get_user_by_username(conn, user.username)
        if not db_user or not verify_password(user.password, db_user["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        token = create_access_token({"sub": user.username})
        return TokenResponse(access_token=token)
    finally:
        conn.close()


# ═══════════════════════════════════════
# 八字排盘（公开 — 纯计算，无副作用）
# ═══════════════════════════════════════

@app.post("/api/bazi/calculate")
def calculate_bazi(req: BaziInput):
    """八字排盘（直接复用 modules.bazi_calc.get_bazi）"""
    return get_bazi(
        req.year, req.month, req.day, req.hour, req.minute, req.gender, req.longitude,
    )


# ═══════════════════════════════════════
# AI 分析（需登录 — 每次调用消耗 API 额度）
# ═══════════════════════════════════════

@app.post("/api/bazi/deep-analysis")
async def do_deep_analysis(req: BaziInput, _user=Depends(get_current_user)):
    """深度分析（日主、喜忌神、财富、一生综评+MBTI）"""
    bazi_data = get_bazi(
        req.year, req.month, req.day, req.hour, req.minute, req.gender, req.longitude,
    )
    bazi_text = bazi_to_text(bazi_data)
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, _user)
        result = await run_in_threadpool(deep_analysis, bazi_text)
        log_action(conn, user_id, "AI深度分析", bazi_data["raw_string"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 服务异常: {e}")
    finally:
        conn.close()
    return {"analysis": result, "bazi_data": bazi_data}


@app.post("/api/bazi/analyze")
async def do_analyze(req: BaziInput, _user=Depends(get_current_user)):
    """AI 命理分析"""
    bazi_data = get_bazi(
        req.year, req.month, req.day, req.hour, req.minute, req.gender, req.longitude,
    )
    bazi_text = bazi_to_text(bazi_data)
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, _user)
        result = await run_in_threadpool(analyze_bazi, bazi_text)
        log_action(conn, user_id, "AI命理分析", bazi_data["raw_string"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 服务异常: {e}")
    finally:
        conn.close()
    return {"analysis": result}


@app.post("/api/bazi/predict-events")
async def do_predict(
    req: BaziInput,
    target_year: Optional[int] = Query(None),
    _user=Depends(get_current_user),
):
    """大运流年事件预测"""
    bazi_data = get_bazi(
        req.year, req.month, req.day, req.hour, req.minute, req.gender, req.longitude,
    )
    bazi_text = bazi_to_text(bazi_data)
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, _user)
        result = await run_in_threadpool(predict_events, bazi_text, target_year)
        detail = f"year={target_year}" if target_year else "综合分析"
        log_action(conn, user_id, "大运流年预测", detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 服务异常: {e}")
    finally:
        conn.close()
    return {"analysis": result}


@app.post("/api/bazi/match")
async def do_match(req: BaziMatchInput, _user=Depends(get_current_user)):
    """八字合盘分析"""
    bazi1 = get_bazi(
        req.person1.year, req.person1.month, req.person1.day,
        req.person1.hour, req.person1.minute, req.person1.gender,
        req.person1.longitude,
    )
    bazi2 = get_bazi(
        req.person2.year, req.person2.month, req.person2.day,
        req.person2.hour, req.person2.minute, req.person2.gender,
        req.person2.longitude,
    )
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, _user)
        result = await run_in_threadpool(
            match_bazi, bazi_to_text(bazi1), bazi_to_text(bazi2), req.match_type,
        )
        log_action(conn, user_id, "八字匹配", f"{bazi1['raw_string']} vs {bazi2['raw_string']} [{req.match_type}]")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 服务异常: {e}")
    finally:
        conn.close()
    return {"analysis": result, "match_data": get_two_bazi_match(bazi1, bazi2)}


# ═══════════════════════════════════════
# 数字起卦（需登录）
# ═══════════════════════════════════════

@app.post("/api/divination")
async def do_divination(req: DivinationInput, _user=Depends(get_current_user)):
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, _user)
        result = await run_in_threadpool(divination, req.numbers, req.question)
        log_action(conn, user_id, "数字起卦", f"数字={req.numbers} 问题={req.question}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 服务异常: {e}")
    finally:
        conn.close()
    return {"analysis": result}


# ═══════════════════════════════════════
# 地理数据（公开 — 纯查询）
# ═══════════════════════════════════════

@app.get("/api/geo/provinces")
def list_provinces():
    return {"provinces": get_provinces()}


@app.get("/api/geo/cities")
def list_cities(province: str):
    return {"cities": get_cities(province)}


@app.get("/api/geo/districts")
def list_districts(province: str, city: str):
    return {"districts": get_districts(province, city)}


@app.get("/api/geo/longitude")
def get_lon(province: str, city: str):
    return {"longitude": get_longitude(province, city)}


# ═══════════════════════════════════════
# 八字档案库（需登录 — 用户数据隔离）
# ═══════════════════════════════════════

@app.get("/api/archive/records")
def list_records(user: str = Depends(get_current_user), category: str = None):
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, user)
        records = get_records_by_user(conn, user_id, category)
        return {"records": records}
    finally:
        conn.close()


@app.post("/api/archive/records")
def create_record(req: RecordInput, user: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, user)
        # 免费限额检查（同名覆盖不受限）
        is_update = any(
            r["name"] == req.name for r in get_records_by_user(conn, user_id)
        )
        if not is_update and get_record_count(conn, user_id) >= 2:
            raise HTTPException(status_code=403, detail="免费版最多保存2条记录")
        record_id = add_record_db(
            conn, user_id,
            req.name, req.category, req.gender,
            req.year, req.month, req.day, req.hour, req.minute,
            req.longitude, req.province, req.city, req.district,
        )
        return {"id": record_id, "status": "ok"}
    finally:
        conn.close()


@app.put("/api/archive/records/{record_id}")
def update_record(
    record_id: str, req: RecordUpdateInput, user: str = Depends(get_current_user),
):
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, user)
        if not get_record_by_id_db(conn, record_id, user_id):
            raise HTTPException(status_code=404, detail="记录不存在")
        update_record_db(conn, record_id, user_id, **req.model_dump(exclude_none=True))
        return {"status": "ok"}
    finally:
        conn.close()


@app.delete("/api/archive/records/{record_id}")
def remove_record(record_id: str, user: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, user)
        delete_record_db(conn, record_id, user_id)
        return {"status": "ok"}
    finally:
        conn.close()


# ═══════════════════════════════════════
# 知识库（浏览公开，问答需登录）
# ═══════════════════════════════════════

@app.get("/api/knowledge/books")
def list_books():
    try:
        return {"books": _kb.get_book_list()}
    except UnicodeDecodeError:
        # 个别书籍文件非 UTF-8 编码，降级为仅返回文件名
        import os
        books_dir = os.path.join(_PROJECT_ROOT, "data", "books")
        if not os.path.exists(books_dir):
            return {"books": []}
        return {
            "books": [
                {"filename": f, "title": os.path.splitext(f)[0], "preview": ""}
                for f in os.listdir(books_dir)
                if f.endswith((".txt", ".md"))
            ]
        }


@app.get("/api/knowledge/books/{filename}")
def read_book(filename: str):
    try:
        content = _kb.get_book_content(filename)
    except UnicodeDecodeError:
        raise HTTPException(status_code=500, detail="该文件编码不支持，请转为 UTF-8")
    if content == "文件不存在":
        raise HTTPException(status_code=404, detail="书籍不存在")
    return {"content": content}


@app.post("/api/knowledge/search")
def search_kb(body: dict = None):
    query = (body or {}).get("query", "")
    if not query:
        raise HTTPException(status_code=422, detail="缺少 query 参数")
    top_k = (body or {}).get("top_k", 5)
    try:
        return {"results": _kb.search(query, top_k)}
    except UnicodeDecodeError:
        return {"results": [], "warning": "部分书籍文件编码异常，索引不完整"}


@app.post("/api/knowledge/qa")
async def knowledge_qa(body: dict, _user=Depends(get_current_user)):
    question = body.get("question", "")
    if not question:
        raise HTTPException(status_code=422, detail="缺少 question 参数")
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, _user)
        answer = await run_in_threadpool(_kb.qa, question)
        log_action(conn, user_id, "知识库问答", question[:100])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 服务异常: {e}")
    finally:
        conn.close()
    return {"answer": answer}


# ═══════════════════════════════════════
# ═══════════════════════════════════════
# 用户反馈
# ═══════════════════════════════════════

@app.post("/api/feedback")
def submit_feedback(req: FeedbackInput, user: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, user)
        add_feedback(conn, user_id, req.category, req.content)
    finally:
        conn.close()
    return {"status": "ok"}


@app.get("/api/feedback/categories")
def list_feedback_categories():
    return {"categories": FEEDBACK_CATEGORIES}


# ═══════════════════════════════════════
# AI 预测记录（需登录）

@app.get("/api/predictions")
def list_predictions(user: str = Depends(get_current_user), type: str = None):
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, user)
        records = get_predictions_by_user(conn, user_id, type)
        return {"records": records}
    finally:
        conn.close()


@app.post("/api/predictions")
def create_prediction(req: PredictionInput, user: str = Depends(get_current_user)):
    if req.type not in PREDICTION_TYPES:
        raise HTTPException(status_code=400, detail=f"无效类型: {req.type}")
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, user)
        add_prediction(conn, user_id, req.type, req.title, req.content, req.detail)
    finally:
        conn.close()
    return {"status": "ok"}


@app.delete("/api/predictions/{prediction_id}")
def remove_prediction(prediction_id: int, user: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        user_id = get_user_id_by_name(conn, user)
        delete_prediction(conn, prediction_id, user_id)
    finally:
        conn.close()
    return {"status": "ok"}


# ═══════════════════════════════════════
# 健康检查
# ═════════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
