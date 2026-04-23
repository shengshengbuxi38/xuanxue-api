"""八字库管理模块 - JSON 文件持久化存储"""

import os
import json
import uuid
from datetime import datetime

from modules.bazi_calc import get_bazi

# 分类列表
CATEGORIES = ["家人", "好友", "熟人", "下属", "上级", "客户", "供应商", "竞争对手", "投资对象", "自定义"]

# 版本限制：免费版最多存2条，None 表示无限制
MAX_RECORDS = None  # None = 无限制（收费版）

# 存储路径
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bazi_db.json")


def _ensure_db_file():
    """确保数据库文件存在"""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    if not os.path.exists(_DB_PATH):
        with open(_DB_PATH, "w", encoding="utf-8") as f:
            json.dump({"records": []}, f, ensure_ascii=False, indent=2)


def load_db():
    """加载八字库"""
    _ensure_db_file()
    with open(_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    """保存八字库"""
    with open(_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def add_record(name, category, year, month, day, hour, minute, gender, longitude, province, city, district):
    """新增一条八字记录，同名则覆盖，返回 (record, status)。status: 'ok' / 'limit_reached' / 'updated'"""
    db = load_db()

    # 同名覆盖：查找同名记录并更新
    for r in db["records"]:
        if r["name"] == name:
            # 检查数量限制（覆盖不增加数量，无需检查）
            r["category"] = category
            r["gender"] = gender
            r["year"] = year
            r["month"] = month
            r["day"] = day
            r["hour"] = hour
            r["minute"] = minute
            r["longitude"] = longitude
            r["province"] = province or ""
            r["city"] = city or ""
            r["district"] = district or ""
            r["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_db(db)
            return r, "updated"

    # 新增记录：检查数量限制
    if MAX_RECORDS is not None and len(db["records"]) >= MAX_RECORDS:
        return None, "limit_reached"

    record = {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "category": category,
        "gender": gender,
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute,
        "longitude": longitude,
        "province": province or "",
        "city": city or "",
        "district": district or "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db["records"].append(record)
    save_db(db)
    return record, "ok"


def update_record(record_id, **kwargs):
    """更新一条记录的字段"""
    db = load_db()
    for r in db["records"]:
        if r["id"] == record_id:
            for k, v in kwargs.items():
                if k in r:
                    r[k] = v
            r["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    save_db(db)


def delete_record(record_id):
    """删除一条记录"""
    db = load_db()
    db["records"] = [r for r in db["records"] if r["id"] != record_id]
    save_db(db)


def get_records(category=None):
    """获取记录列表，可按分类筛选"""
    db = load_db()
    records = db["records"]
    if category and category != "全部":
        records = [r for r in records if r["category"] == category]
    return records


def get_record_by_id(record_id):
    """按 ID 获取单条记录"""
    db = load_db()
    for r in db["records"]:
        if r["id"] == record_id:
            return r
    return None


def record_to_bazi(record):
    """将记录转为排盘参数并调用 get_bazi，返回 bazi_data"""
    return get_bazi(
        record["year"],
        record["month"],
        record["day"],
        record["hour"],
        record["minute"],
        record["gender"],
        record.get("longitude"),
    )


def record_label(record):
    """生成用于下拉框显示的标签"""
    gender_str = "男" if record["gender"] == 1 else "女"
    return f"{record['name']}（{record['category']}）| {record['year']}-{record['month']:02d}-{record['day']:02d} {gender_str}"
