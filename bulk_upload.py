import os
import uuid
import time
from supabase import create_client

# Supabase Credentials
SUPABASE_URL = "https://xhipfasywzgkmpoogaaz.supabase.co"
SUPABASE_KEY = "sb_publishable_K1MGEBgEhHL50VGjS5pipQ_JJfWFDhc"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

image_folder = "optimized_images"
STORE_NAME = "Tokens General Hub"

files = [f for f in os.listdir(image_folder) if f.endswith(".webp")]
total_files = len(files)
print(f"Found {total_files} images to upload. Starting batch process...\n")

for index, filename in enumerate(files, start=1):
    file_path = os.path.join(image_folder, filename)
    storage_path = f"general/{filename}"
    
    success = False
    retries = 3
    
    for attempt in range(1, retries + 1):
        try:
            with open(file_path, "rb") as f:
                supabase.storage.from_("products").upload(
                    path=storage_path, 
                    file=f, 
                    file_options={"content-type": "image/webp", "upsert": "true"}
                )
            
            public_url_res = supabase.storage.from_("products").get_public_url(storage_path)
            image_url = public_url_res if isinstance(public_url_res, str) else public_url_res.get("publicURL", "")

            clean_name = os.path.splitext(filename)[0].replace("_", " ").title()
            product_id = str(uuid.uuid4())[:8]

            product_data = {
                "id": product_id,
                "store_name": STORE_NAME,
                "item_name": clean_name,
                "description": f"High-quality {clean_name.lower()} ready for fast local delivery.",
                "price": 499,
                "category": "General",
                "image_url": image_url
            }
            
            supabase.table("products").insert(product_data).execute()
            print(f"[{index}/{total_files}] Successfully uploaded: {clean_name}")
            success = True
            break

        except Exception as e:
            if attempt < retries:
                print(f"[{index}/{total_files}] Attempt {attempt} failed for {filename}. Retrying...")
                time.sleep(2)
            else:
                print(f"[{index}/{total_files}] ❌ Failed {filename}: {e}")

    time.sleep(0.5)

print("\nAll batch operations completed! 🚀")