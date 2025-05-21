from dotenv import load_dotenv
from openai import OpenAI
import os
import fitz  # PyMuPDF
import base64
import csv
from PIL import Image
import io

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variables
API_KEY = os.getenv('OPEN_AI_API_KEY')
if not API_KEY:
    raise ValueError("OPEN_AI_API_KEY not found in .env file")

# Initialize OpenAI client
client = OpenAI(api_key=API_KEY)

def encode_image(image_bytes):
    """Convert image bytes to base64 string."""
    return base64.b64encode(image_bytes).decode("utf-8")

def crop_top_portion(image_bytes, percentage=30):
    """Crop the top portion of an image."""
    # Convert bytes to PIL Image
    image = Image.open(io.BytesIO(image_bytes))
    
    # Calculate crop height (30% of total height)
    width, height = image.size
    crop_height = int(height * (percentage / 100))
    
    # Crop the image
    cropped_image = image.crop((0, 0, width, crop_height))
    
    # Convert back to bytes
    img_byte_arr = io.BytesIO()
    cropped_image.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def check_product_page(page_image_base64: str) -> bool:
    """
    Uses GPT to determine if the page is a product page.
    Returns True if it is a product page, False otherwise.
    """
    prompt = """
    Is this page a product page? Look for:
    - Product diagrams or images
    
    Return exactly 'yes' if this is a product page, 'no' if it is not.
    """
    
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    { "type": "text", "text": prompt },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{page_image_base64}"
                        },
                    },
                ],
            }
        ],
        max_tokens=10
    )
    
    return completion.choices[0].message.content.strip().lower() == 'yes'

def extract_product_info(cropped_image_base64: str) -> tuple:
    """
    Extract manufacturer and product name from the cropped top portion of the page.
    Returns (manufacturer, product_name)
    """
    prompt = """
    Look at the top portion of this product page and identify:
    1. The manufacturer name (usually the largest text at the top)
    2. The product name(s) (usually the second largest text)
    
    If the product name is not noticeably larger it is not the product name so return 'Unknown' for the product name.
    
    If there are multiple products on the page, return them all as one product. So if it says A & B, return both in A & B format.
    
    Return the information in this exact format, with each product on its own line:
    Manufacturer: [name]
    Product: [name1] or Product: [name1] & [name2] etc.
    
    Include only alphanumeric characters and spaces in the product and manufacturer names.
    If you can't identify either, use 'Unknown' for that field.
    """
    
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    { "type": "text", "text": prompt },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{cropped_image_base64}"
                        },
                    },
                ],
            }
        ],
        max_tokens=200
    )
    
    response = completion.choices[0].message.content.strip()
    
    # Parse the response
    manufacturer = "Unknown"
    products = []
    
    for line in response.split('\n'):
        if line.startswith('Manufacturer:'):
            manufacturer = line.replace('Manufacturer:', '').strip()
        elif line.startswith('Product:'):
            product = line.replace('Product:', '').strip()
            if product != "Unknown":
                products.append(product)
    
    # If no products found, add Unknown
    if not products:
        products = ["Unknown"]
    
    return manufacturer, products

def clean_csv(csv_path: str):
    """
    Clean the CSV file by:
    1. Removing any lines where either Product Name or Manufacturer is 'Unknown'
    2. Removing duplicate product names, keeping only the first occurrence
    3. Removing special characters like '' and '®' from all fields
    """
    # Read all rows from the CSV
    rows = []
    seen_products = set()
    with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Get the header
        
        # First filter out Unknown entries and clean special characters
        valid_rows = []
        for row in reader:
            # Skip if either product name or manufacturer is 'Unknown'
            if row[0] == 'Unknown' or row[1] == 'Unknown':
                continue
                
            # Clean special characters from each field
            cleaned_row = [field.replace('', '').replace('®', '').strip() for field in row]
            valid_rows.append(cleaned_row)
        
        # Then filter out duplicates
        for row in valid_rows:
            product_name = row[0]  # Product name is first column
            if product_name not in seen_products:
                seen_products.add(product_name)
                rows.append(row)
    
    # Write back only the valid, unique rows
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        writer.writerows(rows)
    
    print(f"Cleaned CSV: Removed {len(valid_rows) - len(rows)} duplicate entries")

def has_submittal_text(page) -> bool:
    """
    Check if the page contains the word 'submittal' but not 'model',
    or contains 'Bill of Material' or 'BOM'.
    Returns True if should skip, False otherwise.
    """
    text = page.get_text().lower()
    has_submittal = 'submittal' in text
    has_model = 'model' in text
    has_bom = 'bill of material' in text or 'bom' in text
    
    # Skip if has submittal but no model, or has BOM
    return (has_submittal and not has_model) or has_bom

def process_pdf(pdf_path: str, output_csv: str):
    """
    Process a PDF file and write results to CSV.
    """
    doc = fitz.open(pdf_path)
    print(f"\nProcessing: {pdf_path}")
    print(f"Total pages: {len(doc)}")
    
    # Create results directory if it doesn't exist
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    
    # Create CSV file
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Product Name', 'Manufacturer', 'Page Number'])
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            print(f"Processing page {page_num + 1}")
            
            # Pre-check for skip conditions
            if has_submittal_text(page):
                skip_reason = "contains 'Bill of Material' or 'BOM'" if 'bill of material' in page.get_text().lower() or 'bom' in page.get_text().lower() else "contains 'submittal' but no 'model'"
                print(f"Page {page_num + 1}: Skipped ({skip_reason})")
                continue
            
            # Convert page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            base64_image = encode_image(img_bytes)
            
            # Check if it's a product page
            is_product_page = check_product_page(base64_image)
            
            if is_product_page:
                # Crop top 30% and extract product info
                cropped_bytes = crop_top_portion(img_bytes)
                cropped_base64 = encode_image(cropped_bytes)
                manufacturer, products = extract_product_info(cropped_base64)
                
                # Write each product as a separate row
                for product in products:
                    writer.writerow([product, manufacturer, page_num + 1])
                    print(f"Page {page_num + 1}: {product} - {manufacturer}")
    
    doc.close()
    
    # Clean the CSV file
    clean_csv(output_csv)
    print(f"\nResults saved to: {output_csv}")

if __name__ == "__main__":
    # List of PDFs to process
    pdf_files = [
        "input/230000-001 HVAC Submittal.pdf",
        "input/283100-001 Fire Alarm Shops and PD Submittal.pdf", 
        "input/KP OLAB 220523-001 Plumbing Piping Valves FA.pdf"
    ]
    
    # Create results directory if it doesn't exist
    os.makedirs("results", exist_ok=True)
    
    while True:
        print("\nAvailable PDFs:")
        for i, pdf in enumerate(pdf_files, 1):
            print(f"{i}. {os.path.basename(pdf)}")
        print(f"{len(pdf_files) + 1}. Process all PDFs")
        print("0. Exit")
        
        try:
            choice = int(input("\nSelect a PDF to process (0 to exit): "))
            
            if choice == 0:
                print("Exiting...")
                break
            elif choice == len(pdf_files) + 1:
                # Process all PDFs
                print("\nProcessing all PDFs...")
                for pdf_file in pdf_files:
                    try:
                        output_csv = pdf_file.replace('.pdf', '_products.csv').replace('input/', 'results/')
                        process_pdf(pdf_file, output_csv)
                    except Exception as e:
                        print(f"Error processing {pdf_file}: {str(e)}")
            elif 1 <= choice <= len(pdf_files):
                # Process single PDF
                pdf_file = pdf_files[choice - 1]
                try:
                    output_csv = pdf_file.replace('.pdf', '_products.csv').replace('input/', 'results/')
                    process_pdf(pdf_file, output_csv)
                except Exception as e:
                    print(f"Error processing {pdf_file}: {str(e)}")
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
