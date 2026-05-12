import os, random, string
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from database import init_db, fetchone, fetchall, execute
from auth import verify_password, create_token, decode_token, hash_password

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Утилиты
def gen_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

async def get_active_sub(user_id: int):
    now = datetime.utcnow().isoformat()
    return await fetchone(
        """SELECT * FROM subscriptions WHERE user_id=? AND active=1
           AND (end_date IS NULL OR end_date > ?)""",
        (user_id, now)
    )

async def get_user_from_token(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Нет токена")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Токен недействителен")
    user = await fetchone("SELECT * FROM users WHERE id=?", (int(payload["sub"]),))
    if not user:
        raise HTTPException(401, "Пользователь не найден")
    return user

# Модели
class LoginBody(BaseModel):
    login: str
    password: str

class BindHwidBody(BaseModel):
    hwid: str

class VerifyCodeBody(BaseModel):
    username: str
    code: str

# 1. POST /api/login
@app.post("/api/login")
async def api_login(body: LoginBody):
    user = await fetchone("SELECT * FROM users WHERE username=?", (body.login,))
    if not user or not verify_password(body.password, user["password"]):
        raise HTTPException(401, detail={"success": False, "message": "Неверный логин или пароль"})
    if user["role"] == "blocked":
        raise HTTPException(403, detail={"success": False, "message": "Аккаунт заблокирован"})
    token = create_token(user["id"], user["username"])
    return {"success": True, "token": token}

# 2. GET /api/check
@app.get("/api/check")
async def api_check(hwid: str = Query(...), authorization: str | None = Header(None)):
    user = await get_user_from_token(authorization)
    sub = await get_active_sub(user["id"])
    hwid_bound = bool(user["hwid"])
    hwid_match = (user["hwid"] == hwid) if hwid_bound else False
    if not sub:
        return {"subscription_active": False, "hwid_bound": hwid_bound, "hwid_match": hwid_match}
    days_left = None
    if sub["end_date"]:
        delta = datetime.fromisoformat(sub["end_date"]) - datetime.utcnow()
        days_left = max(0, delta.days)
    return {"subscription_active": True, "plan": sub["plan"], "days_left": days_left, "hwid_bound": hwid_bound, "hwid_match": hwid_match}

# 3. POST /api/bind-hwid
@app.post("/api/bind-hwid")
async def api_bind_hwid(body: BindHwidBody, authorization: str | None = Header(None)):
    user = await get_user_from_token(authorization)
    if user["hwid"]:
        raise HTTPException(400, detail={"success": False, "message": "HWID уже привязан"})
    await execute("UPDATE users SET hwid=?, hwid_bind_date=? WHERE id=?", (body.hwid, datetime.utcnow().isoformat(), user["id"]))
    return {"success": True}

# 4. GET /api/download-dlc
@app.get("/api/download-dlc")
async def api_download_dlc(hwid: str = Query(...), authorization: str | None = Header(None)):
    user = await get_user_from_token(authorization)
    sub = await get_active_sub(user["id"])
    if not sub:
        raise HTTPException(403, detail={"success": False, "message": "Нет активной подписки"})
    if not user["hwid"]:
        await execute("UPDATE users SET hwid=?, hwid_bind_date=? WHERE id=?", (hwid, datetime.utcnow().isoformat(), user["id"]))
    elif user["hwid"] != hwid:
        raise HTTPException(403, detail={"success": False, "message": "HWID не совпадает"})
    dlc_path = os.path.join("static", "dlc.zip")
    if not os.path.exists(dlc_path):
        raise HTTPException(404, detail={"success": False, "message": "Файл не найден"})
    return FileResponse(dlc_path, media_type="application/zip", filename="dlc.zip")

# 5. POST /api/verify-telegram
@app.post("/api/verify-telegram")
async def api_verify_telegram(body: VerifyCodeBody):
    now = datetime.utcnow().isoformat()
    user = await fetchone("SELECT * FROM users WHERE username=?", (body.username,))
    if not user:
        raise HTTPException(404, detail={"success": False, "message": "Пользователь не найден"})
    rec = await fetchone("SELECT * FROM verification_codes WHERE user_id=? AND code=? AND expires>?", (user["id"], body.code, now))
    if not rec:
        raise HTTPException(400, detail={"success": False, "message": "Неверный или истёкший код"})
    await execute("DELETE FROM verification_codes WHERE id=?", (rec["id"],))
    return {"success": True, "telegram_id": user["telegram_id"], "telegram_username": user["telegram_username"]}

# 6. Внутренний endpoint для создания юзера
class CreateUserBody(BaseModel):
    username: str
    password: str

@app.post("/internal/create-user")
async def internal_create_user(body: CreateUserBody, x_internal_key: str | None = Header(None)):
    if x_internal_key != os.getenv("INTERNAL_KEY", "internal_secret"):
        raise HTTPException(403)
    existing = await fetchone("SELECT id FROM users WHERE username=?", (body.username,))
    if existing:
        raise HTTPException(400, detail="Пользователь уже существует")
    hashed = hash_password(body.password)
    await execute("INSERT INTO users (username, password) VALUES (?, ?)", (body.username, hashed))
    return {"success": True}
