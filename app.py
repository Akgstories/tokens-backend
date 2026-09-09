import os
import uuid
import hmac
import hashlib
from typing import Optional
from fastapi import FastAPI, HTTPException, status, File, UploadFile, Form
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
import razorpay

app = FastAPI(
    title="Tokens Gifting Platform API",
    description="Backend services for India's Dedicated Gifting Platform with Admin Moderation",
    version="3.4.0"
)

# --- CORS Configuration ---
origins = [
    "https://tokensforeveryone.in",
    "https://www.tokensforeveryone.in",
    "https://tokens-frontend-git-main-tokens2.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Supabase Credentials ---
SUPABASE_URL = "https://xhipfasywzgkmpoogaaz.supabase.co"
SUPABASE_KEY = "sb_publishable_K1MGEBgEhHL50VGjS5pipQ_JJfWFDhc"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Razorpay Configuration ---
RAZORPAY_KEY_ID = "rzp_live_TYu7Hj0Jzp6Yxm"
RAZORPAY_KEY_SECRET = "VqEJQgg057H1ZdS2VOJ04DZh"
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# --- Pydantic Request Models ---

class UserSignRequest(BaseModel):
    email: EmailStr
    password: str

class OrderCreateRequest(BaseModel):
    product_id: str
    store_name: str
    item_name: str
    recipient_name: str
    delivery_address: str
    gift_message: Optional[str] = ""
    sender_name: str
    sender_email: Optional[str] = ""
    price: float

class PaymentOrderRequest(BaseModel):
    amount: float

class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class OrderStatusUpdateRequest(BaseModel):
    status: str

class ProductStatusUpdateRequest(BaseModel):
    status: str  # "approved" or "rejected"

class CorporateLeadRequest(BaseModel):
    name: str
    email: EmailStr
    quantity_required: str

class PartnerOnboardingRequest(BaseModel):
    store_name: str
    founder_name: str
    email: EmailStr
    phone: str
    category: str
    store_link: Optional[str] = ""

class PartnerLoginRequest(BaseModel):
    partner_id: str

class ContactMessageRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str


# --- API Routes ---

@app.get("/", tags=["Health Check"])
async def root():
    return {"status": "online", "message": "Welcome to Tokens Platform API 🚀"}


# --- XML Sitemap Endpoint ---
@app.get("/sitemap.xml", tags=["SEO"])
async def get_sitemap():
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://tokensforeveryone.in/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://tokensforeveryone.in/#catalog</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://tokensforeveryone.in/#hub</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://tokensforeveryone.in/#pool-gifting</loc>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://tokensforeveryone.in/#corporate</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://tokensforeveryone.in/#onboard</loc>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
</urlset>"""
    return Response(content=sitemap_xml, media_type="application/xml")


# --- Authentication Endpoints ---

@app.post("/api/auth/signup", tags=["Authentication"])
async def signup_user(payload: UserSignRequest):
    try:
        response = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password
        })
        return {
            "success": True, 
            "message": "User registered successfully!", 
            "data": response
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login", tags=["Authentication"])
async def login_user(payload: UserSignRequest):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })
        return {
            "success": True, 
            "message": "Logged in successfully! ✨", 
            "session": response.session,
            "user": response.user
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password.")


# --- Payment Order Creation ---
@app.post("/api/create-payment-order", tags=["Payments"])
async def create_payment_order(payload: PaymentOrderRequest):
    try:
        amount_in_paise = int(payload.amount * 100)
        razorpay_order = razorpay_client.order.create({  # type: ignore
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1
        })
        return {
            "success": True,
            "order_id": razorpay_order['id'],
            "amount": razorpay_order['amount'],
            "key_id": RAZORPAY_KEY_ID
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Secure Payment Signature Verification Endpoint ---
@app.post("/api/verify-payment", tags=["Payments"])
async def verify_payment(payload: PaymentVerifyRequest):
    try:
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode('utf-8'),
            f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if generated_signature == payload.razorpay_signature:
            return {"success": True, "message": "Payment verified securely!"}
        else:
            raise HTTPException(status_code=400, detail="Invalid payment signature verification.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Fetch Approved Products Endpoint (Public Catalog) ---
@app.get("/api/products", tags=["Products"])
async def get_products():
    try:
        response = supabase.table("products").select("*").eq("status", "approved").execute()
        if response.data and len(response.data) > 0:
            return {"success": True, "data": response.data}
        return {"success": True, "data": []}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Admin Moderation & Management Endpoints ---

@app.get("/api/admin/products/pending", tags=["Admin Portal"])
async def get_pending_products():
    """Fetch all partner-uploaded products waiting for admin approval."""
    try:
        response = supabase.table("products").select("*").eq("status", "pending").execute()
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/products/all", tags=["Admin Portal"])
async def get_all_platform_products():
    """Fetch every product listed across all partner stores (regardless of status)."""
    try:
        response = supabase.table("products").select("*").execute()
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/partners", tags=["Admin Portal"])
async def get_all_partners():
    """Fetch all registered partner applications/stores."""
    try:
        response = supabase.table("partner_applications").select("*").execute()
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/products/{product_id}", tags=["Admin Portal"])
async def admin_delete_product(product_id: str):
    """Admin hard delete for any inappropriate or unwanted product."""
    try:
        response = supabase.table("products").delete().eq("id", product_id).execute()
        return {"success": True, "message": "Product deleted successfully by admin.", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/admin/products/{product_id}/status", tags=["Admin Portal"])
async def update_product_approval_status(product_id: str, payload: ProductStatusUpdateRequest):
    """Approve or reject a partner's product listing."""
    try:
        if payload.status == "rejected":
            response = supabase.table("products").delete().eq("id", product_id).execute()
        else:
            response = supabase.table("products").update({"status": "approved"}).eq("id", product_id).execute()
            
        return {"success": True, "message": f"Product status updated to {payload.status}!", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/metrics", tags=["Admin Portal"])
async def get_admin_metrics():
    """Get platform-wide overview metrics."""
    try:
        orders = supabase.table("orders").select("id, price").execute()
        products = supabase.table("products").select("id").execute()
        partners = supabase.table("partner_applications").select("partner_id").execute()
        
        total_revenue = 0.0
        orders_data = orders.data
        if isinstance(orders_data, list):
            for o in orders_data:
                if isinstance(o, dict):
                    price_val = o.get("price", 0)
                    if price_val is not None:
                        total_revenue += float(price_val)  # type: ignore
        
        return {
            "success": True,
            "total_orders": len(orders_data) if isinstance(orders_data, list) else 0,
            "total_revenue": total_revenue,
            "total_products": len(products.data) if isinstance(products.data, list) else 0,
            "total_partners": len(partners.data) if isinstance(partners.data, list) else 0
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Orders Endpoints ---

@app.post("/api/orders", tags=["Orders"])
async def create_order(payload: OrderCreateRequest):
    try:
        response = supabase.table("orders").insert({
            "product_id": payload.product_id,
            "store_name": payload.store_name,
            "item_name": payload.item_name,
            "recipient_name": payload.recipient_name,
            "delivery_address": payload.delivery_address,
            "gift_message": payload.gift_message,
            "sender_name": payload.sender_name,
            "sender_email": payload.sender_email,
            "price": payload.price,
            "status": "Pending Dispatch"
        }).execute()
        return {"success": True, "message": "Gift order placed successfully! 🎁", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/orders", tags=["Orders"])
async def get_user_orders(email: str):
    try:
        response = supabase.table("orders").select("*").eq("sender_email", email).execute()
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Partner Portal Endpoints ---

@app.post("/api/partner/login", tags=["Partner Dashboard"])
async def partner_login(payload: PartnerLoginRequest):
    try:
        response = supabase.table("partner_applications").select("*").eq("partner_id", payload.partner_id).execute()
        rows = response.data
        if isinstance(rows, list) and len(rows) > 0:
            partner = rows[0]
            if isinstance(partner, dict):
                return {
                    "success": True, 
                    "message": "Partner logged in successfully! ✨", 
                    "store_name": partner.get("store_name", ""),
                    "partner_id": partner.get("partner_id", "")
                }
        raise HTTPException(status_code=404, detail="Invalid Partner ID.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))    


@app.post("/api/partner/products", tags=["Partner Dashboard"])
async def partner_add_product(
    partner_id: str = Form(...),
    store_name: str = Form(...),
    item_name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        verify_res = supabase.table("partner_applications").select("*").eq("partner_id", partner_id).eq("store_name", store_name).execute()
        if not verify_res.data or len(verify_res.data) == 0:
            raise HTTPException(status_code=403, detail="Unauthorized partner details.")

        file_bytes = await file.read()
        safe_filename = "".join(c for c in (file.filename or "img.jpg") if c.isalnum() or c in ('._-')).strip()
        file_path = f"{uuid.uuid4()}_{safe_filename}"
        
        supabase.storage.from_("products").upload(path=file_path, file=file_bytes)
        image_url = supabase.storage.from_("products").get_public_url(file_path)

        response = supabase.table("products").insert({
            "id": str(uuid.uuid4())[:8],
            "store_name": store_name,
            "item_name": item_name,
            "description": description,
            "price": price,
            "category": category,
            "image_url": image_url,
            "status": "pending"  # Requires Admin Approval before showing up publicly
        }).execute()
        
        return {"success": True, "message": "Product submitted for Admin approval successfully! 🚀", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/partner/orders", tags=["Partner Dashboard"])
async def get_partner_orders(store_name: str):
    try:
        response = supabase.table("orders").select("*").eq("store_name", store_name).execute()
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/api/partner/orders/{order_id}/status", tags=["Partner Dashboard"])
async def update_order_status(order_id: str, payload: OrderStatusUpdateRequest):
    try:
        response = supabase.table("orders").update({"status": payload.status}).eq("id", order_id).execute()
        return {"success": True, "message": "Order status updated successfully!", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- B2B & Support Endpoints ---

@app.post("/api/corporate/inquiry", status_code=status.HTTP_201_CREATED, tags=["B2B Corporate"])
async def submit_corporate_inquiry(payload: CorporateLeadRequest):
    try:
        response = supabase.table("corporate_leads").insert({
            "lead_id": str(uuid.uuid4())[:6],
            "name": payload.name,
            "email": payload.email,
            "quantity_required": payload.quantity_required
        }).execute()
        return {"success": True, "message": "Inquiry received!", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/partners/onboard", status_code=status.HTTP_201_CREATED, tags=["Partner Hub"])
async def onboard_partner_store(payload: PartnerOnboardingRequest):
    try:
        partner_id = str(uuid.uuid4())[:6]
        response = supabase.table("partner_applications").insert({
            "partner_id": partner_id,
            "store_name": payload.store_name,
            "founder_name": payload.founder_name,
            "email": payload.email,
            "phone": payload.phone,
            "category": payload.category,
            "store_link": payload.store_link,
            "status": "pending_review"
        }).execute()
        return {"success": True, "message": "Application submitted!", "partner_id": partner_id, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/contact/submit", status_code=status.HTTP_201_CREATED, tags=["Support"])
async def submit_contact_message(payload: ContactMessageRequest):
    try:
        response = supabase.table("contact_messages").insert({
            "ticket_id": str(uuid.uuid4())[:6],
            "name": payload.name,
            "email": payload.email,
            "subject": payload.subject,
            "message": payload.message
        }).execute()
        return {"success": True, "message": "Message sent!", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

   