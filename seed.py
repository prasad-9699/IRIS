import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from faker import Faker
from database import get_db_context, init_db, get_db_path

CATEGORY_TEMPLATES = {
    "Electronics": {
        "adjectives": ["Ultra", "Pro", "Wireless", "Smart", "Compact", "Portable", "Digital", "High-Definition", "Fast-Charging", "Noise-Cancelling"],
        "items": ["Earbuds", "Headphones", "Bluetooth Speaker", "Mechanical Keyboard", "Gaming Mouse", "4K Webcam", "USB-C Hub", "Power Bank", "Smartwatch", "Wi-Fi 6 Router", "OLED Monitor", "Tablet Stand", "Laser Printer", "Microphone"],
        "min_price": 499.0,
        "max_price": 79999.0,
    },
    "Home & Kitchen": {
        "adjectives": ["Stainless Steel", "Non-Stick", "Ergonomic", "Smart", "Electric", "Eco-Friendly", "Cast Iron", "Ceramic", "Automatic", "Aroma"],
        "items": ["Air Fryer", "Espresso Machine", "Blender", "Cookware Set", "Electric Kettle", "Toaster", "Vacuum Cleaner", "Diffuser", "Knife Set", "Dinnerware Set", "Water Purifier", "Food Processor"],
        "min_price": 299.0,
        "max_price": 29999.0,
    },
    "Fashion": {
        "adjectives": ["Classic", "Slim-Fit", "Casual", "Vintage", "Waterproof", "Breathable", "Pure Cotton", "Thermal", "Comfortable", "Athletic"],
        "items": ["Denim Jacket", "Chino Pants", "Sneakers", "Leather Wallet", "Polarized Sunglasses", "Merino Sweater", "Linen Shirt", "Backpack", "Running Shoes", "Trench Coat", "Formal Belt", "Ankle Boots"],
        "min_price": 399.0,
        "max_price": 14999.0,
    },
    "Sports": {
        "adjectives": ["Heavy-Duty", "Lightweight", "Adjustable", "Pro-Grip", "Anti-Slip", "All-Weather", "Durable", "Speed", "Orthopedic", "Hydration"],
        "items": ["Yoga Mat", "Dumbbell Set", "Resistance Bands", "Badminton Racket", "Football", "Cycling Helmet", "Gym Bag", "Trekking Poles", "Jump Rope", "Foam Roller", "Water Bottle", "Tennis Racquet"],
        "min_price": 199.0,
        "max_price": 18999.0,
    },
    "Books": {
        "adjectives": ["The Art of", "Modern", "Essential", "Advanced", "The Practical Guide to", "Foundations of", "Handbook of", "Mastering", "Principles of", "The Architecture of"],
        "items": ["Distributed Systems", "Cloud Architecture", "Clean Code & Refactoring", "Machine Learning", "Database Internals", "Computer Networking", "Microservices Design", "High Performance Python", "UI/UX Design", "System Scalability", "Cybersecurity", "Data Structures"],
        "min_price": 249.0,
        "max_price": 4999.0,
    },
    "Beauty": {
        "adjectives": ["Hydrating", "Organic", "Nourishing", "Brightening", "Anti-Aging", "Gentle", "Herbal", "Radiance", "Vitamin C", "Pure"],
        "items": ["Facial Serum", "Moisturizer Cream", "Clay Mask", "Hair Treatment Oil", "Cleanser Gel", "Sunscreen SPF 50", "Eye Cream", "Lip Treatment", "Exfoliating Scrub", "Shampoo & Conditioner", "Body Butter"],
        "min_price": 149.0,
        "max_price": 6999.0,
    },
}

def generate_products(count: int = 700, seed: int = 42) -> list[dict]:
    """Generate realistic, diverse products using Faker with consistent pseudo-random seed."""
    fake = Faker()
    Faker.seed(seed)
    random.seed(seed)

    products = []
    seen_names = set()
    categories = list(CATEGORY_TEMPLATES.keys())

    # Reference time anchor
    now = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)

    for i in range(1, count + 1):
        category = categories[i % len(categories)]
        template = CATEGORY_TEMPLATES[category]

        # Generate unique product name
        for _ in range(50):
            adj = random.choice(template["adjectives"])
            item = random.choice(template["items"])
            suffix = random.choice(["Edition", "Series", "Model", "Plus", "Max", "Prime", "Elite", "Core", "V2", "Classic", "Lite", f"{random.randint(100, 990)}X"])
            name = f"{adj} {item} {suffix}"
            if name not in seen_names:
                seen_names.add(name)
                break
        else:
            name = f"{category} {item} #{i:04d}"
            seen_names.add(name)

        # Realistic description
        features = [
            f"Crafted with premium materials for maximum durability and performance.",
            f"Engineered for daily use with intuitive ergonomics and modern styling.",
            f"Includes manufacturer warranty and dedicated customer support.",
            f"Designed to exceed industry standards in efficiency and comfort.",
            f"Delivers exceptional quality and reliable performance every time.",
        ]
        description = f"{name}. {random.choice(features)} {fake.sentence(nb_words=12)}"

        # Realistic price
        price_raw = random.uniform(template["min_price"], template["max_price"])
        # Format as realistic consumer price ending in .99 or .00
        price = round(price_raw, 2)

        # Stock: ~12% out of stock (0), otherwise between 1 and 350
        is_out_of_stock = random.random() < 0.12
        stock = 0 if is_out_of_stock else random.randint(1, 350)

        # Rating: 1.5 to 5.0 rounded to 1 decimal
        rating = round(random.uniform(2.5, 5.0), 1)
        if random.random() < 0.05:
            rating = round(random.uniform(1.2, 2.4), 1)

        # Creation timestamp spread over past 400 days
        days_ago = random.randint(0, 400)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        seconds_ago = random.randint(0, 59)
        created_dt = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago, seconds=seconds_ago)
        created_at = created_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        products.append({
            "name": name,
            "description": description,
            "category": category,
            "price": price,
            "stock": stock,
            "rating": rating,
            "createdAt": created_at,
        })

    return products

def seed_database(db_path: str | None = None, count: int = 700, reset: bool = False, seed: int = 42) -> int:
    """Seed the database with realistic product records."""
    target_path = db_path or get_db_path()
    init_db(target_path)

    with get_db_context(target_path) as conn:
        cursor = conn.cursor()
        
        if reset:
            cursor.execute("DELETE FROM products;")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='products';")

        # Check existing records to avoid duplicates when seeding without reset
        cursor.execute("SELECT COUNT(*) AS total FROM products;")
        existing_count = cursor.fetchone()["total"]

        if existing_count >= count and not reset:
            print(f"[Seed] Database already has {existing_count} records. Pass --reset to clear and re-seed.")
            return existing_count

        products = generate_products(count=count, seed=seed)
        
        if not reset and existing_count > 0:
            # If not reset but count was less, only insert remaining
            products = products[existing_count:]

        cursor.executemany("""
            INSERT INTO products (name, description, category, price, stock, rating, createdAt)
            VALUES (:name, :description, :category, :price, :stock, :rating, :createdAt);
        """, products)

        cursor.execute("SELECT COUNT(*) AS total FROM products;")
        final_count = cursor.fetchone()["total"]
        print(f"[Seed] Successfully seeded {len(products)} products into '{target_path}'. Total records: {final_count}.")
        return final_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Product Catalog SQLite Database")
    parser.add_argument("--count", type=int, default=700, help="Number of products to generate (default: 700)")
    parser.add_argument("--reset", action="store_true", help="Clear existing products before seeding")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible data (default: 42)")
    args = parser.parse_args()

    seed_database(count=args.count, reset=args.reset, seed=args.seed)
