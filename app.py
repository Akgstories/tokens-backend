from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
import uuid
import os

# SQLAlchemy imports for Supabase PostgreSQL
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Supabase Database Configuration ---
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:[Tokensdatabase02]@db.xhipfasywzgkmpoogaaz.supabase.co:6543/postgres"
)

# Initialize engine with connection pooling parameters to prevent drops
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- SQLAlchemy Database Models ---
class CorporateLeadModel(Base):
    __tablename__ = "corporate_leads"
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(String, unique=True)
    name = Column(String)
    email = Column(String)
    quantity_required = Column(String)

class PartnerAppModel(Base):
    __tablename__ = "partner_applications"
    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(String, unique=True)
    store_name = Column(String)
    founder_name = Column(String)
    email = Column(String)
    phone = Column(String)
    category = Column(String)
    store_link = Column(String)
    status = Column(String, default="pending_review")

class ContactMessageModel(Base):
    __tablename__ = "contact_messages"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String, unique=True)
    name = Column(String)
    email = Column(String)
    subject = Column(String)
    message = Column(String)


# --- FastAPI App Setup ---
app = FastAPI(
    title="Tokens Gifting Platform API",
    description="Backend services for India's Dedicated Gifting Platform",
    version="1.0.0"
)

# Enable CORS for frontend integration (Netlify + Localhost)
origins = [
    "https://tokensgifting.netlify.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Safe Startup Event: Creates tables without crashing the server if connection hiccups
@app.on_event("startup")
def startup_db_client():
    try:
        Base.metadata.create_all(bind=engine)
        print("Successfully connected to Supabase and verified tables!")
    except Exception as e:
        print(f"WARNING: Database connection failed on startup, but server is running: {e}")


# In-memory storage for active pools
POOLS_DB = {}


# --- Pydantic Models for Data Validation ---

class MatchmakerRequest(BaseModel):
    recipient_type: str = Field(..., description="e.g., Best Friend, Partner, Colleague")
    budget_range: str = Field(..., description="e.g., Under ₹500, ₹500 - ₹1500, ₹1500+")

class GiftRecommendation(BaseModel):
    id: str
    title: str
    price: int
    store: str
    category: str
    match_reason: str

class PoolCreateRequest(BaseModel):
    creator_name: str
    recipient_name: str
    target_gift_name: str
    target_amount: int = Field(..., gt=0)

class PoolContributionRequest(BaseModel):
    contributor_name: str
    amount: int = Field(..., gt=0)

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
    store_link: str

class ContactMessageRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str


# --- API Routes ---

@app.get("/", tags=["Health Check"])
async def root():
    return {"status": "online", "message": "Welcome to Tokens Platform API 🚀"}


# 1. AI Gift Matchmaker Endpoint
@app.post("/api/matchmaker/recommend", response_model=List[GiftRecommendation], tags=["AI Matchmaker"])
async def get_ai_recommendations(payload: MatchmakerRequest):
    catalog = [
        {
            "id": "g1",
            "title": "Custom Magic Mug with Personalised Engraving",
            "price": 399,
            "store": "Artisan Print & Engrave",
            "category": "Personalised Items",
            "match_reason": "Top pick for college peers within student pocket budget."
        },
        {
            "id": "g2",
            "title": "Aesthetic Sunset LED Lamp with Remote",
            "price": 799,
            "store": "Aesthetic Vibes Decor",
            "category": "Decor & Lights",
            "match_reason": "High demand Gen Z room aesthetic product."
        },
        {
            "id": "g3",
            "title": "Luxury Self-Designed Chocolate & Notes Hamper",
            "price": 1499,
            "store": "The Hamper Co.",
            "category": "Sweets, Treats & Hampers",
            "match_reason": "Great choice if you are pooling funds or want a premium feel."
        }
    ]

    budget_filter = payload.budget_range.lower()
    if "under ₹500" in budget_filter:
        filtered = [item for item in catalog if item["price"] <= 500]
    elif "₹1,500+" in budget_filter or "1500" in budget_filter:
        filtered = [item for item in catalog if item["price"] >= 1000]
    else:
        filtered = catalog

    return filtered if filtered else catalog


# 2. Group Pool-Gifting Endpoints
@app.post("/api/pools/create", status_code=status.HTTP_201_CREATED, tags=["Pool Gifting"])
async def create_pool(payload: PoolCreateRequest):
    pool_id = str(uuid.uuid4())[:8]
    new_pool = {
        "pool_id": pool_id,
        "creator_name": payload.creator_name,
        "recipient_name": payload.recipient_name,
        "target_gift_name": payload.target_gift_name,
        "target_amount": payload.target_amount,
        "current_raised": 0,
        "contributors": []
    }
    POOLS_DB[pool_id] = new_pool
    return {
        "message": "Pool created successfully!",
        "pool_id": pool_id,
        "shareable_link": f"https://tokensgifting.in/pool/{pool_id}",
        "data": new_pool
    }

@app.post("/api/pools/{pool_id}/contribute", tags=["Pool Gifting"])
async def contribute_to_pool(pool_id: str, payload: PoolContributionRequest):
    if pool_id not in POOLS_DB:
        raise HTTPException(status_code=404, detail="Pool not found.")
    
    pool = POOLS_DB[pool_id]
    pool["current_raised"] += payload.amount
    pool["contributors"].append({
        "name": payload.contributor_name,
        "amount": payload.amount
    })
    
    return {
        "message": "Contribution added successfully!",
        "current_raised": pool["current_raised"],
        "target_amount": pool["target_amount"],
        "percentage_funded": min(100, int((pool["current_raised"] / pool["target_amount"]) * 100))
    }


# 3. Corporate Gifting Inquiries Endpoint (Saved to Supabase)
@app.post("/api/corporate/inquiry", status_code=status.HTTP_201_CREATED, tags=["B2B Corporate"])
async def submit_corporate_inquiry(payload: CorporateLeadRequest):
    db = SessionLocal()
    try:
        lead_id = str(uuid.uuid4())[:6]
        lead_item = CorporateLeadModel(
            lead_id=lead_id,
            name=payload.name,
            email=payload.email,
            quantity_required=payload.quantity_required
        )
        db.add(lead_item)
        db.commit()
        return {
            "message": "Corporate inquiry received! Our B2B team will email your custom catalog within 24 hours.",
            "lead_id": lead_id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# 4. Partner Store Onboarding Endpoint (Saved to Supabase)
@app.post("/api/partners/onboard", status_code=status.HTTP_201_CREATED, tags=["Partner Hub"])
async def onboard_partner_store(payload: PartnerOnboardingRequest):
    db = SessionLocal()
    try:
        partner_id = str(uuid.uuid4())[:6]
        partner_item = PartnerAppModel(
            partner_id=partner_id,
            store_name=payload.store_name,
            founder_name=payload.founder_name,
            email=payload.email,
            phone=payload.phone,
            category=payload.category,
            store_link=payload.store_link,
            status="pending_review"
        )
        db.add(partner_item)
        db.commit()
        return {
            "message": "Partner application submitted successfully!",
            "partner_id": partner_id,
            "status": "pending_review"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# 5. Customer Contact Support Endpoint (Saved to Supabase)
@app.post("/api/contact/submit", status_code=status.HTTP_201_CREATED, tags=["Support"])
async def submit_contact_message(payload: ContactMessageRequest):
    db = SessionLocal()
    try:
        ticket_id = str(uuid.uuid4())[:6]
        ticket_item = ContactMessageModel(
            ticket_id=ticket_id,
            name=payload.name,
            email=payload.email,
            subject=payload.subject,
            message=payload.message
        )
        db.add(ticket_item)
        db.commit()
        return {
            "message": "Support message sent successfully!",
            "ticket_id": ticket_id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()