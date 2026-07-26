import sqlite3
import random
import os

def initialize_database():
    db_path = os.path.join(os.path.dirname(__file__), "centers.db")
    print(f"Initializing database at: {db_path}")
    
    # Remove existing db if any to start fresh
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS application_centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_name TEXT NOT NULL,
            address TEXT NOT NULL,
            district TEXT NOT NULL,
            state TEXT NOT NULL,
            pincode TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            available_services TEXT NOT NULL
        )
    """)
    
    cities = [
        {"name": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lng": 80.2707, "pin_prefix": "60000", "type": "e-Sevai Center"},
        {"name": "Coimbatore", "state": "Tamil Nadu", "lat": 11.0168, "lng": 76.9558, "pin_prefix": "64100", "type": "e-Sevai Center"},
        {"name": "Madurai", "state": "Tamil Nadu", "lat": 9.9252, "lng": 78.1198, "pin_prefix": "62500", "type": "e-Sevai Center"},
        {"name": "Mumbai", "state": "Maharashtra", "lat": 18.9750, "lng": 72.8258, "pin_prefix": "40000", "type": "CSC Center"},
        {"name": "Pune", "state": "Maharashtra", "lat": 18.5204, "lng": 73.8567, "pin_prefix": "41100", "type": "CSC Center"},
        {"name": "Bangalore", "state": "Karnataka", "lat": 12.9716, "lng": 77.5946, "pin_prefix": "56000", "type": "Bangalore One Center"},
        {"name": "Patna", "state": "Bihar", "lat": 25.5941, "lng": 85.1376, "pin_prefix": "80000", "type": "Vasudha Kendra (CSC)"},
        {"name": "Kolkata", "state": "West Bengal", "lat": 22.5726, "lng": 88.3639, "pin_prefix": "70000", "type": "Tathya Mitra (CSC)"},
        {"name": "New Delhi", "state": "Delhi", "lat": 28.6139, "lng": 77.2090, "pin_prefix": "11000", "type": "Jeevan One Stop Center"},
        {"name": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8467, "lng": 80.9462, "pin_prefix": "22600", "type": "Jan Seva Kendra (CSC)"},
        {"name": "Hyderabad", "state": "Telangana", "lat": 17.3850, "lng": 78.4867, "pin_prefix": "50000", "type": "MeeSeva Center"},
        {"name": "Kochi", "state": "Kerala", "lat": 9.9312, "lng": 76.2673, "pin_prefix": "68200", "type": "Akshaya Kendra (CSC)"}
    ]

    services_list = [
        "Aadhaar Enrollment & Update, PAN Card, Voter ID, Income Certificate",
        "Community Certificate, Nativity Certificate, Old Age Pension Registration",
        "Crop Insurance, Land Records (Patta/Chitta), Utility Bill Payment",
        "Digital Signature, Passport Application Help, Driving License Services",
        "E-Shram Card, PM-Kisan Registration, Ayushman Bharat Card Generation",
        "Pensions Application, Widow Pension Registration, Disability Support Services"
    ]
    
    # Generate 100 centers for each city to reach 1,200 records
    centers = []
    random.seed(42)  # For deterministic generation
    
    for city in cities:
        for i in range(1, 101):
            # Coordinates are offset within a ~5 km radius around the city center
            # 0.045 degrees approx equals 5 km
            lat_offset = random.uniform(-0.045, 0.045)
            lng_offset = random.uniform(-0.045, 0.045)
            
            c_lat = city["lat"] + lat_offset
            c_lng = city["lng"] + lng_offset
            
            c_name = f"{city['type']} - Zone {i // 10 + 1} (Branch {i})"
            pincode = f"{city['pin_prefix']}{i % 9 + 1:d}"
            
            streets = [
                "M.G. Road", "Netaji Marg", "Gandhi Salai", "Station Road", 
                "Market Street", "J.N. Road", "Panchayat Office Road", 
                "Main Bazaar", "Civil Lines", "Lajpat Nagar Road"
            ]
            street = random.choice(streets)
            address = f"Shop No. {i}, Building {10 + i}, {street}, {city['name']}"
            
            district = city["name"]
            
            # Select 2 random service blocks from the list
            services = ", ".join(random.sample(services_list, 2))
            
            centers.append((
                c_name,
                address,
                district,
                city["state"],
                pincode,
                c_lat,
                c_lng,
                services
            ))
            
    cursor.executemany("""
        INSERT INTO application_centers (
            center_name, address, district, state, pincode, latitude, longitude, available_services
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, centers)
    
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM application_centers")
    count = cursor.fetchone()[0]
    print(f"Database successfully populated with {count} records.")
    
    conn.close()

if __name__ == "__main__":
    initialize_database()
