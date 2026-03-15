"""
Run this ONCE to:
1. Wipe the corrupt semantic_registry collection
2. Re-seed it with clean, correct entries

Usage:
    python seed_registry.py
"""

from app.db.database import semantic_registry_collection
from datetime import datetime

def seed():
    # ── Step 1: Wipe existing corrupt data ──────────────────────────
    result = semantic_registry_collection.delete_many({})
    print(f"Deleted {result.deleted_count} corrupt/duplicate entries")

    # ── Step 2: Clean seed data ──────────────────────────────────────
    entries = [
        {
            "key": "product_id",
            "aliases": ["product_id", "product id", "asin", "id", "prod_id"],
            "description": "Unique product identifier (ASIN or internal ID)",
            "data_type": "categorical"
        },
        {
            "key": "product_name",
            "aliases": ["product_name", "product name", "name", "item_name", "item name", "title"],
            "description": "Name or title of the product",
            "data_type": "categorical"
        },
        {
            "key": "product_description",
            "aliases": ["product_description", "product description", "about_product",
                        "about product", "description", "details", "product_details"],
            "description": "Detailed description or about section of the product",
            "data_type": "categorical"
        },
        {
            "key": "category",
            "aliases": ["category", "category_name", "category name", "product_category",
                        "product category", "type", "genre", "department"],
            "description": "Product category or classification",
            "data_type": "categorical"
        },
        {
            "key": "discounted_price_numeric",
            "aliases": ["discounted_price", "discounted price", "sale_price", "sale price",
                        "selling_price", "selling price", "offer_price", "offer price",
                        "discount_price", "discount price"],
            "description": "Numeric discounted/sale price (currency symbol removed)",
            "data_type": "numeric"
        },
        {
            "key": "actual_price_numeric",
            "aliases": ["actual_price", "actual price", "original_price", "original price",
                        "mrp", "list_price", "list price", "price_numeric", "price"],
            "description": "Numeric original/MRP price before discount",
            "data_type": "numeric"
        },
        {
            "key": "discount_pct",
            "aliases": ["discount_percentage", "discount percentage", "discount_pct",
                        "discount pct", "discount", "off_percentage", "off percentage"],
            "description": "Discount percentage (e.g. 64 for 64% off)",
            "data_type": "numeric"
        },
        {
            "key": "rating",
            "aliases": ["rating", "avg_rating", "average rating", "star_rating",
                        "star rating", "product_rating", "product rating", "stars"],
            "description": "Average customer rating score (e.g. 4.2 out of 5)",
            "data_type": "numeric"
        },
        {
            "key": "rating_count",
            "aliases": ["rating_count", "rating count", "rating_count_int",
                        "num_ratings", "number of ratings", "total_ratings",
                        "total ratings", "no_of_ratings", "ratings"],
            "description": "Total number of customer ratings",
            "data_type": "numeric"
        },
        {
            "key": "review_id",
            "aliases": ["review_id", "review id", "review_id_list", "review id list"],
            "description": "Unique identifier(s) for customer reviews",
            "data_type": "categorical"
        },
        {
            "key": "review_title",
            "aliases": ["review_title", "review title", "review_summary", "review summary"],
            "description": "Short title or summary of the customer review",
            "data_type": "categorical"
        },
        {
            "key": "review_text",
            "aliases": ["review_content", "review content", "review_text", "review text",
                        "review", "feedback", "customer_review", "customer review"],
            "description": "Full text of the customer review",
            "data_type": "categorical"
        },
        {
            "key": "user_id",
            "aliases": ["user_id", "user id", "customer_id", "customer id",
                        "buyer_id", "buyer id"],
            "description": "Unique identifier for the user/customer",
            "data_type": "categorical"
        },
        {
            "key": "user_name",
            "aliases": ["user_name", "user name", "username", "customer_name",
                        "customer name", "reviewer_name", "reviewer name"],
            "description": "Display name of the user or reviewer",
            "data_type": "categorical"
        },
        {
            "key": "product_link",
            "aliases": ["product_link", "product link", "product_url", "product url",
                        "img_link", "image_link", "image link", "url", "link"],
            "description": "URL link to the product page or image",
            "data_type": "categorical"
        },
        {
            "key": "region",
            "aliases": ["region", "area", "location", "zone", "territory",
                        "state", "city", "country", "geography"],
            "description": "Geographic region or location",
            "data_type": "categorical"
        },
        {
            "key": "transaction_date",
            "aliases": ["transaction_date", "transaction date", "date", "order_date",
                        "order date", "purchase_date", "purchase date", "created_at",
                        "timestamp", "time", "sale_date", "sale date", "saledate",
                        "sales_date", "sales date", "invoice_date", "invoice date"],
            "description": "Date or timestamp of the transaction or record",
            "data_type": "date"
        },
        {
            "key": "quantity",
            "aliases": ["quantity", "qty", "count", "units", "amount",
                        "stock", "inventory", "items_sold", "items sold",
                        "units_sold", "units sold", "qty_sold", "qty sold",
                        "num_items", "num items", "pieces_sold", "pieces sold"],
            "description": "Quantity or count of items",
            "data_type": "numeric"
        },
        {
            "key": "revenue",
            "aliases": ["revenue", "sales", "total_sales", "total sales",
                        "gross_revenue", "gross revenue", "income", "earnings",
                        "total_value", "total value", "sale_value", "sale value",
                        "order_value", "order value", "transaction_value", "transaction value"],
            "description": "Total revenue or sales amount",
            "data_type": "numeric"
        },
    ]

    # ── Step 3: Insert with timestamp ───────────────────────────────
    now = datetime.utcnow()
    for entry in entries:
        entry["created_at"] = now
        semantic_registry_collection.insert_one(entry)

    print(f"Seeded {len(entries)} clean registry entries")
    print("\nKeys seeded:")
    for e in entries:
        print(f"  {e['key']:35s} → aliases: {e['aliases'][:3]}{'...' if len(e['aliases']) > 3 else ''}")


if __name__ == "__main__":
    seed()