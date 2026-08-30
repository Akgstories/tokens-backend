from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
import uuid

app = FastAPI(
    title="Tokens Gifting Platform API",
    description="Backend services for India's Dedicated Gifting Platform",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory Databases (Mock Storage for demonstration) ---
POOLS_DB = {}
PARTNERS_DB = []
CORPORATE_LEADS_DB = []
CONTACT_MESSAGES_DB = []


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
    """
    Simulates AI gift matching based on recipient and budget filters.
    """
    # Mock intelligent recommendations catalog
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

    # Filter recommendations based on user budget choice roughly
    budget_filter = payload.budget_range.lower()
    if "under ₹500" in budget_filter:
        filtered = [item for item in catalog if item["price"] <= 500]
    elif "₹1,500+" in budget_filter or "1500" in budget_filter:
        filtered = [item for item in catalog if item["price"] >= 1000]
    else:
        filtered = catalog  # Default or mid-range

    return filtered if filtered else catalog


# 2. Group Pool-Gifting Endpoints
@app.post("/api/pools/create", status_code=status.HTTP_201_CREATED, tags=["Pool Gifting"])
async def create_pool(payload: PoolCreateRequest):
    """
    Creates a new group pool-gifting campaign link.
    """
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
    """
    Adds a friend's contribution to an existing pool.
    """
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


# 3. Corporate Gifting Inquiries Endpoint
@app.post("/api/corporate/inquiry", status_code=status.HTTP_201_CREATED, tags=["B2B Corporate"])
async def submit_corporate_inquiry(payload: CorporateLeadRequest):
    """
    Captures bulk B2B catalog and volume discount inquiries.
    """
    lead_id = str(uuid.uuid4())[:6]
    lead_data = {
        "lead_id": lead_id,
        **payload.dict()
    }
    CORPORATE_LEADS_DB.append(lead_data)
    return {
        "message": "Corporate inquiry received! Our B2B team will email your custom catalog within 24 hours.",
        "lead_id": lead_id
    }


# 4. Partner Store Onboarding Endpoint
@app.post("/api/partners/onboard", status_code=status.HTTP_201_CREATED, tags=["Partner Hub"])
async def onboard_partner_store(payload: PartnerOnboardingRequest):
    """
    Registers a new boutique vendor looking to list products on the multi-store hub.
    """
    partner_id = str(uuid.uuid4())[:6]
    partner_record = {
        "partner_id": partner_id,
        **payload.dict(),
        "status": "pending_review"
    }
    PARTNERS_DB.append(partner_record)
    return {
        "message": "Partner application submitted successfully!",
        "partner_id": partner_id,
        "status": "pending_review"
    }


# 5. Customer Contact Support Endpoint
@app.post("/api/contact/submit", status_code=status.HTTP_201_CREATED, tags=["Support"])
async def submit_contact_message(payload: ContactMessageRequest):
    """
    Handles customer support tickets and contact form messages.
    """
    ticket_id = str(uuid.uuid4())[:6]
    ticket_record = {
        "ticket_id": ticket_id,
        **payload.dict()
    }
    CONTACT_MESSAGES_DB.append(ticket_record)
    return {
        "message": "Support message sent successfully!",
        "ticket_id": ticket_id
    }

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Paste your Supabase connection URI here:
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:Tokensdatabase02@db.xhipfasywzgkmpoogaaz.supabase.co:5432/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define your table model
class UserSubmissionModel(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    preference = Column(String)

# Automatically create tables in Supabase if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TokenData(BaseModel):
    name: str
    preference: str

@app.post("/api/match")
def save_token_data(data: TokenData):
    db = SessionLocal()
    try:
        db_item = UserSubmissionModel(name=data.name, preference=data.preference)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return {"message": "Data saved to Supabase successfully!", "id": db_item.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()