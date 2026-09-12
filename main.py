from collections  import Counter
import os
import requests
import pandas as pd
from pprint import pprint
from sqlalchemy import create_engine, text
import time


# The Api Credentials
app_id = os.getenv("ADZUNA_APP_ID")

app_key = os.getenv("ADZUNA_APP_KEY")

if not app_id or not app_key:
    raise ValueError("Adzuna API credentials are missing.")

MAX_DAILY_HITS = 150


# Set up the Request
COUNTRY = "gb"
page = 1



params = {
    "app_id": app_id,
    "app_key": app_key,
    "results_per_page": 20,
    "what": "data"
}

def load_jobs_to_database(df, engine):
    with engine.begin() as connection:
        # create the table if it does not exist
        connection.execute(
            text("""
                CREATE TABLE IF NOT EXISTS adzuna_jobs (
                    job_id VARCHAR PRIMARY KEY,
                    title VARCHAR,
                    company VARCHAR,
                    local_area VARCHAR,
                    broad_area VARCHAR,
                    category VARCHAR,
                    contract_type VARCHAR,
                    salary_min FLOAT,
                    salary_max FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE
                );
            """)
        )
        
        #insert or update the data
        connection.execute(
            text("""
                INSERT INTO adzuna_jobs (
                            job_id,
                            title,
                            company,
                            local_area,
                            broad_area,
                            category,
                            contract_type,
                            salary_min,
                            salary_max,
                            created_at
                        )
                        VALUES (
                            :job_id,
                            :title,
                            :company,
                            :local_area,
                            :broad_area,
                            :category,
                            :contract_type,
                            :salary_min,
                            :salary_max,
                            :created_at
                        )
                        ON CONFLICT (job_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        company = EXCLUDED.company,
                        local_area = EXCLUDED.local_area,
                        broad_area = EXCLUDED.broad_area,
                        category = EXCLUDED.category,
                        contract_type = EXCLUDED.contract_type,
                        salary_min = EXCLUDED.salary_min,
                        salary_max = EXCLUDED.salary_max,
                        created_at = EXCLUDED.created_at;
                    """),
            df.to_dict(orient="records")
        ) 



all_jobs = []
for page in range(1, MAX_DAILY_HITS + 1):
    
    url = f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search/{page}"
    response = requests.get(url, params=params)

    if response.status_code == 200:
    
        data = response.json()

        print(data["count"]) 
        job_list = data.get('results', [])

        for job in job_list:
            # We use .get() so if a field is missing, it returns None instead of crashing
            # extracting the complet location
            location = job.get("location", {})
            location_area = location.get("area", [])
            
            job_data = {
                "job_id" : job.get("id"),
                "title" : job.get("title"),
                "company" : job.get("company", {}).get("display_name"), 
                "local_area" : location.get("area", [])[2] if len(location.get("area", [])) > 2 else None,
                "broad_area" : location.get("area", [])[1] if len(location.get("area", [])) > 1 else None,
                "category" : job.get("category", {}).get("label"),
                "contract_type" : job.get("contract_time"),
                "salary_min" : job.get("salary_min"),
                "salary_max" : job.get("salary_max"),
                "created_at" : job.get("created")
            }
            
            # add the job_data to the clean_jobs list
            all_jobs.append(job_data)
            
    else:
        print(f"Page {page} failed with status code: {response.status_code}")
    
    time.sleep(1)  # to avoid hitting the API rate limit
        

    
df = pd.DataFrame(all_jobs)
    
# The Data Cleaning and Transformation phase 
# change the data type of the created_at column to datetime
df["created_at"] = pd.to_datetime(df["created_at"], utc=True)

df["contract_type"] = df["contract_type"].fillna("Not Specified")
df["local_area"] = df["local_area"].fillna("Not Specified")
df["broad_area"] = df["broad_area"].fillna("Not Specified")

#  Make sure salary columns are float and replace missing values with 0
df["salary_min"] = pd.to_numeric(
    df["salary_min"], errors="coerce"
).fillna(0).astype(float)

df["salary_max"] = pd.to_numeric(
    df["salary_max"], errors="coerce"
).fillna(0).astype(float)

text_columns = ["title", "company", "local_area", "broad_area", "category", "contract_type"]

for col in text_columns:
    df[col] = df[col].str.title()


# Testing the connection with the Supabase PostgreSQL database
DB_CONNECTION = os.getenv("DATABASE_URL")

if not DB_CONNECTION:
    raise ValueError("Database connection string is missing.")

try:
    engine = create_engine(DB_CONNECTION)

    # with engine.connect() as connection:
    #     print("Database connection successful!")

except Exception as e:
    print(f"Database error: {e}")
    

load_jobs_to_database(df, engine)



    
    
    
