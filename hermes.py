
import pandas as pd
import requests
from bs4 import BeautifulSoup

# The URL of the page you want to scrape
url = 'https://www.exportkreditgarantien.de/en/solutions/costs/country-risk-categories.html'

##------------Data and Tables --------------------

def calculate_pre_ship(FBZ):
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
    
    return pd.DataFrame(pre_ship_cover_calc)

def calculate_short_term(country_cat, buyer_cat, rlz):

    # Define the data as a dictionary
    short_term_slope = {
        'm': ['Sov+', 'Sov', 'Sov-', 'CC0', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5'],
        1: [0.0086, 0.0095, 0.0105, 0.0095, 0.0165, 0.0218, 0.0254, 0.0345, 0.051],
        2: [0.0092, 0.0102, 0.0112, 0.0102, 0.018, 0.0234, 0.0302, 0.0395, 0.0553],
        3: [0.0125, 0.0139, 0.0153, 0.0139, 0.0208, 0.0279, 0.0337, 0.0459, 0.0622],
        4: [0.0197, 0.0219, 0.0241, 0.0219, 0.0279, 0.0367, 0.044, 0.0574, 0.0773],
        5: [0.0334, 0.0371, 0.0409, 0.0371, 0.0426, 0.0518, 0.0601, 0.0771, 0],
        6: [0.0465, 0.0517, 0.0569, 0.0517, 0.0562, 0.0655, 0.08, 0, 0],
        7: [0.0682, 0.0758, 0.0834, 0.0758, 0.0806, 0.0871, 0, 0, 0]
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
        5: [1.17, 1.3, 1.43, 1.3, 1.37, 1.43, 1.5, 1.56, None],
        6: [1.53, 1.7, 1.87, 1.7, 1.79, 1.87, 1.96, None, None],
        7: [1.89, 2.1, 2.31, 2.1, 2.23, 2.36, None, None, None]
    }

    # Convert the data into a DataFrame
    short_term_fix = pd.DataFrame(short_term_fix)
    short_term_fix.set_index('n', inplace=True)
    
    m = short_term_slope.loc[buyer_cat, country_cat]
    n = short_term_fix.loc[buyer_cat, country_cat]

    premium = round(m * rlz + n, 2)
    

    return premium

# Fetch the content from the URL
response = requests.get(url)

# Use BeautifulSoup to parse the HTML content
soup = BeautifulSoup(response.text, 'html.parser')


# Find all tables on the page
tables = soup.find_all('table')

# Initialize an empty list to store the data
all_data = []

# Loop through each table
for table in tables[1:-1]:
    # Assuming the table is standard with rows (<tr>) and cells (<td> or <th>), iterate over it
    rows = table.find_all('tr')
    # Skip the first row (header)
    for row in rows[1:]:
        cells = row.find_all(['td', 'th'])  # Find both td and th elements
        data = [cell.text.strip().replace("./.", "0") for cell in cells]
        all_data.append(data)

# Convert the list of lists into a DataFrame
df = pd.DataFrame(all_data)

#----------------Eingaben--------------------

country = "Argentina" #input("which country: ")
FBZ = 5 #float(input("number of 3 months periods (1.5 years are 5): "))/4
Selbstkosten = 85 #int(input("Eingabe Selbstkosten in %:  "))
Garantien = 20 #int(input("Garantievolumen außer Anzahlungsgarantie in %: "))
Zahlungsrate = 85 #float(input("Zahlungsrate in %: "))
rlz = 1 #int(input("Risikolaufzeit in Monaten (Ganzzahl): "))
buyer_cat = "CC2" #input("Buyer Category - choose: 'Sov+', 'Sov', 'Sov-', 'CC0', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5'")

#----------------Berechnungen---------------
# Filter the DataFrame to return rows matching the specified country
country_df = df[df[0] == country]

# Extract the category for the specified country
category = int(country_df.iloc[0, 1]) if not country_df.empty else None

pre_ship_cover_calc = calculate_pre_ship(FBZ)
# row = pre_ship_cover_calc.loc[category]


# print(row)

# Assuming 'pre_ship' and 'counter_guar' are column names
pre_ship_value = round(pre_ship_cover_calc.loc[category, 'pre-ship'] * Selbstkosten/100, 2)
counter_guar_value = round(pre_ship_cover_calc.loc[category, 'counter_guar'] * Garantien/100,2)
post_ship_premium = round(calculate_short_term(category, buyer_cat, rlz)*Zahlungsrate/100,2)

#-----------Ausgaben------------------

print(f"Category for {country}: {category}")
print("Pre-ship cover premium in % of contract price:", pre_ship_value)
print("Counter guarantee cover premium in % of contract price:", counter_guar_value)
print("Short term cover premium in % of contract price:", post_ship_premium)