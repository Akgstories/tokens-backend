import os
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from typing import Any, Optional

import razorpay
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from supabase import Client, create_client


APP_NAME = "Tokens Gifting Platform API"
APP_VERSION = "4.0.0"

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
PARTNER_TOKEN_SECRET = os.getenv("PARTNER_TOKEN_SECRET", "").strip() or secrets.token_urlsafe(48)
ADMIN_EMAILS = {
    x.strip().lower()
    for x in os.getenv("ADMIN_EMAILS", "").split(",")
    if x.strip()
}
ALLOWED_ORIGINS = [
    x.strip()
    for x in os.getenv(
        "ALLOWED_ORIGINS",
        "https://tokensforeveryone.in,https://www.tokensforeveryone.in,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if x.strip()
]

supabase: Optional[Client] = (
    create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
    else None
)
razorpay_client: Any = (
    razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET
    else None
)

app = FastAPI(
    title=APP_NAME,
    description="Secure backend services for Tokens, a gifting and personalization marketplace.",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def db() -> Client:
    if supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
        )
    return supabase


def bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token


async def current_user(authorization: Optional[str] = Header(default=None)) -> Any:
    token = bearer_token(authorization)
    try:
        result = db().auth.get_user(token)
        user = getattr(result, "user", None)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired session.")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")


async def admin_user(user: Any = Depends(current_user)) -> Any:
    email = (getattr(user, "email", "") or "").lower()
    if not ADMIN_EMAILS or email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return user


def sign_partner_token(partner_id: str) -> str:
    payload = {
        "partner_id": partner_id,
        "exp": int(time.time()) + 60 * 60 * 24 * 7,
        "nonce": secrets.token_hex(8),
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(PARTNER_TOKEN_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_partner_token(token: str) -> dict[str, Any]:
    try:
        raw, sig = token.rsplit(".", 1)
        expected = hmac.new(PARTNER_TOKEN_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired partner session.")


async def partner_session(x_partner_token: Optional[str] = Header(default=None)) -> dict[str, Any]:
    if not x_partner_token:
        raise HTTPException(status_code=401, detail="Partner authentication required.")
    return verify_partner_token(x_partner_token)


def money_to_paise(value: float) -> int:
    if value < 0 or value > 10_000_000:
        raise HTTPException(status_code=400, detail="Invalid amount.")
    return int(round(value * 100))


class UserSignRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ProductStatusUpdateRequest(BaseModel):
    status: str


class PartnerStatusUpdateRequest(BaseModel):
    status: str


class OrderStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=2, max_length=50)


class CorporateLeadRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    quantity_required: str = Field(min_length=1, max_length=120)
    phone: Optional[str] = Field(default="", max_length=30)
    company: Optional[str] = Field(default="", max_length=160)
    message: Optional[str] = Field(default="", max_length=2000)


class PartnerOnboardingRequest(BaseModel):
    store_name: str = Field(min_length=2, max_length=120)
    founder_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=30)
    category: str = Field(min_length=2, max_length=80)
    store_link: Optional[str] = Field(default="", max_length=500)


class PartnerLoginRequest(BaseModel):
    partner_id: str = Field(min_length=4, max_length=32)
    access_code: str = Field(min_length=6, max_length=64)


class ContactMessageRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=2, max_length=4000)


class CartItem(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=20)
    recipient_name: str = Field(min_length=1, max_length=120)
    delivery_address: str = Field(min_length=5, max_length=500)
    gift_message: str = Field(default="", max_length=1000)
    sender_name: str = Field(min_length=1, max_length=120)
    personalization_text: str = Field(default="", max_length=1000)
    personalization_image_url: str = Field(default="", max_length=1000)


class PaymentOrderRequest(BaseModel):
    items: list[CartItem] = Field(min_length=1, max_length=50)


class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    items: list[CartItem] = Field(min_length=1, max_length=50)


class OrderCreateRequest(CartItem):
    store_name: Optional[str] = ""
    item_name: Optional[str] = ""
    price: Optional[float] = None
    sender_email: Optional[EmailStr] = None


@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "service": APP_NAME,
        "version": APP_VERSION,
        "database_configured": supabase is not None,
        "payments_configured": razorpay_client is not None,
    }


@app.get("/api/config", tags=["Configuration"])
async def public_config():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="Frontend configuration is incomplete.")
    return {"supabase_url": SUPABASE_URL, "supabase_anon_key": SUPABASE_ANON_KEY, "razorpay_key_id": RAZORPAY_KEY_ID}


@app.get("/sitemap.xml", tags=["SEO"])
async def get_sitemap():
    urls = [
        "https://tokensforeveryone.in/",
        "https://tokensforeveryone.in/#catalog",
        "https://tokensforeveryone.in/#personalized",
        "https://tokensforeveryone.in/#corporate",
        "https://tokensforeveryone.in/#partners",
    ]
    body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    body += "".join(f"<url><loc>{u}</loc><changefreq>daily</changefreq></url>" for u in urls)
    body += "</urlset>"
    return Response(content=body, media_type="application/xml")


@app.post("/api/auth/signup", tags=["Authentication"])
async def signup_user(payload: UserSignRequest):
    try:
        result = db().auth.sign_up({"email": payload.email, "password": payload.password})
        return {"success": True, "message": "Account created. Check your email if confirmation is enabled.", "user": result.user}
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to create account. The email may already be registered.")


@app.post("/api/auth/login", tags=["Authentication"])
async def login_user(payload: UserSignRequest):
    try:
        result = db().auth.sign_in_with_password({"email": payload.email, "password": payload.password})
        return {"success": True, "session": result.session, "user": result.user}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password.")


@app.post("/api/personalization/upload", tags=["Personalization"])
async def upload_personalization_image(file: UploadFile = File(...), _: Any = Depends(current_user)):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Only JPG, PNG and WebP images are allowed.")
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")
    filename = "".join(c for c in (file.filename or "gift.jpg") if c.isalnum() or c in "._-")[:100]
    path = f"personalizations/{uuid.uuid4()}_{filename or 'gift.jpg'}"
    try:
        db().storage.from_("products").upload(
            path=path, file=content, file_options={"content-type": file.content_type}
        )
        return {"success": True, "image_url": db().storage.from_("products").get_public_url(path)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to upload personalization image.") from exc


@app.get("/api/products", tags=["Products"])
async def get_products(category: Optional[str] = None, search: Optional[str] = None, limit: int = 60):
    limit = max(1, min(limit, 100))
    query = db().table("products").select("*").eq("status", "approved").limit(limit)
    if category and category.lower() not in {"all", "general"}:
        query = query.ilike("category", f"%{category}%")
    if search:
        safe = search.replace(",", " ").strip()[:80]
        if safe:
            query = query.or_(f"item_name.ilike.%{safe}%,description.ilike.%{safe}%")
    try:
        response = query.execute()
        return {"success": True, "data": response.data or []}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to load products.") from exc


@app.get("/api/orders", tags=["Orders"])
async def get_user_orders(user: Any = Depends(current_user)):
    email = getattr(user, "email", "")
    try:
        response = db().table("orders").select("*").eq("sender_email", email).order("created_at", desc=True).execute()
        return {"success": True, "data": response.data or []}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to load orders.") from exc


@app.post("/api/create-payment-order", tags=["Payments"])
async def create_payment_order(payload: PaymentOrderRequest, user: Any = Depends(current_user)):
    if razorpay_client is None:
        raise HTTPException(status_code=503, detail="Payments are not configured.")
    product_ids = [item.product_id for item in payload.items]
    try:
        raw_products = db().table("products").select("id,item_name,store_name,price,status").in_("id", product_ids).execute().data
        products = raw_products if isinstance(raw_products, list) else []
        by_id = {str(p.get("id")): p for p in products if isinstance(p, dict)}
        
        total_paise = 0
        for item in payload.items:
            product = by_id.get(item.product_id)
            if not product or product.get("status") != "approved":
                raise HTTPException(status_code=400, detail=f"Product {item.product_id} is unavailable.")
            
            raw_price = product.get("price")
            try:
                price_val = float(str(raw_price)) if raw_price is not None else 0.0
            except (TypeError, ValueError):
                price_val = 0.0

            total_paise += money_to_paise(price_val) * item.quantity
            
        if total_paise <= 0:
            raise HTTPException(status_code=400, detail="Cart total must be greater than zero.")
        order = razorpay_client.order.create({
            "amount": total_paise,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {"user_id": str(getattr(user, "id", ""))},
        })
        return {
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": "INR",
            "key_id": RAZORPAY_KEY_ID,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to initialize payment.") from exc


@app.post("/api/verify-payment", tags=["Payments"])
async def verify_payment(payload: PaymentVerifyRequest, user: Any = Depends(current_user)):
    if not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=503, detail="Payments are not configured.")
    generated_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(generated_signature, payload.razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment signature verification failed.")

    try:
        if razorpay_client is None:
            raise HTTPException(status_code=503, detail="Payments are not configured.")
        gateway_order = razorpay_client.order.fetch(payload.razorpay_order_id)
        product_ids = [item.product_id for item in payload.items]
        
        raw_products = db().table("products").select("id,item_name,store_name,price,status").in_("id", product_ids).execute().data
        products = raw_products if isinstance(raw_products, list) else []
        by_id = {str(p.get("id")): p for p in products if isinstance(p, dict)}
        
        total_paise = 0
        for item in payload.items:
            product = by_id.get(item.product_id)
            if not product or product.get("status") != "approved":
                raise HTTPException(status_code=400, detail="A product in the cart is no longer available.")
            
            raw_price = product.get("price")
            try:
                price_val = float(str(raw_price)) if raw_price is not None else 0.0
            except (TypeError, ValueError):
                price_val = 0.0

            total_paise += money_to_paise(price_val) * item.quantity

        gateway_amount = gateway_order.get("amount", -1) if isinstance(gateway_order, dict) else -1
        if int(gateway_amount) != total_paise:
            raise HTTPException(status_code=400, detail="Payment amount does not match the cart.")

        existing = db().table("orders").select("id").eq("payment_id", payload.razorpay_payment_id).limit(1).execute()
        if existing.data:
            return {"success": True, "message": "Payment already processed.", "data": existing.data}

        email = getattr(user, "email", "")
        rows = []
        for item in payload.items:
            product = by_id[item.product_id]
            raw_price = product.get("price")
            try:
                price_val = float(str(raw_price)) if raw_price is not None else 0.0
            except (TypeError, ValueError):
                price_val = 0.0
            
            for _ in range(item.quantity):
                rows.append({
                    "id": str(uuid.uuid4()),
                    "product_id": str(product.get("id", "")),
                    "store_name": product.get("store_name", ""),
                    "item_name": product.get("item_name", ""),
                    "recipient_name": item.recipient_name,
                    "delivery_address": item.delivery_address,
                    "gift_message": item.gift_message,
                    "sender_name": item.sender_name,
                    "sender_email": email,
                    "price": price_val,
                    "quantity": 1,
                    "payment_id": payload.razorpay_payment_id,
                    "razorpay_order_id": payload.razorpay_order_id,
                    "status": "Payment Confirmed",
                    "personalization_text": item.personalization_text,
                    "personalization_image_url": item.personalization_image_url,
                })
        response = db().table("orders").insert(rows).execute()
        return {"success": True, "message": "Payment verified and order placed.", "data": response.data or []}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Payment succeeded but order creation failed. Contact support with your payment ID.") from exc


@app.get("/api/admin/metrics", tags=["Admin Portal"])
async def get_admin_metrics(_: Any = Depends(admin_user)):
    try:
        orders = db().table("orders").select("id,price").execute().data or []
        products = db().table("products").select("id").execute().data or []
        partners = db().table("partner_applications").select("partner_id").execute().data or []
        revenue = sum(float(str(o.get("price") or 0)) for o in orders if isinstance(o, dict))
        return {"success": True, "total_orders": len(orders), "total_revenue": revenue, "total_products": len(products), "total_partners": len(partners)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to load admin metrics.") from exc


@app.get("/api/admin/products/pending", tags=["Admin Portal"])
async def get_pending_products(_: Any = Depends(admin_user)):
    return {"success": True, "data": db().table("products").select("*").eq("status", "pending").execute().data or []}


@app.get("/api/admin/products/all", tags=["Admin Portal"])
async def get_all_platform_products(_: Any = Depends(admin_user)):
    return {"success": True, "data": db().table("products").select("*").order("item_name").execute().data or []}


@app.delete("/api/admin/products/{product_id}", tags=["Admin Portal"])
async def admin_delete_product(product_id: str, _: Any = Depends(admin_user)):
    response = db().table("products").delete().eq("id", product_id).execute()
    return {"success": True, "message": "Product deleted.", "data": response.data or []}


@app.patch("/api/admin/products/{product_id}/status", tags=["Admin Portal"])
async def update_product_approval_status(product_id: str, payload: ProductStatusUpdateRequest, _: Any = Depends(admin_user)):
    if payload.status not in {"approved", "rejected", "pending"}:
        raise HTTPException(status_code=400, detail="Invalid product status.")
    response = db().table("products").update({"status": payload.status}).eq("id", product_id).execute()
    return {"success": True, "message": f"Product status updated to {payload.status}.", "data": response.data or []}


@app.get("/api/admin/partners", tags=["Admin Portal"])
async def get_all_partners(_: Any = Depends(admin_user)):
    return {"success": True, "data": db().table("partner_applications").select("*").order("created_at", desc=True).execute().data or []}


@app.patch("/api/admin/partners/{partner_id}/status", tags=["Admin Portal"])
async def update_partner_status(partner_id: str, payload: PartnerStatusUpdateRequest, _: Any = Depends(admin_user)):
    if payload.status not in {"active", "suspended", "pending"}:
        raise HTTPException(status_code=400, detail="Invalid partner status.")
    response = db().table("partner_applications").update({"status": payload.status}).eq("partner_id", partner_id).execute()
    return {"success": True, "message": f"Partner status updated to {payload.status}.", "data": response.data or []}


@app.get("/api/admin/support", tags=["Admin Portal"])
async def get_admin_support_tickets(_: Any = Depends(admin_user)):
    return {"success": True, "data": db().table("contact_messages").select("*").order("created_at", desc=True).execute().data or []}


@app.delete("/api/admin/support/{ticket_id}", tags=["Admin Portal"])
async def delete_support_ticket(ticket_id: str, _: Any = Depends(admin_user)):
    response = db().table("contact_messages").delete().eq("ticket_id", ticket_id).execute()
    return {"success": True, "message": "Support ticket resolved.", "data": response.data or []}


@app.get("/api/admin/corporate", tags=["Admin Portal"])
async def get_admin_corporate_leads(_: Any = Depends(admin_user)):
    return {"success": True, "data": db().table("corporate_leads").select("*").order("created_at", desc=True).execute().data or []}


@app.post("/api/partner/login", tags=["Partner Dashboard"])
async def partner_login(payload: PartnerLoginRequest):
    try:
        rows = db().table("partner_applications").select("partner_id,store_name,status,access_code_hash").eq("partner_id", payload.partner_id).limit(1).execute().data or []
        if not rows:
            raise HTTPException(status_code=404, detail="Invalid Partner ID or access code.")
        partner = rows[0]
        if partner.get("status") == "suspended":
            raise HTTPException(status_code=403, detail="Partner store is suspended.")
        if partner.get("status") != "active":
            raise HTTPException(status_code=403, detail="Partner store is awaiting approval.")
        expected = str(partner.get("access_code_hash") or "")
        actual = hashlib.sha256(payload.access_code.encode()).hexdigest()
        if not expected or not hmac.compare_digest(expected, actual):
            raise HTTPException(status_code=401, detail="Invalid Partner ID or access code.")
        return {
            "success": True,
            "message": "Partner logged in.",
            "store_name": partner.get("store_name", ""),
            "partner_id": partner.get("partner_id", ""),
            "partner_token": sign_partner_token(str(partner["partner_id"])),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Partner login failed.") from exc


@app.post("/api/partner/products", tags=["Partner Dashboard"])
async def partner_add_product(
    partner: dict[str, Any] = Depends(partner_session),
    partner_id: str = Form(...),
    store_name: str = Form(...),
    item_name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
):
    if partner["partner_id"] != partner_id:
        raise HTTPException(status_code=403, detail="Unauthorized partner.")
    if price <= 0 or price > 1_000_000:
        raise HTTPException(status_code=400, detail="Invalid price.")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Only JPG, PNG and WebP images are allowed.")
    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be 5 MB or smaller.")
    safe_filename = "".join(c for c in (file.filename or "image.jpg") if c.isalnum() or c in "._-")[:100]
    file_path = f"{uuid.uuid4()}_{safe_filename or 'image.jpg'}"
    try:
        db().storage.from_("products").upload(path=file_path, file=file_bytes, file_options={"content-type": file.content_type})
        image_url = db().storage.from_("products").get_public_url(file_path)
        response = db().table("products").insert({
            "id": str(uuid.uuid4()),
            "store_name": store_name,
            "item_name": item_name[:160],
            "description": description[:2000],
            "price": price,
            "category": category[:80],
            "image_url": image_url,
            "status": "pending",
        }).execute()
        return {"success": True, "message": "Product submitted for approval.", "data": response.data or []}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to publish product.") from exc


@app.get("/api/partner/orders", tags=["Partner Dashboard"])
async def get_partner_orders(store_name: str, partner: dict[str, Any] = Depends(partner_session)):
    try:
        rows = db().table("partner_applications").select("store_name,status").eq("partner_id", partner["partner_id"]).limit(1).execute().data or []
        if not rows or rows[0].get("store_name") != store_name:
            raise HTTPException(status_code=403, detail="Unauthorized partner.")
        response = db().table("orders").select("*").eq("store_name", store_name).order("created_at", desc=True).execute()
        return {"success": True, "data": response.data or []}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to load partner orders.") from exc


@app.patch("/api/partner/orders/{order_id}/status", tags=["Partner Dashboard"])
async def update_order_status(order_id: str, payload: OrderStatusUpdateRequest, partner: dict[str, Any] = Depends(partner_session)):
    allowed = {"Payment Confirmed", "Preparing", "Ready to Dispatch", "Out for Delivery", "Delivered", "Cancelled"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid order status.")
    try:
        owned = db().table("orders").select("id,store_name").eq("id", order_id).limit(1).execute().data or []
        if not owned:
            raise HTTPException(status_code=404, detail="Order not found.")
        store = db().table("partner_applications").select("store_name").eq("partner_id", partner["partner_id"]).limit(1).execute().data or []
        if not store or store[0]["store_name"] != owned[0]["store_name"]:
            raise HTTPException(status_code=403, detail="Unauthorized partner.")
        response = db().table("orders").update({"status": payload.status}).eq("id", order_id).execute()
        return {"success": True, "message": "Order status updated.", "data": response.data or []}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to update order status.") from exc


class PoolCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    target_amount: float = Field(gt=0, le=10_000_000)
    recipient_name: str = Field(min_length=1, max_length=120)
    message: str = Field(default="", max_length=1000)


@app.post("/api/pools", status_code=status.HTTP_201_CREATED, tags=["Pool Gifting"])
async def create_pool(payload: PoolCreateRequest, user: Any = Depends(current_user)):
    pool_code = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    try:
        response = db().table("gift_pools").insert({
            "pool_code": pool_code,
            "creator_id": str(getattr(user, "id", "")),
            "creator_email": getattr(user, "email", ""),
            "title": payload.title,
            "target_amount": payload.target_amount,
            "recipient_name": payload.recipient_name,
            "message": payload.message,
            "status": "open",
            "raised_amount": 0,
        }).execute()
        return {"success": True, "pool_code": pool_code, "data": response.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to create gift pool.") from exc


@app.get("/api/pools/{pool_code}", tags=["Pool Gifting"])
async def get_pool(pool_code: str):
    rows = db().table("gift_pools").select("pool_code,title,target_amount,recipient_name,message,status,raised_amount").eq("pool_code", pool_code).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Gift pool not found.")
    return {"success": True, "data": rows[0]}


@app.post("/api/corporate/inquiry", status_code=status.HTTP_201_CREATED, tags=["B2B Corporate"])
async def submit_corporate_inquiry(payload: CorporateLeadRequest):
    try:
        response = db().table("corporate_leads").insert({
            "lead_id": str(uuid.uuid4()),
            "name": payload.name,
            "email": payload.email,
            "phone": payload.phone,
            "company": payload.company,
            "quantity_required": payload.quantity_required,
            "message": payload.message,
            "status": "new",
        }).execute()
        return {"success": True, "message": "Inquiry received.", "data": response.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to submit inquiry.") from exc


@app.post("/api/partners/onboard", status_code=status.HTTP_201_CREATED, tags=["Partner Hub"])
async def onboard_partner_store(payload: PartnerOnboardingRequest):
    access_code = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:10]
    try:
        response = db().table("partner_applications").insert({
            "partner_id": secrets.token_hex(4),
            "store_name": payload.store_name,
            "founder_name": payload.founder_name,
            "email": payload.email,
            "phone": payload.phone,
            "category": payload.category,
            "store_link": payload.store_link,
            "access_code_hash": hashlib.sha256(access_code.encode()).hexdigest(),
            "status": "pending",
        }).execute()
        row = (response.data or [{}])[0]
        return {
            "success": True,
            "message": "Application submitted. Save the credentials; the store can log in after approval.",
            "partner_id": row.get("partner_id"),
            "access_code": access_code,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to submit partner application.") from exc


@app.post("/api/contact/submit", status_code=status.HTTP_201_CREATED, tags=["Support"])
async def submit_contact_message(payload: ContactMessageRequest):
    try:
        response = db().table("contact_messages").insert({
            "ticket_id": str(uuid.uuid4()),
            "name": payload.name,
            "email": payload.email,
            "subject": payload.subject,
            "message": payload.message,
            "status": "open",
        }).execute()
        return {"success": True, "message": "Message sent.", "data": response.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to submit message.") from exc