import os
from PIL import Image

# Configuration
input_folder = "raw_images"       
output_folder = "optimized_images" 
max_size = (800, 800)             
quality_setting = 80              

os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):
    if filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        input_path = os.path.join(input_folder, filename)
        
        base_name = os.path.splitext(filename)[0]
        safe_name = "".join(c for c in base_name if c.isalnum() or c in ('._-')).strip()
        output_filename = f"{safe_name}.webp"
        output_path = os.path.join(output_folder, output_filename)
        
        try:
            with Image.open(input_path) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                img.save(output_path, "WEBP", quality=quality_setting, method=6)
                
                print(f"Optimized: {filename} -> {output_filename}")
        except Exception as e:
            print(f"Failed to process {filename}: {e}")

print("All images successfully optimized!")