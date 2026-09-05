import os
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client

app = FastAPI(
    title="Tokens Gifting Platform API",
    description="Backend services for India's Dedicated Gifting Platform",
    version="2.2.0"
)

# --- CORS Configuration ---
origins = [
    "https://tokensforeveryone.in",
    "https://www.tokensforeveryone.in",
    "https://tokens-frontend-git-main-tokens2.vercel.app/",
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
    price: float

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

class ContactMessageRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str


# --- API Routes ---

@app.get("/", tags=["Health Check"])
async def root():
    return {"status": "online", "message": "Welcome to Tokens Platform API 🚀"}


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
            "message": "User registered successfully! Please check your email for verification if required.", 
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
            "message": "Logged in successfully! 🎉", 
            "session": response.session,
            "user": response.user
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password.")


# 1. Fetch Products Endpoint
@app.get("/api/products", tags=["Products"])
async def get_products():
    try:
        response = supabase.table("products").select("*").execute()
        if response.data and len(response.data) > 0:
            return {"success": True, "data": response.data}
        raise Exception("No products found in table, loading fallback.")
    except Exception as e:
        fallback_catalog = [
            {
                "id": "p1",
                "store_name": "Artisan Print & Engrave",
                "item_name": "Custom Magic Mug with Personalised Engraving",
                "description": "Specializes in custom mugs, keychains, and photo frames.",
                "price": 399,
                "category": "Personalised Items",
                "image_url": "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&q=80&w=500"
            },
            {
                "id": "p2",
                "store_name": "Aesthetic Vibes Decor",
                "item_name": "Aesthetic Sunset LED Lamp",
                "description": "Boutique wall decor, fairy lights, and room aesthetic boxes.",
                "price": 799,
                "category": "Decor & Lights",
                "image_url": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&q=80&w=500"
            },
            {
                "id": "p3",
                "store_name": "The Hamper Co.",
                "item_name": "Luxury Chocolate & Notes Hamper",
                "description": "Self-designed gift combos, luxury chocolates, and curated gift boxes.",
                "price": 1499,
                "category": "Sweets, Treats & Hampers",
                "image_url": "https://images.unsplash.com/photo-1549465220-1a8b9238cd48?auto=format&fit=crop&q=80&w=500"
            }
        ]
        return {"success": True, "data": fallback_catalog}


# 2. Create Order & Personalization Endpoint
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
            "price": payload.price,
            "status": "Pending Dispatch"
        }).execute()
        return {"success": True, "message": "Gift order placed successfully with personalization! 🎁", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 3. Corporate Gifting Inquiries Endpoint
@app.post("/api/corporate/inquiry", status_code=status.HTTP_201_CREATED, tags=["B2B Corporate"])
async def submit_corporate_inquiry(payload: CorporateLeadRequest):
    try:
        lead_id = str(uuid.uuid4())[:6]
        response = supabase.table("corporate_leads").insert({
            "lead_id": lead_id,
            "name": payload.name,
            "email": payload.email,
            "quantity_required": payload.quantity_required
        }).execute()
        return {"success": True, "message": "Corporate inquiry received successfully!", "lead_id": lead_id, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4. Partner Store Onboarding Endpoint
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
        return {"success": True, "message": "Partner application submitted successfully!", "partner_id": partner_id, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 5. Customer Contact Support Endpoint
@app.post("/api/contact/submit", status_code=status.HTTP_201_CREATED, tags=["Support"])
async def submit_contact_message(payload: ContactMessageRequest):
    try:
        ticket_id = str(uuid.uuid4())[:6]
        response = supabase.table("contact_messages").insert({
            "ticket_id": ticket_id,
            "name": payload.name,
            "email": payload.email,
            "subject": payload.subject,
            "message": payload.message
        }).execute()
        return {"success": True, "message": "Support message sent successfully!", "ticket_id": ticket_id, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


