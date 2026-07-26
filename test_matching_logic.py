import os
import json
import logging
from dotenv import load_dotenv

# Set up logging to show debug statements
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv()

from logic import get_top_matches

def load_backup_schemes():
    path = os.path.join(os.path.dirname(__file__), "scheme_elligibility_engine", "schemes.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_tests():
    schemes = load_backup_schemes()
    print(f"Loaded {len(schemes)} candidate schemes.")
    
    test_cases = [
        {
            "name": "TEST 1: Farmer in Tamil Nadu",
            "profile": {
                "gender": "male",
                "marital_status": "single",
                "income": 50000.0,
                "state": "tamil nadu",
                "occupation": "farmer",
                "age": 35
            },
            "user_text": "Category: Farmer, State: Tamil Nadu, Age: 35, Gender: Male, Occupation: Farmer, Income: 50000, Land ownership: Yes"
        },
        {
            "name": "TEST 2: Engineering Student in Tamil Nadu",
            "profile": {
                "gender": "male",
                "marital_status": "single",
                "income": 80000.0,
                "state": "tamil nadu",
                "occupation": "student",
                "age": 20
            },
            "user_text": "Category: Engineering Student, State: Tamil Nadu, Age: 20, Gender: Male, Occupation: Student, Income: 80000"
        },
        {
            "name": "TEST 3: Profile that does not qualify for any scheme",
            "profile": {
                "gender": "male",
                "marital_status": "married",
                "income": 10000000.0,
                "state": "tamil nadu",
                "occupation": "unemployed",
                "age": 2
            },
            "user_text": "Category: Infant, State: Tamil Nadu, Age: 2, Gender: Male, Occupation: Unemployed, Income: 10000000"
        }
    ]
    
    for tc in test_cases:
        print(f"\n==================================================")
        print(f"RUNNING {tc['name']}")
        print(f"==================================================")
        print(f"Profile: {tc['profile']}")
        print(f"Input Text: '{tc['user_text']}'")
        
        results = get_top_matches(
            tc["profile"],
            schemes,
            top_n=10,
            user_text=tc["user_text"]
        )
        
        print(f"\nRESULTS MATCHED: {len(results)} schemes found")
        if not results:
            print("No eligible schemes found for your profile.")
        for i, res in enumerate(results):
            print(f"\n  {i+1}. {res['scheme_name']} ({res['match_score']}% Match)")
            print(f"     Why Matched: {res['why_matched']}")
            if res.get('why_not_matched'):
                print(f"     Unmatched/Details: {res['why_not_matched']}")

if __name__ == "__main__":
    run_tests()
