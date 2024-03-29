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

class ScheduleCategory(BaseModel):
    schedule_item: str = Field(..., description="Category of schedule, e.g., Engineering, Equipment, Services")
    payments: List[PaymentTranche] = Field(..., description="List of payments under this category")   

class ProjectSchedule(BaseModel):
    EngineeringStart: Optional[int] = Field(None, description="Start month for Engineering phase.")
    EngineeringEnd: Optional[int] = Field(None, description="End month for Engineering phase.")
    EngineeringValue: Optional[float] = Field(0, description="value of item.")
    EquipmentStart: Optional[int] = Field(None, description="Start month for Deliveries.")
    EquipmentEnd: Optional[int] = Field(None, description="End month for Deliveries.")
    EquipmentValue: Optional[float] = Field(0, description="value of item.")
    SparesStart: Optional[int] = Field(None, description="Start month for spare parts, ocp.")
    SparesEnd: Optional[int] = Field(None, description="End month for spare parts, ocp.")
    SparesValue: Optional[float] = Field(0, description="value of item.")
    ErectionStart: Optional[int] = Field(None, description="Start month for Erection phase.")
    ErectionEnd: Optional[int] = Field(None, description="End month for Erection phase.")
    ErectionValue: Optional[float] = Field(0, description="value of item.")
    AssistanceStart: Optional[int] = Field(None, description="Start month for Technical Services.")
    AssistanceEnd: Optional[int] = Field(None, description="End month for Technical Services.")
    AssistanceValue: Optional[float] = Field(0, description="value of item.")
    Commissioning: Optional[int] = Field(None, description="Month for Commissioning milestone.")
    PAC: Optional[int] = Field(None, description="Month for Performance Acceptance Certificate (PAC) milestone.")
    FAC: Optional[int] = Field(None, description="Month for Final Acceptance Certificate (FAC) milestone.")
    
    def calculate_average(self):
        phases = ['Engineering', 'Equipment', 'Spares', 'Erection', 'Assistance']
        results = {}
        average = ""

        # Calculate for delivery phases
        for phase in phases:
            start_month = getattr(self, f'{phase}Start', None)
            end_month = getattr(self, f'{phase}End', None)
            phase_value = getattr(self, f'{phase}Value', 0)

            if start_month and end_month:
                average = (start_month + end_month) /2
            elif start_month:
                average = start_month
            elif end_month:
                average = end_month
            else:
                average = 0
       
            results[phase] = {"average_month": average, "value": phase_value}

        return results




class PremiumCalculationInput(BaseModel):
    country: str
    #FBZ: float = Field(..., description="Number of 3 months periods.")
    Selbstkosten: int = Field(..., description="Self-cost in percentage.")
    Garantien: int = Field(..., description="Guarantee volume excluding down payment guarantee in percentage.")
    buyer_cat: str = Field(..., description="Buyer category.")
    project_schedule: ProjectSchedule
    payments: List[ScheduleCategory]
    fin_amount: int = Field(..., description="financed amount in percentage.")
    fin_tenor: int = Field(..., description="tenor of loan in years.")

def fetch_and_organize_content_by_section(url, start_header_text, end_header_text):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    all_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'])  # Adjust based on the page structure
    start_index, end_index = None, None

    # Identify start and end points
    for i, element in enumerate(all_elements):
        if element.text.strip() == start_header_text:
            start_index = i
        elif element.text.strip() == end_header_text:
            end_index = i
            break

    if start_index is None or end_index is None:
        return "Start or end marker not found."

    # Initialize storage for organized content
    section_content = {}
    current_header = None

    # Iterate through elements, organizing paragraphs under headers
    for element in all_elements[start_index:end_index + 1]:  # Include the end marker
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            current_header = element.text.strip()
            section_content[current_header] = []  # Initialize a new section for this header
        elif element.name == 'p' and current_header:
            # Append paragraphs to the current section
            section_content[current_header].append(element.text.strip())

    return section_content

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
        {"Cat": 0, "pre-ship": (0.006 * FBZ) ** 0.5 + 0.264, "counter_guar": 0.12},
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
    kreditlauf = 10
    
    m = short_term_slope.loc[buyer_cat, country_cat]
    n = short_term_fix.loc[buyer_cat, country_cat]

    premium = round(m * rlz + n, 2)


    return premium

def calculate_long_term(country_cat: int, buyer_cat: str, rlz_lang: int) -> float:
    # Define the data as a dictionary
    long_term_slope = {
        'm': ['Sov+', 'Sov', 'Sov-', 'CC0', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5'],
        1: [0.0808, 0.0897, 0.0987, 0.0897, 0.1993, 0.2890, 0.3588, 0.4933, 0.7175],
        2: [0.1789, 0.1987, 0.2186, 0.1987, 0.3180, 0.4094, 0.5167, 0.6548, 0.8694],
        3: [0.3103, 0.3448, 0.3793, 0.3448, 0.4531, 0.5645, 0.6600, 0.8324, 1.0540],
        4: [0.4864, 0.5404, 0.5944, 0.5404, 0.6387, 0.7703, 0.8843, 1.0710, 1.3362],
        5: [0.6544, 0.7271, 0.7998, 0.7271, 0.8253, 0.9688, 1.1004, 1.3372, 1.3362],
        6: [0.7938, 0.8820, 0.9702, 0.8820, 0.9800, 1.1349, 1.3524, 1.3372, 1.3362],
        7: [0.9702, 1.0780, 1.1858, 1.0780, 1.2005, 1.3436, 1.3524, 1.3372, 1.3362]
    }

    # Convert the data into a DataFrame
    long_term_slope = pd.DataFrame(long_term_slope)
    long_term_slope.set_index('m', inplace=True)

    long_term_fix = {
        'n': ['Sov+', 'Sov', 'Sov-', 'CC0', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5'],
        1: [0.3139, 0.3488, 0.3837, 0.3488, 0.3488, 0.3488, 0.3488, 0.3488, 0.3488],
        2: [0.3130, 0.3478, 0.3826, 0.3478, 0.3478, 0.3478, 0.3478, 0.3478, 0.3478],
        3: [0.3103, 0.3448, 0.3793, 0.3448, 0.3448, 0.3448, 0.3448, 0.3448, 0.3448],
        4: [0.3095, 0.3439, 0.3783, 0.3439, 0.3439, 0.3439, 0.3439, 0.3439, 0.3439],
        5: [0.6632, 0.7369, 0.8106, 0.7369, 0.7369, 0.7369, 0.7369, 0.7369, 0.7369],
        6: [1.0584, 1.1760, 1.2936, 1.1760, 1.1760, 1.1760, 1.1760, 1.1760, 1.1760],
        7: [1.5876, 1.7640, 1.9404, 1.7640, 1.7640, 1.7640, 1.7640, 1.7640, 1.7640]
    }

    # Convert the data into a DataFrame
    long_term_fix = pd.DataFrame(long_term_fix)
    long_term_fix.set_index('n', inplace=True)

    m_lang = long_term_slope.loc[buyer_cat, country_cat]
    n_lang = long_term_fix.loc[buyer_cat, country_cat]

    long_premium = round(m_lang * rlz_lang + n_lang, 2)
    formula_string = f"long-term premium = {m_lang} * RLZ + {n_lang}"

    return long_premium, formula_string

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
    warning_starting_point = "empty"
    warning_marketable_risk_short = "empty"
    warning_marketable_risk_long = "empty"
    starting_point = 0
    country_category = get_country_category(data.country, country_risk_df)
    if country_category is None:
        raise HTTPException(status_code=404, detail="Country not found")
    
     # Calculate basis for pre-ship and counter guarantees
    results = data.project_schedule.calculate_average()
    cover_amount_pre = results['Engineering']['value']+results['Equipment']['value']+results['Spares']['value']
    cover_amount_guar =  results['Engineering']['value']+results['Equipment']['value']+results['Spares']['value']+results['Erection']['value']+results['Assistance']['value']
    
    
    # Calculate pre-ship and counter guarantees
    fab_time = int(data.project_schedule.EquipmentStart)/4 if int(data.project_schedule.EquipmentStart)%4 == 0 else int(data.project_schedule.EquipmentStart)//4+1
    pre_ship_results = calculate_pre_ship(fab_time, country_category)
    pre_ship_cover = round(pre_ship_results["pre-ship"] * data.Selbstkosten / 100, 2)
    pre_ship_cover_eur = round(pre_ship_cover/100 * cover_amount_pre,2)
    guarantee_cover = round(pre_ship_results["counter_guar"] * data.Garantien / 100, 2)
    guar_cover_eur = round(guarantee_cover/100 * cover_amount_guar,2)

    
    if data.project_schedule.Commissioning >0:
        starting_point = data.project_schedule.Commissioning
    elif data.project_schedule.FAC>0:
        starting_point = data.project_schedule.FAC
    else:
        starting_point = 0
        warning_starting_point = "You have not defined a valid starting point. The calculation assumes a pre-risk period of 1 year."

    delivery_start = data.project_schedule.EquipmentStart
    delivery_end = data.project_schedule.EquipmentEnd
    vorlauf = (starting_point - data.project_schedule.EquipmentStart)/12 if starting_point>0 else 1 
    kreditlaufzeit = data.fin_tenor
    rlz_lang = vorlauf/2 + kreditlaufzeit
    rlz_string = f" risk tenor({rlz_lang}) = (starting point: ({starting_point}) - start delivery: ({data.project_schedule.EquipmentStart}))/24 + repayment tenor in years: ({data.fin_tenor})"
    
    if delivery_start and delivery_end:
        average_delivery = (delivery_start + delivery_end) / 2
    elif delivery_start:
        average_delivery = delivery_start 
    elif delivery_end:
        average_delivery = delivery_end
    
    # URL and section headers to start and stop at
    country = data.country.lower()
    url = f"https://www.exportkreditgarantien.de/en/country-information/{country}.html"
    start_header_text = "Short-term Business"
    end_header_text = "Secure Risks"

    # Fetch organized content
    organized_content = ""
    organized_content = fetch_and_organize_content_by_section(url, start_header_text, end_header_text)
    
    # Prepare response with pre-ship and counter guarantee
    response = {
        "Country:":data.country,
        "Country Category:": country_category,
        "further information:":organized_content,
        "Pre-shipment cover premium in % of contract price for deliveries (ENG, EQU, SP)": pre_ship_cover,
        "Pre-shipment cover premium in EUR": pre_ship_cover_eur,
        "Counter-guarantee cover premium in % of contract price (assuming guarantee percentages are on total contract price):": guarantee_cover,
        "Counter-guarantee cover premium in EUR:": guar_cover_eur,
        "payments": [],
        "total_post_ship":[],
        "financing": [] 
    }
    
    if country_category == 0:
        warning_marketable_risk_short = """
                                    You have selected an OECD high income country. 
                                    In these countries, short-term credit risks are considered 'marketable risks' for which no cover is provided by a government ECA. 
                                    For premium calculation, I will pursue with country category 1 as benchmark."""
        warning_marketable_risk_long = """
                                    You have selected an OECD high income country. 
                                    Long-term credit risks can be insured, the determination of the payable premium, however, may be subject to a so-called 'market test'. 
                                    For premium calculation, I will pursue with country category 1 as benchmark.
                                    """
        country_category = 1

    # Construct a new dictionary for each payment that includes the risk_tenor
    financing_cover_value, formula = calculate_long_term(country_category, data.buyer_cat, rlz_lang)
    financing_cover = round(financing_cover_value, 2)
    financing_info = {
            "starting point of repayment schedule in month:": starting_point,
            "loan tenor": data.fin_tenor,
            "loan amount in % of contract price": data.fin_amount,
            "risk tenor": rlz_string,
            "Post-shipment premium for medium- and long-term financing formula:": formula,
            "Post-shipment premium for medium- and long-term financing in % of contract price": financing_cover,
            "Warning marketable risk (if applicable):": warning_marketable_risk_long,
            "Warning missing starting point (if applicable):": warning_starting_point
        }
    post_ship_premium = 0
    post_ship_premium_eur = 0
    # For each payment tranche, calculate premiums
    results = data.project_schedule.calculate_average()
    for category in data.payments:
        category_name = category.schedule_item
        category_average = results[category_name]['average_month']
        category_value = results[category_name]['value']
        for payment in category.payments:
            average_delivery = category_average
            if payment.payment_month <= average_delivery:
                rlz = 0
            else:
                rlz = math.ceil(payment.payment_month - average_delivery)

            exception_list = ['down-payment', 'down payment', 'advance payment']
            if payment.name.lower() in exception_list:
                post_ship_prem = 0
                post_ship_prem_eur = 0
            else:
                post_ship_prem = round(calculate_short_term(country_category, data.buyer_cat, rlz) * payment.amount_percent / 100, 2)
                post_ship_prem_eur = round(post_ship_prem/100 * category_value,2)
        
            post_ship_premium += post_ship_prem
            post_ship_premium_eur += post_ship_prem_eur
            payment_info = {
            "Schedule Item:":category.schedule_item,
            "Installment name:": payment.name,
            "Payment month:": payment.payment_month,
            "Payment in %": payment.amount_percent,
            "Risk tenor:": rlz,
            "Post-shipment premium in %:": post_ship_prem,
            "Post-shipment premium in EUR:": post_ship_prem_eur,
            "Warning marketable risk (if applicable):": warning_marketable_risk_short,
            }
            response["payments"].append(payment_info)
    
    
    total_in_EUR = post_ship_premium_eur
    total_post = {
            "Total post-shipment premium in % of contract price": post_ship_premium,
            "Total post-shipment premium in EUR:":total_in_EUR
        }    
    response["total_post_ship"].append(total_post)
    response["financing"].append(financing_info)
    
    return response

@app.get("/")
def read_root():
    return {"Welcome": "Navigate to /docs for API usage."}

