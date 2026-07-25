"""
database.py — Complete database setup and operations
SQLite locally, PostgreSQL on Render. Auto-detects.
"""

import databases
import sqlalchemy
import secrets
import json
from datetime import datetime, timedelta
from config import DATABASE_URL, TIERS

# === SETUP ===
# SQLite needs aiosqlite, PostgreSQL needs asyncpg or psycopg2
db = databases.Database(DATABASE_URL)

metadata = sqlalchemy.MetaData()

# =====================
# USERS TABLE
# =====================
users = sqlalchemy.Table(
    "api_users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("email", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("api_key", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("plan", sqlalchemy.String, default="free"),
    sqlalchemy.Column("requests_used", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("requests_limit", sqlalchemy.Integer, default=50),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, server_default=sqlalchemy.func.now()),
    sqlalchemy.Column("reset_at", sqlalchemy.DateTime),  # When counter resets
    sqlalchemy.Column("stripe_id", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean, default=True),
)

# =====================
# ANALYSIS CACHE TABLE
# =====================
cache = sqlalchemy.Table(
    "analysis_cache",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("url_hash", sqlalchemy.String, index=True),  # MD5 of URL for fast lookup
    sqlalchemy.Column("url", sqlalchemy.String),
    sqlalchemy.Column("result_json", sqlalchemy.String),  # Full result as JSON string
    sqlalchemy.Column("depth", sqlalchemy.String, default="basic"),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, server_default=sqlalchemy.func.now()),
    sqlalchemy.Column("expires_at", sqlalchemy.DateTime),
)

# =====================
# API LOG TABLE (track all requests)
# =====================
api_logs = sqlalchemy.Table(
    "api_logs",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.Integer),
    sqlalchemy.Column("url_queried", sqlalchemy.String),
    sqlalchemy.Column("endpoint", sqlalchemy.String),
    sqlalchemy.Column("response_time_ms", sqlalchemy.Integer),
    sqlalchemy.Column("status", sqlalchemy.String, default="success"),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, server_default=sqlalchemy.func.now()),
)

# === CREATE TABLES ===
engine = sqlalchemy.create_engine(
    DATABASE_URL.replace("sqlite:///./", "sqlite:///") if DATABASE_URL.startswith("sqlite") else DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
metadata.create_all(engine)


# =====================
# USER FUNCTIONS
# =====================

async def create_user(email: str, plan: str = "free") -> dict:
    """New user register → API key generate"""
    api_key = f"biz_{secrets.token_urlsafe(32)}"
    tier_info = TIERS[plan]
    
    now = datetime.now()
    reset_at = now + timedelta(days=30)  # Reset counter after 30 days
    
    query = users.insert().values(
        email=email,
        api_key=api_key,
        plan=plan,
        requests_used=0,
        requests_limit=tier_info["requests_per_month"],
        reset_at=reset_at,
    )
    last_id = await db.execute(query)
    
    return {
        "id": last_id,
        "api_key": api_key,
        "plan": plan,
        "requests_limit": tier_info["requests_per_month"],
        "features": tier_info["features"],
        "data_depth": tier_info["data_depth"],
        "monthly_price": tier_info["price"],
        "message": f"Welcome! You're on the {plan} plan with {tier_info['requests_per_month']} monthly requests."
    }


async def get_user_by_key(api_key: str) -> dict | None:
    """Find user by API key"""
    query = users.select().where(
        (users.c.api_key == api_key) & (users.c.is_active == True)
    )
    result = await db.fetch_one(query)
    return dict(result) if result else None


async def check_and_increment_usage(api_key: str) -> dict:
    """Check if user can make request, then increment counter"""
    user = await get_user_by_key(api_key)
    
    if not user:
        return {"allowed": False, "reason": "Invalid API key"}
    
    # Check if counter should reset (monthly)
    now = datetime.now()
    if user["reset_at"] and now > user["reset_at"]:
        # Reset the counter!
        query = users.update().where(users.c.api_key == api_key).values(
            requests_used=0,
            reset_at=now + timedelta(days=30)
        )
        await db.execute(query)
        user["requests_used"] = 0
    
    # Unlimited plans
    if user["requests_limit"] == -1:
        query = users.update().where(users.c.api_key == api_key).values(
            requests_used=user["requests_used"] + 1
        )
        await db.execute(query)
        return {
            "allowed": True,
            "plan": user["plan"],
            "remaining": "unlimited",
            "features": TIERS[user["plan"]]["features"],
            "data_depth": TIERS[user["plan"]]["data_depth"],
        }
    
    # Check limit
    if user["requests_used"] >= user["requests_limit"]:
        return {
            "allowed": False,
            "reason": "Monthly limit reached",
            "plan": user["plan"],
            "used": user["requests_used"],
            "limit": user["requests_limit"],
            "upgrade_to": get_upgrade_suggestion(user["plan"]),
        }
    
    # Increment
    new_used = user["requests_used"] + 1
    remaining = user["requests_limit"] - new_used
    
    query = users.update().where(users.c.api_key == api_key).values(
        requests_used=new_used
    )
    await db.execute(query)
    
    return {
        "allowed": True,
        "plan": user["plan"],
        "remaining": remaining,
        "features": TIERS[user["plan"]]["features"],
        "data_depth": TIERS[user["plan"]]["data_depth"],
    }


def get_upgrade_suggestion(current_plan: str) -> str:
    """What plan should user upgrade to"""
    order = ["free", "pro", "business", "enterprise"]
    idx = order.index(current_plan)
    if idx < len(order) - 1:
        next_plan = order[idx + 1]
        return f"Upgrade to {next_plan} (${TIERS[next_plan]['price']}/mo) for {TIERS[next_plan]['requests_per_month']} requests"
    return "You're on the highest plan already"


async def check_feature(user_plan: str, feature: str) -> bool:
    """Check if a plan includes a feature"""
    return feature in TIERS[user_plan]["features"]


# =====================
# CACHE FUNCTIONS
# =====================

import hashlib

def url_hash(url: str) -> str:
    """Create hash for fast URL lookup"""
    return hashlib.md5(url.lower().strip().encode()).hexdigest()


async def save_cache(url: str, result: dict, depth: str):
    """Save analysis result to cache"""
    h = url_hash(url)
    expires = datetime.now() + timedelta(days=7)
    
    # Delete old cache for same URL+depth
    delete_query = cache.delete().where(
        (cache.c.url_hash == h) & (cache.c.depth == depth)
    )
    await db.execute(delete_query)
    
    # Insert new
    insert_query = cache.insert().values(
        url_hash=h,
        url=url,
        result_json=json.dumps(result),
        depth=depth,
        expires_at=expires,
    )
    await db.execute(insert_query)


async def get_cache(url: str, min_depth: str = "basic") -> dict | None:
    """Get cached result if it exists and is deep enough"""
    h = url_hash(url)
    depth_levels = {"basic": 0, "full": 1, "deep": 2, "maximum": 3}
    min_level = depth_levels.get(min_depth, 0)
    
    query = cache.select().where(
        (cache.c.url_hash == h) &
        (cache.c.expires_at > datetime.now())
    )
    results = await db.fetch_all(query)
    
    for row in results:
        row_level = depth_levels.get(row["depth"], 0)
        if row_level >= min_level:
            return json.loads(row["result_json"])
    
    return None


# =====================
# LOG FUNCTIONS
# =====================

async def log_request(user_id: int, url: str, endpoint: str, 
                      response_time_ms: int, status: str = "success"):
    """Log every API request (analytics for you)"""
    query = api_logs.insert().values(
        user_id=user_id,
        url_queried=url,
        endpoint=endpoint,
        response_time_ms=response_time_ms,
        status=status,
    )
    await db.execute(query)