"""
validation.py

Profile consistency validation helper module.
Validates logical consistency across profile fields (e.g. age, occupation, marital status, income).
"""

from typing import List, Dict, Any

def validate_profile_consistency(profile: Dict[str, Any], raw_text: str = "") -> List[str]:
    """
    Validates the user's profile for logical consistency.
    
    Returns a list of friendly warning/error messages. If empty, the profile is valid.
    """
    errors = []
    raw_text = str(raw_text).lower()

    # 1. Income validation
    income = profile.get("income")
    if income is not None:
        try:
            inc_val = float(income)
            if inc_val < 0:
                errors.append("Annual income cannot be negative. Please enter a valid income.")
        except (ValueError, TypeError):
            pass

    # 2. Age validation
    age = profile.get("age")
    if age is not None:
        try:
            age_val = int(age)
            if age_val < 1 or age_val > 120:
                errors.append("Please enter a valid age between 1 and 120.")
        except (ValueError, TypeError):
            pass

    # 3. Age & Occupation consistency
    occupation = profile.get("occupation")
    if age is not None and occupation is not None:
        try:
            age_val = int(age)
            occ_val = str(occupation).lower().strip()
            
            # Student checks
            is_college = "college" in raw_text or "university" in raw_text or "degree" in raw_text
            if occ_val == "student":
                if is_college and age_val < 16:
                    errors.append("College students are usually older than 16 years. Please verify your age or education details.")
                elif age_val < 3:
                    errors.append("A student cannot be under 3 years old. Please verify your age or occupation.")
            
            # Retired checks
            if occ_val == "retired" or "retired" in raw_text or "pensioner" in raw_text:
                if age_val < 40:
                    errors.append(f"A retired individual is typically older than 40 years. Your entered age is {age_val}. Please verify.")
                    
        except (ValueError, TypeError):
            pass

    # 4. Age & Marital Status consistency
    marital_status = profile.get("marital_status")
    if age is not None and marital_status is not None:
        try:
            age_val = int(age)
            mar_val = str(marital_status).lower().strip()
            
            if mar_val in ["married", "widowed", "widow", "divorced"] and age_val < 18:
                errors.append(f"Marital status is set to '{marital_status.capitalize()}', but the entered age is {age_val}. Legal age for marriage or widow status is usually 18 or older. Please verify.")
        except (ValueError, TypeError):
            pass
            
    return errors
