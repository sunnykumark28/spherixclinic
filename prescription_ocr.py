import os
import json
import base64
import re
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_BASE = os.getenv('GROQ_API_BASE', 'https://api.groq.com/openai/v1')
GROQ_API_MODEL = os.getenv('GROQ_API_MODEL', 'llama3-8b-8192')
GOOGLE_VISION_API_KEY = os.getenv('GOOGLE_VISION_API_KEY')

def extract_text_from_image(image_path: str) -> str:
    """
    Extract raw text from a prescription image using Google Cloud Vision API,
    with a fallback to Groq Vision API if Google Cloud Vision is not configured.
    """
    if not image_path or not os.path.exists(image_path):
        print(f"⚠️ Prescription image path does not exist: {image_path}")
        return ""

    # Try Google Cloud Vision API first
    if GOOGLE_VISION_API_KEY and GOOGLE_VISION_API_KEY != 'none':
        try:
            from google.cloud import vision
            
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
                
            client = vision.ImageAnnotatorClient(
            client_options={"api_key": GOOGLE_VISION_API_KEY}
            )
            request_dict = {
                "image": {"content": content},
                "features": [
                    {"type_": vision.Feature.Type.TEXT_DETECTION},
                ],
            }
            response = client.annotate_image(request=request_dict)
            if response.text_annotations:
                text = response.text_annotations[0].description
                print("✅ Successfully extracted text using Google Cloud Vision API.")
                return text
        except Exception as e:
            print(f"⚠️ Google Cloud Vision OCR failed: {e}. Trying fallback...")
            
    # Try Groq Vision API as a fallback
    if GROQ_API_KEY and GROQ_API_KEY != 'none':
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
            mime_type = "image/jpeg"
            if str(image_path).lower().endswith(".png"):
                mime_type = "image/png"
                
            endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            models_to_try = [
                "qwen/qwen3.6-27b",
                "meta-llama/llama-4-scout-17b-16e-instruct"
            ]
            
            for model in models_to_try:
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Read the text from this prescription image and return only the raw text visible on the page. Be precise and include all medicine names."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{encoded_string}"
                                    }
                                }
                            ]
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024
                }
                response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
                if response.ok:
                    data = response.json()
                    text = data['choices'][0]['message']['content']
                    print(f"✅ Successfully extracted text using Groq Vision API fallback with model {model}.")
                    return text
        except Exception as e:
            print(f"⚠️ Groq Vision OCR fallback failed: {e}")

    print("⚠️ No OCR provider succeeded or was configured.")
    return ""

def parse_medicines_with_groq(raw_text: str) -> list:
    """
    Use Groq API to parse medicine names from the raw OCR text.
    Returns a list of dictionaries with key 'medicine_name'.
    """
    if not raw_text.strip():
        return []

    if not GROQ_API_KEY or GROQ_API_KEY == 'none':
        print("⚠️ Groq API key not configured. Cannot parse medicines.")
        return []

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = (
        "Extract all names of medicines or pharmaceutical drugs from the following raw OCR text of a medical prescription. "
        "Return the list as a valid JSON array of objects, where each object has a single key 'medicine_name'.\n"
        "Example Output format:\n"
        "[\n"
        "  {\"medicine_name\": \"Amoxicillin\"},\n"
        "  {\"medicine_name\": \"Ibuprofen\"}\n"
        "]\n"
        "Do not include any conversational explanation, markdown blocks (other than the json block), or extra text outside the JSON list.\n"
        f"Raw OCR text:\n{raw_text}"
    )
    
    payload = {
        "model": GROQ_API_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 512
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        if response.ok:
            data = response.json()
            content = data['choices'][0]['message']['content'].strip()
            
            # Clean up potential markdown formatting block
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            medicines = json.loads(content)
            if isinstance(medicines, list):
                # Clean up and validate that each entry is dict and contains 'medicine_name'
                cleaned_medicines = []
                for item in medicines:
                    if isinstance(item, dict) and 'medicine_name' in item:
                        cleaned_medicines.append(item)
                return cleaned_medicines
    except Exception as e:
        print(f"⚠️ Failed to parse medicines using Groq completion: {e}")
        
    # Regex fallback if API fails or parsing fails
    # Try to find words that look like drug names (usually capitalized, 4+ letters)
    print("⚠️ Attempting regex fallback for medicine parsing.")
    words = re.findall(r'\b[A-Z][a-z]{3,}\b', raw_text)
    # Filter out common non-drug English words or headers
    stop_words = {'Prescription', 'Doctor', 'Patient', 'Name', 'Date', 'Address', 'Clinic', 'Hospital', 'Phone', 'Email', 'Medical', 'Tablet', 'Capsule', 'Syrup', 'Mg', 'Mgml'}
    medicines = [{'medicine_name': word} for word in set(words) if word not in stop_words]
    return medicines
