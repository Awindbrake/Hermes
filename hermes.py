from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import pandas as pd
import numpy as np
import math
import requests
from bs4 import BeautifulSoup


# Define the URL in the global scope
url = 'https://www.exportkreditgarantien.de/en/solutions/costs/country-risk-categories.html'

app = FastAPI(
    title="Export Credit Guarantee Financial Analysis",
    description="Calculates pre-shipment, counter-guarantee, and post-shipment cover premiums.",
    version="1.0.0",
    servers=[
        {
            "url": "https://hermes-credit-insurance-f9a2d1069ad1.herokuapp.com",
            "description": "Commission Calculator API"
        }
    ]
    )

class PaymentTranche(BaseModel):
    name: str
    payment_month: int
    amount_percent: float

class ProjectSchedule(BaseModel):
    EngineeringStart: Optional[int] = Field(None, description="Start month for Engineering phase.")
    EngineeringEnd: Optional[int] = Field(None, description="End month for Engineering phase.")
    DeliveriesStart: Optional[int] = Field(None, description="Start month for Deliveries.")
    DeliveriesEnd: Optional[int] = Field(None, description="End month for Deliveries.")
    ErectionStart: Optional[int] = Field(None, description="Start month for Erection phase.")
    ErectionEnd: Optional[int] = Field(None, description="End month for Erection phase.")
    TechnicalServicesStart: Optional[int] = Field(None, description="Start month for Technical Services.")
    TechnicalServicesEnd: Optional[int] = Field(None, description="End month for Technical Services.")
    Commissioning: Optional[int] = Field(None, description="Month for Commissioning milestone.")
    PAC: Optional[int] = Field(None, description="Month for Performance Acceptance Certificate (PAC) milestone.")
    FAC: Optional[int] = Field(None, description="Month for Final Acceptance Certificate (FAC) milestone.")

class PremiumCalculationInput(BaseModel):
    country: str
    FBZ: float = Field(..., description="Number of 3 months periods.")
    Selbstkosten: int = Field(..., description="Self-cost in percentage.")
    Garantien: int = Field(..., description="Guarantee volume excluding down payment guarantee in percentage.")
    buyer_cat: str = Field(..., description="Buyer category.")
    project_schedule: ProjectSchedule
    payments: List[PaymentTranche]

def fetch_country_risk_categories(url: str) -> pd.DataFrame:
    
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    tables = soup.find_all('table')

    all_data = []
    for table in tables[1:-1]:  # Assuming relevant data is not in the first and last table
        rows = table.find_all('tr')
        for row in rows[1:]:  # Skip header
            cells = row.find_all(['td', 'th'])
            row_data = [cell.text.strip().replace("./.", "0") for cell in cells]
            all_data.append(row_data)

    df = pd.DataFrame(all_data, columns=["Country", "Category"])
    return df

def get_country_category(country: str, df: pd.DataFrame) -> Optional[int]:
    category_row = df[df["Country"].str.contains(country, case=False, na=False)]
    if not category_row.empty:
        return int(category_row.iloc[0]["Category"])
    else:
        return None

def calculate_pre_ship(FBZ: float, country_category: int) -> dict:
    
    # return a dictionary with pre-ship and counter_guar values
    pre_ship_cover_data = [
        {"Cat": 1, "pre-ship": (0.006 * FBZ) ** 0.5 + 0.264, "counter_guar": 0.12},
        {"Cat": 2, "pre-ship": (0.021 * FBZ) ** 0.5 + 0.431, "counter_guar": 0.2},
        {"Cat": 3, "pre-ship": (0.05 * FBZ) ** 0.5 + 0.573, "counter_guar": 0.28},
        {"Cat": 4, "pre-ship": (0.071 * FBZ) ** 0.5 + 0.761, "counter_guar": 0.36},
        {"Cat": 5, "pre-ship": (0.093 * FBZ) ** 0.5 + 1.206, "counter_guar": 0.52},
        {"Cat": 6, "pre-ship": (0.232 * FBZ) ** 0.5 + 1.467, "counter_guar": 0.68},
        {"Cat": 7, "pre-ship": (0.373 * FBZ) ** 0.5 + 1.785, "counter_guar": 0.84}
    ]
    pre_ship_cover_calc = pd.DataFrame(pre_ship_cover_data)
    pre_ship_cover_calc.set_index('Cat', inplace=True)
    pre_ship_cover_calc = pd.DataFrame(pre_ship_cover_data)
    pre_ship_cover_calc.set_index('Cat', inplace=True)
    result = pre_ship_cover_calc.loc[country_category].to_dict()
    return result

def calculate_short_term(country_cat: int, buyer_cat: str, rlz: int) -> float:
    # Define the data as a dictionary
    short_term_slope = {
        'm': ['Sov+', 'Sov', 'Sov-', 'CC0', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5'],
        1: [0.0086, 0.0095, 0.0105, 0.0095, 0.0165, 0.0218, 0.0254, 0.0345, 0.051],
        2: [0.0092, 0.0102, 0.0112, 0.0102, 0.018, 0.0234, 0.0302, 0.0395, 0.0553],
        3: [0.0125, 0.0139, 0.0153, 0.0139, 0.0208, 0.0279, 0.0337, 0.0459, 0.0622],
        4: [0.0197, 0.0219, 0.0241, 0.0219, 0.0279, 0.0367, 0.044, 0.0574, 0.0773],
        5: [0.0334, 0.0371, 0.0409, 0.0371, 0.0426, 0.0518, 0.0601, 0.0771, 0.0771],
        6: [0.0465, 0.0517, 0.0569, 0.0517, 0.0562, 0.0655, 0.08, 0.08, 0.08],
        7: [0.0682, 0.0758, 0.0834, 0.0758, 0.0806, 0.0871, 0.0871, 0.0871, 0.0871]
    }

    # Convert the data into a DataFrame
    short_term_slope = pd.DataFrame(short_term_slope)
    short_term_slope.set_index('m', inplace=True)

    short_term_fix = {
        'n': ['Sov+', 'Sov', 'Sov-', 'CC0', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5'],
        1: [0.27, 0.3, 0.33, 0.3, 0.35, 0.4, 0.46, 0.51, 0.56],
        2: [0.45, 0.5, 0.55, 0.5, 0.55, 0.6, 0.66, 0.71, 0.76],
        3: [0.63, 0.7, 0.77, 0.7, 0.75, 0.8, 0.86, 0.91, 0.96],
        4: [0.81, 0.9, 0.99, 0.9, 0.95, 1, 1.06, 1.11, 1.16],
        5: [1.17, 1.3, 1.43, 1.3, 1.37, 1.43, 1.5, 1.56, 1.56],
        6: [1.53, 1.7, 1.87, 1.7, 1.79, 1.87, 1.96, 1.96, 1.96],
        7: [1.89, 2.1, 2.31, 2.1, 2.23, 2.36, 2.36, 2.36, 2.36]
    }

    # Convert the data into a DataFrame
    short_term_fix = pd.DataFrame(short_term_fix)
    short_term_fix.set_index('n', inplace=True)

    m = short_term_slope.loc[buyer_cat, country_cat]
    n = short_term_fix.loc[buyer_cat, country_cat]

    premium = round(m * rlz + n, 2)


    return premium


# Pre-fetch country categories on app startup
@app.on_event("startup")
async def startup_event():
    global country_risk_df
    country_risk_df = fetch_country_risk_categories(url)

@app.post("/get_country_category")
async def api_get_country_category(country: str):
    category = get_country_category(country, country_risk_df)
    if category is not None:
        return {"country": country, "category": category}
    else:
        raise HTTPException(status_code=404, detail="Country not found")



@app.post("/calculate_premiums")
async def calculate_premiums(data: PremiumCalculationInput):
    global country_risk_df
    # Fetch country category
    country_category = get_country_category(data.country, country_risk_df)
    if country_category is None:
        raise HTTPException(status_code=404, detail="Country not found")
    
    # Calculate pre-ship and counter guarantees
    pre_ship_results = calculate_pre_ship(data.FBZ, country_category)
    pre_ship_cover = pre_ship_results["pre-ship"] * data.Selbstkosten / 100
    guarantee_cover = pre_ship_results["counter_guar"] * data.Garantien / 100

    delivery_start = data.project_schedule.DeliveriesStart
    delivery_end = data.project_schedule.DeliveriesEnd
    
    if delivery_start and delivery_end:
        average_delivery = (delivery_start + delivery_end) / 2
    elif delivery_start:
        average_delivery = delivery_start 
    elif delivery_end:
        average_delivery = delivery_end
    
    # Prepare response with pre-ship and counter guarantee
    response = {
        "country":data.country,
        "country_category": country_category,
        "pre_ship_cover": pre_ship_cover,
        "guarantee_cover": guarantee_cover,
        "payments": []
    }
    
    # For each payment tranche, calculate premiums
    for payment in data.payments:
        
        if payment.payment_month <= average_delivery:
            rlz = 0
        else:
            rlz = math.ceil(payment.payment_month - average_delivery)

        post_ship_prem = round(calculate_short_term(country_category, data.buyer_cat, rlz) * payment.amount_percent / 100, 2)

        # Construct a new dictionary for each payment that includes the risk_tenor
        payment_info = {
            "name": payment.name,
            "payment_month": payment.payment_month,
            "amount_percent": payment.amount_percent,
            "risk_tenor": rlz,
            "post_shipment_premium": post_ship_prem
        }
        
        response["payments"].append(payment_info)
    
    return response

@app.get("/")
def read_root():
    return {"Welcome": "Navigate to /docs for API usage."}

