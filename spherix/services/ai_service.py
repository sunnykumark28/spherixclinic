import os
import sys
import json
import re
import hashlib
import requests
import time as time_module
from datetime import datetime
from flask import current_app, session

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_BASE = os.getenv('GROQ_API_BASE', 'https://api.groq.com/openai/v1')
GROQ_API_MODEL = os.getenv('GROQ_API_MODEL', 'openai/gpt-oss-20b')
AI_PROVIDER = os.getenv('AI_PROVIDER', 'GROQ').strip().upper()

def _is_groq_configured():
    return bool(GROQ_API_KEY and GROQ_API_KEY != 'none')

def _determine_ai_provider():
    if _is_groq_configured():
        return 'GROQ'
    return None

AI_PROVIDER_ACTIVE = _determine_ai_provider()

GOOGLE_VISION_API_KEY = os.getenv('GOOGLE_VISION_API_KEY')
ENABLE_IMAGE_ANALYSIS = os.getenv('ENABLE_IMAGE_ANALYSIS', 'true').lower() == 'true'
OPENFDA_API_KEY = os.getenv('OPENFDA_API_KEY')

try:
    from google.cloud import vision
except ImportError:
    vision = None

def _is_vision_configured():
    return bool(GOOGLE_VISION_API_KEY and vision and ENABLE_IMAGE_ANALYSIS)

# Initialize the new SymptomAnalyzer (global instance for reuse)
try:
    from symptoms_analyzer import SymptomAnalyzer
    analyzer = SymptomAnalyzer()
    print("✅ SymptomAnalyzer initialized for advanced diagnosis")
except ImportError:
    analyzer = None
    print("⚠️ SymptomAnalyzer not available - using local fallback only")
except Exception as e:
    analyzer = None
    print(f"⚠️ Error initializing SymptomAnalyzer: {e}")

def analyze_symptoms_locally(symptoms_query, age=None, gender=None):
    """
    Local fallback analyzer when SymptomAnalyzer is not available.
    Does not require API calls or a loaded knowledge base.
    """
    # This function is now a final, simple fallback.
    return {
        "conditions": ["General Consultation Recommended"],
        "confidence_scores": [40],
        "advice": "Your symptoms require professional medical evaluation. The AI analysis engine is currently unavailable. Please consult a healthcare provider for accurate diagnosis and treatment.",
        "description": "Unable to perform analysis as the required AI services and local knowledge base are unavailable.",
        "self_care": ["Rest", "Stay hydrated", "Monitor symptoms"],
        "suggested_medicines": ["Consult healthcare provider"],
        "when_to_see_doctor": "It is recommended to see a healthcare provider to properly diagnose your symptoms, especially if they persist or worsen.",
        "recommended_departments": ["General Medicine"],
        "note": "⚠️ The AI analysis engine is offline. This is a generic recommendation."
    }

# ============ CACHING & RATE LIMITING FOR AI APIs ============
SYMPTOM_CACHE = {}  # Cache for symptom analysis results
ACTIVE_SYMPTOM_REPORTS = {}  # Global in-memory cache for full un-truncated symptom reports
LAST_API_CALL_TIME = {}  # Track last API call time per user

def get_cache_key(symptoms_query, age, gender, height=None, weight=None):
    """Generate a hash-based cache key from symptoms and patient info."""
    cache_str = f"{symptoms_query}:{age}:{gender}:{height}:{weight}"
    return hashlib.md5(cache_str.encode()).hexdigest()


def _extract_json_payload(text):
    """Extract JSON object from AI response text safely with resilient cleaning and auto-repair."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    
    # 1. Check for markdown code fence extraction first
    code_fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if code_fence_match:
        candidate = code_fence_match.group(1).strip()
        try:
            return json.loads(candidate, strict=False)
        except Exception:
            pass

    # 2. Direct parse attempt
    try:
        return json.loads(text, strict=False)
    except Exception:
        pass

    # 3. Strip any outer markdown fences if present
    cleaned = text
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        if len(lines) > 1 and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()
        try:
            return json.loads(cleaned, strict=False)
        except Exception:
            pass

    # 4. Extract substring between first '{' and last '}'
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate, strict=False)
        except Exception:
            # 4b. Clean trailing commas e.g. ", }" -> " }"
            try:
                sanitized = re.sub(r',\s*([\]}])', r'\1', candidate)
                return json.loads(sanitized, strict=False)
            except Exception:
                pass

    # 5. Resilient truncation repair (if response was cut off mid-JSON)
    if start != -1:
        candidate = text[start:]
        open_braces = candidate.count('{') - candidate.count('}')
        open_brackets = candidate.count('[') - candidate.count(']')
        candidate = re.sub(r',\s*$', '', candidate.strip())
        if candidate.count('"') % 2 != 0:
            candidate += '"'
        if open_brackets > 0:
            candidate += ']' * open_brackets
        if open_braces > 0:
            candidate += '}' * open_braces
        try:
            sanitized = re.sub(r',\s*([\]}])', r'\1', candidate)
            return json.loads(sanitized, strict=False)
        except Exception:
            pass

    return None



def _analyze_image_with_vision(image_path):
    """
    Analyze symptoms from an image using Google Vision API.
    Returns visual findings relevant to medical analysis.
    """
    if not _is_vision_configured():
        return None
    
    try:
        # Read image file
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        # Create Vision client with API key
        client = vision.ImageAnnotatorClient(
            client_options={"api_key": GOOGLE_VISION_API_KEY}
        )
        
        # Perform multiple analyses for comprehensive results using dictionary format
        request_dict = {
            "image": {"content": content},
            "features": [
                {"type_": vision.Feature.Type.LABEL_DETECTION},
                {"type_": vision.Feature.Type.TEXT_DETECTION},
                {"type_": vision.Feature.Type.OBJECT_LOCALIZATION},
                {"type_": vision.Feature.Type.SAFE_SEARCH_DETECTION},
            ],
        }
        
        response = client.annotate_image(request=request_dict)
        
        # Extract relevant findings
        findings = {
            'visual_elements': [],
            'text_found': '',
            'objects_detected': [],
            'analysis': ''
        }
        
        # Get labels (what's visible in the image)
        if response.label_annotations:
            findings['visual_elements'] = [
                label.description for label in response.label_annotations[:5]
            ]
        
        # Extract text from image (OCR)
        if response.text_annotations:
            findings['text_found'] = response.text_annotations[0].description[:500]
        
        # Get objects detected
        if response.localized_object_annotations:
            findings['objects_detected'] = [
                obj.name for obj in response.localized_object_annotations[:3]
            ]
        
        # Build analysis description from findings
        analysis_parts = []
        if findings['visual_elements']:
            analysis_parts.append(f"Visual indicators: {', '.join(findings['visual_elements'])}")
        if findings['text_found']:
            analysis_parts.append(f"Text visible in image: {findings['text_found'][:100]}...")
        if findings['objects_detected']:
            analysis_parts.append(f"Objects identified: {', '.join(findings['objects_detected'])}")
        
        findings['analysis'] = ' '.join(analysis_parts) or "Image analyzed successfully"
        
        print(f"✅ Image analysis complete: {findings['analysis'][:100]}...")
        return findings
        
    except Exception as e:
        print(f"❌ Image analysis error: {e}")
        return None

def _analyze_image_with_groq_vision(image_path, custom_prompt=None):
    """Fallback image analysis using Groq Vision API."""
    if not _is_groq_configured():
        return {'error': 'GROQ_API_KEY is not configured.'}

    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        mime_type = "image/jpeg"
        if str(image_path).lower().endswith(".png"):
            mime_type = "image/png"

        endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
        if "responses" in endpoint:
            endpoint = endpoint.replace("responses", "chat/completions")
            
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Try active multimodal models
        models_to_try = [
            "qwen/qwen3.6-27b",
            "meta-llama/llama-4-scout-17b-16e-instruct"
        ]

        last_error = "No models attempted"
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": custom_prompt or "Analyze this image for any visible medical symptoms, skin conditions, or relevant health indicators. Be objective and concise. Note: This is for an AI symptom checker."
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
                "temperature": 0.2,
                "max_tokens": 1024
            }
            try:
                print(f"🔄 Attempting Groq Vision analysis with model: {model}...")
                response = requests.post(endpoint, headers=headers, json=payload, timeout=45, verify=True)
                if response.ok:
                    data = response.json()
                    analysis_text = data['choices'][0]['message']['content']
                    print(f"✅ Groq Vision analysis complete (with {model}): {analysis_text[:100]}...")
                    return {
                        'analysis': analysis_text
                    }
                else:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', error_msg)
                    except Exception:
                        pass
                    last_error = f"API Error ({model}): {error_msg}"
                    print(f"⚠️ Groq Vision model {model} failed: {last_error}")
            except Exception as e:
                last_error = f"Request Error ({model}): {str(e)}"
                print(f"⚠️ Groq Vision model {model} request failed: {last_error}")

        # If all models fail
        print(f"❌ All Groq Vision models failed. Last error: {last_error}")
        return {'error': last_error}
    except Exception as e:
        print(f"❌ Groq Vision analysis error: {e}")
        return {'error': str(e)}

def _invoke_groq_symptom_analysis(symptoms_query, age=None, gender=None, height=None, weight=None):
    """Call Groq API for symptom analysis and normalize output schema."""
    if not _is_groq_configured():
        return None

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")

    prompt = f"""You are a professional medical triage assistant. Analyze these patient symptom details and produce a JSON object ONLY. Output valid JSON without any markdown formatting like ```json.

symptoms: {symptoms_query}
age: {age or 'unknown'}
gender: {gender or 'unknown'}
height: {height or 'unknown'} cm
weight: {weight or 'unknown'} kg

CRITICAL INSTRUCTION: Explicitly tailor your diagnosis, advice, and warnings to a patient of this specific age, biological sex, height, and weight. Consider gender-specific conditions, hormonal factors, physiological risk factors, and BMI-related implications if applicable.

Required keys:
- conditions: list of 1-3 probable condition names (strings)
- confidence_scores: list of numeric probabilities matching conditions (0-100)
- advice: concise medical advice for the user.
- description: short explanation of likely condition.
- pathophysiology: concise explanation (1-2 sentences) of the underlying physiological mechanism or bodily cause.
- differential_analysis: list of short distinctions for why each probable condition was considered.
- self_care: list of 3 practical self-care steps.
- dietary_guidelines: object with "recommended" (list of 2-3 recovery foods/fluids) and "avoid" (list of 2-3 foods/substances to avoid).
- suggested_medicines: list of safe over-the-counter suggestions (non-prescriptive).
- when_to_see_doctor: red-flags with urgency guidance.
- triage_timeline: short expected progression or recovery timeline (e.g. 24-48h monitoring window).
- recommended_departments: list of relevant specialty departments.
- note: short caution that this is not a diagnosis.
"""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.25,
        'max_tokens': 2048,
        'response_format': {'type': 'json_object'}
    }

    try:
        print(f"📤 Calling Groq API at: {endpoint}")
        print(f"📤 With model: {GROQ_API_MODEL}, headers: Authorization={GROQ_API_KEY[:20]}...")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()

        output_text = _extract_groq_text_response(payload_json)
        if not output_text:
            raise ValueError('Groq response has no content')

        parsed = _extract_json_payload(output_text)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError('Groq response could not be parsed as JSON')

        conditions = parsed.get('conditions') if isinstance(parsed.get('conditions'), list) else [parsed.get('conditions')] if parsed.get('conditions') else ['Non-specific symptoms']
        
        # Clean and normalize confidence scores, handling concatenated formats like 702010 -> 70, 20, 10
        raw_scores = parsed.get('confidence_scores')
        if not isinstance(raw_scores, list):
            if raw_scores is not None:
                raw_scores = [raw_scores]
            else:
                raw_scores = []
        
        cleaned_scores = []
        for val in raw_scores:
            try:
                val_int = int(val)
                if val_int > 100:
                    s = str(val_int)
                    pairs = []
                    idx = 0
                    while idx < len(s):
                        if len(s) - idx == 1:
                            pairs.append(int(s[idx:]))
                            idx += 1
                        else:
                            val_pair = int(s[idx:idx+2])
                            if val_pair <= 100:
                                pairs.append(val_pair)
                                idx += 2
                            else:
                                pairs.append(int(s[idx:idx+1]))
                                idx += 1
                    if all(0 <= p <= 100 for p in pairs):
                        cleaned_scores.extend(pairs)
                        continue
                cleaned_scores.append(val_int if 0 <= val_int <= 100 else 60)
            except (ValueError, TypeError):
                cleaned_scores.append(60)
                
        if len(cleaned_scores) < len(conditions):
            cleaned_scores = cleaned_scores + [55] * (len(conditions) - len(cleaned_scores))
        elif len(cleaned_scores) > len(conditions):
            cleaned_scores = cleaned_scores[:len(conditions)]

        result = {
            'conditions': conditions,
            'confidence_scores': cleaned_scores,
            'advice': parsed.get('advice') or parsed.get('recommendation') or 'Please consult a medical professional.',
            'description': parsed.get('description') or 'Symptom pattern analysis from Groq AI.',
            'pathophysiology': parsed.get('pathophysiology') or 'Acute physiological response and cellular inflammatory mediation in affected tissue structures.',
            'differential_analysis': parsed.get('differential_analysis') if isinstance(parsed.get('differential_analysis'), list) else [],
            'self_care': parsed.get('self_care') if isinstance(parsed.get('self_care'), list) else ['Monitor symptoms', 'Stay hydrated', 'If symptoms worsen, seek healthcare.'],
            'dietary_guidelines': parsed.get('dietary_guidelines') if isinstance(parsed.get('dietary_guidelines'), dict) else {
                'recommended': ['Hydrate adequately with electrolyte-balanced fluids', 'Warm broths or soothing herbal infusions', 'Easily digestible, nutrient-dense whole foods'],
                'avoid': ['Excessive caffeine, refined sugars, and alcohol', 'Greasy or heavily spiced irritants', 'Unpasteurized or ultra-processed items']
            },
            'suggested_medicines': parsed.get('suggested_medicines') if isinstance(parsed.get('suggested_medicines'), list) else ['Rest', 'Hydration', 'Gentle pain relief'],
            'when_to_see_doctor': parsed.get('when_to_see_doctor') or 'Visit a doctor if symptoms worsen or persist beyond 48 hours.',
            'triage_timeline': parsed.get('triage_timeline') or 'Monitor progression actively over 24-48 hours. Most uncomplicated presentations improve within 5-7 days.',
            'recommended_departments': parsed.get('recommended_departments') if isinstance(parsed.get('recommended_departments'), list) else ['General Medicine'],
            'note': parsed.get('note') or 'This is an AI-generated suggestion and not a medical diagnosis.',
        }

        return result

    except Exception as e:
        print(f"⚠️ Groq analysis failed: {e}")
        return {
            'conditions': ['AI Service Unavailable'],
            'confidence_scores': [0],
            'advice': 'Could not complete analysis via Groq API. Please verify API key and network connectivity.',
            'description': 'Groq API call error.',
            'self_care': ['Check your network and API key', 'Retry the analysis', 'Consult a healthcare professional in-person if urgent'],
            'suggested_medicines': ['Consult a doctor'],
            'when_to_see_doctor': 'Contact healthcare provider if condition appears serious.',
            'recommended_departments': ['General Medicine'],
            'note': str(e),
            'error_details': str(e)
        }


def _extract_groq_text_response(payload_json):
    if not isinstance(payload_json, dict):
        return ''
    if 'choices' in payload_json and len(payload_json['choices']) > 0:
        choice = payload_json['choices'][0]
        if isinstance(choice, dict):
            if 'message' in choice and isinstance(choice['message'], dict):
                msg = choice['message']
                content = msg.get('content')
                if content and str(content).strip():
                    return str(content)
                reasoning = msg.get('reasoning')
                if reasoning and str(reasoning).strip():
                    return str(reasoning)
            if 'text' in choice and choice['text']:
                return str(choice['text'])
    output_text = payload_json.get('output_text')
    if not output_text:
        output = payload_json.get('output', [])
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict) and item.get('type') == 'message':
                    content = item.get('content', [])
                    if isinstance(content, list):
                        for content_item in content:
                            if isinstance(content_item, dict) and content_item.get('type') == 'output_text':
                                output_text = content_item.get('text', '')
                                break
                    break
    return output_text or ''



def _invoke_groq_symptom_followup(symptoms_context, followup_question, age=None, gender=None):
    """Call Groq API to answer a follow-up chat question about symptoms."""
    if not _is_groq_configured():
        return 'AI follow-up unavailable because Groq API is not configured.'

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")
    prompt = f"""You are a professional medical triage assistant. Use the following patient symptom summary and current AI analysis to answer the follow-up question clearly and safely.

Patient info:
- Age: {age or 'unknown'}
- Gender: {gender or 'unknown'}

Current symptom summary:
{symptoms_context}

Follow-up question:
{followup_question}

Respond in plain text only. Provide a concise answer, include any necessary caution, and mention when the user should seek medical help or finalize the result."""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.25,
        'max_tokens': 512
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()
        return _extract_groq_text_response(payload_json).strip() or 'The AI assistant could not generate a response. Please try again.'
    except Exception as e:
        print(f"⚠️ Groq follow-up chat failed: {e}")
        return 'AI follow-up unavailable at the moment. Please try again later.'


def _invoke_groq_symptom_finalization(result, chat_history, age=None, gender=None):
    """Call Groq API to create a finalized summary based on the analysis and chat context."""
    if not _is_groq_configured():
        return result.get('clinical_summary') or result.get('description') or 'Finalized result is unavailable because AI service is not configured.'

    summary_parts = [result.get('clinical_summary') or result.get('description', ''), 'Recommendations: ' + '; '.join(result.get('ai_recommendations', []))]
    if result.get('warning_alerts'):
        summary_parts.append('Warnings: ' + '; '.join(result.get('warning_alerts', [])))
    chat_section = '\n'.join([f"Patient: {entry['message']}\nAI: {entry['response']}" for entry in chat_history[-5:]]) if chat_history else 'No follow-up chat history.'

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")
    prompt = f"""You are a professional medical triage assistant. Create a finalized patient-facing summary for the following symptom analysis and follow-up chat.

Patient info:
- Age: {age or 'unknown'}
- Gender: {gender or 'unknown'}

Current summary and recommendations:
{chr(10).join(part for part in summary_parts if part)}

Recent follow-up chat:
{chat_section}

Write a concise final result statement that includes the most critical diagnosis points, next steps, and whether this should be reviewed by a specialist or saved in a PDF report. Use plain text only."""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.25,
        'max_tokens': 512
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()
        return _extract_groq_text_response(payload_json).strip() or (result.get('clinical_summary') or result.get('description') or 'Finalized summary generation failed.')
    except Exception as e:
        print(f"⚠️ Groq finalization failed: {e}")
        return result.get('clinical_summary') or result.get('description') or 'Finalized result could not be generated.'


def _invoke_groq_drug_info(drug_name):
    """Call Groq API to generate a drug information summary."""
    if not _is_groq_configured():
        return None

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")
    prompt = f"""You are a professional medical reference assistant. Provide a JSON object only, no markdown or extra text.

Drug name: {drug_name}

Required keys:
- drug_name: string
- description: string
- primary_use: concise primary medical use or indication
- common_side_effects: list of 3-5 common side effects
- caution: short caution statement, including when to consult a doctor
- clinical_notes: brief note about important usage or safety information
- usage_instructions: step-by-step instructions on how to use/take the medicine
- dosage_interval: clinical advice on how much time to wait before reuse (interval/frequency)
"""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.25,
        'max_tokens': 2048
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()

        output_text = payload_json.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not output_text:
            raise ValueError('Groq response has no content')

        parsed = _extract_json_payload(output_text)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError('Groq response could not be parsed as JSON')

        return {
            'drug_name': parsed.get('drug_name', drug_name),
            'description': parsed.get('description', 'No description available.'),
            'primary_use': parsed.get('primary_use', 'General medication use.'),
            'common_side_effects': parsed.get('common_side_effects') if isinstance(parsed.get('common_side_effects'), list) else [],
            'caution': parsed.get('caution', 'Consult a healthcare professional before use.'),
            'clinical_notes': parsed.get('clinical_notes', ''),
            'usage_instructions': parsed.get('usage_instructions', 'Refer to packaging or professional advice.'),
            'dosage_interval': parsed.get('dosage_interval', 'Consult a healthcare professional for exact dosage intervals.'),
            'source': 'ai'
        }
    except Exception as e:
        print(f"❌ Groq drug info generation failed: {e}")
        return None


def _invoke_openfda_drug_info(drug_name):
    """Call OpenFDA API to get authoritative drug information with robust normalization."""
    if not drug_name:
        return None

    # Clean the drug name to remove non-ASCII dashes, special characters, dosages, forms
    raw_str = str(drug_name)
    # Replace non-breaking hyphens (\u2010-\u2015, \u2212) and weird whitespace with standard ASCII
    clean_str = re.sub(r'[\u2010-\u2015\u2212]', '-', raw_str)
    clean_str = re.sub(r'[^\x00-\x7F]+', ' ', clean_str)

    search_term = clean_str.split('(')[0].split(',')[0].strip()
    
    # Split by common conjunctions to isolate the primary medication
    search_term = re.split(r'(?i)\b(or|and|with|for)\b', search_term)[0].strip()
    
    # Remove numbers and common units (e.g., "200mg", "3 times", "3")
    search_term = re.sub(r'\b\d+([a-zA-Z]+)?\b', '', search_term).strip()
    
    # Remove common non-drug terms
    stop_words = r'(?i)\b(topical|gel|cream|ointment|applied|every|hours|for|pain|relief|daily|times|mg|ml|mcg|tablet|capsule|oral|syrup|without|food|water|nasal|decongestant|spray|drops|suppository|inhaler|cough|cold|medication|fatty|acids|acid)\b'
    search_term = re.sub(stop_words, '', search_term).strip()
    
    # Keep alphanumeric characters only, removing trailing/leading dashes or punctuation
    search_term = re.sub(r'[^a-zA-Z0-9\s]', ' ', search_term).strip()
    search_term = re.sub(r'\s+', ' ', search_term).strip()
    
    # Fallback if stripped too aggressively
    if len(search_term) < 3:
        fallback_words = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in clean_str.split()]
        valid_words = [w for w in fallback_words if len(w) >= 3]
        search_term = valid_words[0] if valid_words else ""

    if not search_term or len(search_term) < 2:
        return None

    # Keep to max 2 words for exact search
    words = search_term.split()
    if len(words) > 2:
        search_term = " ".join(words[:2])

    endpoint = "https://api.fda.gov/drug/label.json"
    # Safe quoted query
    query = f'openfda.brand_name:"{search_term}" OR openfda.generic_name:"{search_term}"'
    params = {'search': query, 'limit': 1}
    
    if OPENFDA_API_KEY:
        params['api_key'] = OPENFDA_API_KEY
        
    try:
        response = requests.get(endpoint, params=params, timeout=8)
        
        # If 404 or 400 with multi-words, try searching just the first word
        if response.status_code in (400, 404) and len(words) > 1:
            fallback_term = words[0]
            query = f'openfda.brand_name:"{fallback_term}" OR openfda.generic_name:"{fallback_term}"'
            params['search'] = query
            response = requests.get(endpoint, params=params, timeout=8)
            
        if response.status_code >= 400:
            return None

        data = response.json()
        if not data.get('results'):
            return None
            
        result = data['results'][0]
        openfda = result.get('openfda', {})
        
        brand_name = openfda.get('brand_name', [drug_name])[0]
        indications = result.get('indications_and_usage', [''])[0]
        description = result.get('description', [''])[0]
        if not description:
            description = indications if indications else 'No detailed description available.'
            
        adverse = result.get('adverse_reactions', [''])[0]
        if adverse:
            adverse = adverse.replace('\n', ' ').replace('•', '')
            side_effects = [s.strip().capitalize() for s in adverse.split(',') if s.strip() and len(s) < 50][:5]
            if not side_effects:
                side_effects = [adverse[:150] + "..."]
        else:
            side_effects = []
            
        warnings = result.get('warnings', ['Consult a healthcare professional before use.'])[0]
        dosage = result.get('dosage_and_administration', ['Refer to packaging or professional advice.'])[0]
        
        def truncate(text, length=250):
            if not text: return ""
            text = text.replace('\n', ' ').strip()
            return text[:length] + "..." if len(text) > length else text
            
        return {
            'drug_name': brand_name.title(),
            'description': truncate(description, 400),
            'primary_use': truncate(indications, 200) or 'General medication use.',
            'common_side_effects': side_effects if side_effects else ['See package insert for full side effects list.'],
            'caution': truncate(warnings, 200),
            'clinical_notes': truncate(result.get('boxed_warning', [''])[0], 200),
            'usage_instructions': truncate(dosage, 300),
            'dosage_interval': truncate(result.get('how_supplied', ['Consult a healthcare professional for exact dosage intervals.'])[0], 200),
            'source': 'OpenFDA API'
        }
    except Exception:
        return None


def _generate_fallback_condition_info(condition_name):
    """Generate a medically structured 15-section fallback monograph when external AI API is unavailable."""
    clean_name = (condition_name or 'Clinical Health Condition').strip().title()
    return {
        'condition_name': clean_name,
        'overview': f"{clean_name} is a clinically identified health condition characterized by distinct physiological mechanisms and symptomatic patterns. A thorough clinical evaluation and evidence-based diagnostic verification are essential for optimal health management and timely recovery.",
        'key_facts': [
            f"{clean_name} presents with identifiable localized or systemic clinical indicators.",
            "Early diagnostic consultation and personalized intervention significantly improve long-term outcomes.",
            "Standard protocols incorporate evidence-based pharmacotherapy, nutritional support, and rest.",
            "Consultation with a certified medical doctor is strongly advised for definitive diagnosis."
        ],
        'symptoms': {
            'description': f"Clinical manifestations of {clean_name} may range from mild transient discomfort to acute symptomatic presentations.",
            'list': [
                "Localized discomfort, soreness, or acute irritation",
                "Systemic fatigue and diminished baseline energy",
                "Inflammatory or physiological response in the affected area",
                "Transient fluctuations in vital comfort and activity tolerance"
            ]
        },
        'causes': [
            "Pathophysiological triggers or localized inflammatory cascade activation",
            "Environmental exposures, acute lifestyle stressors, or physical strain",
            "Immune response variations or metabolic susceptibility",
            "Infectious pathogens or acute biochemical imbalances"
        ],
        'risk_factors': [
            "Genetic or familial predisposition",
            "Elevated occupational, environmental, or psychological stress",
            "Pre-existing comorbidities or weakened immune defense",
            "Suboptimal nutrition, irregular sleep cycles, or dehydration"
        ],
        'diagnosis': [
            "Comprehensive physical examination and clinical history intake",
            "Targeted laboratory investigations (complete blood counts, inflammatory markers)",
            "Diagnostic imaging (Ultrasound, X-ray, or CT scan as clinically indicated)",
            "Standardized clinical symptom severity scoring"
        ],
        'prevention': [
            "Maintain balanced nutrition and adequate systemic hydration",
            "Adhere to routine health screenings and preventive wellness checkups",
            "Implement ergonomic and stress-reduction protocols",
            "Practice proper hygiene and minimize exposure to known environmental triggers"
        ],
        'specialist_to_visit': {
            'primary_specialist': "General Physician / Specialist Consultant",
            'department': "General Medicine / Clinical Specialties",
            'when_urgent': "Seek emergency clinical care immediately if experiencing persistent high fever, acute severe pain, shortness of breath, or rapidly worsening symptoms."
        },
        'treatment': {
            'overview': f"Multi-modal therapeutic approach tailored to the individual severity of {clean_name}.",
            'medications': [
                "Targeted symptomatic pharmacotherapy as prescribed by a licensed clinician",
                "Supportive anti-inflammatory and analgesic medications",
                "Hydration and electrolyte restorative solutions"
            ],
            'procedures': [
                "Clinical monitoring and diagnostic follow-up",
                "Non-invasive therapeutic interventions as indicated"
            ],
            'therapies': [
                "Targeted restorative physical therapy if musculoskeletal involvement exists",
                "Guided rest and recuperation schedule"
            ]
        },
        'complications': [
            "Progression to chronic or recurrent symptomatic episodes if left unaddressed",
            "Secondary infection or heightened inflammatory burden",
            "Impaired daily functional capacity and prolonged recovery duration"
        ],
        'alternative_therapies': [
            "Evidence-based therapeutic herbal teas and warm compress applications",
            "Gentle yoga, breathing exercises, and mindfulness meditation",
            "Physiotherapy and ergonomic posture support"
        ],
        'home_care': [
            "Prioritize adequate restorative sleep (7-9 hours nightly)",
            "Maintain continuous fluid intake with water and electrolyte broths",
            "Avoid strenuous physical exertion during the acute phase",
            "Keep a daily log of symptom frequency and temperature readings"
        ],
        'living_with': [
            "Schedule regular follow-up consultations with your primary healthcare team",
            "Establish consistent daily wellness routines and balanced meals",
            "Maintain open communication with family and caregivers regarding symptom patterns"
        ],
        'faqs': [
            {
                'question': f"How quickly can one recover from {clean_name}?",
                'answer': "Recovery timelines vary based on individual health baseline, symptom severity, and prompt adherence to clinical care plans."
            },
            {
                'question': "When should I consult a doctor immediately?",
                'answer': "Immediate evaluation is warranted if you experience persistent high fever, sudden sharp pain, shortness of breath, or neurological symptoms."
            }
        ],
        'references': [
            "World Health Organization (WHO) Clinical Guidelines",
            "National Institutes of Health (NIH) Medical Encyclopedia",
            "Centers for Disease Control and Prevention (CDC) Health Protocols",
            "Spherix Clinic Evidence-Based Medicine Guidelines"
        ],
        # Compatibility keys
        'description': f"{clean_name} is a clinically identified health condition. Timely medical assessment, diagnostic verification, and structured management are essential for optimal health outcomes.",
        'self_care': [
            "Prioritize adequate restorative sleep",
            "Maintain continuous hydration",
            "Avoid strenuous physical exertion during the acute phase"
        ],
        'when_to_see_doctor': "Seek urgent clinical care if symptoms worsen rapidly or do not subside within 48-72 hours.",
        'source': 'Spherix Clinical Reference Standard'
    }


def _invoke_groq_condition_info(condition_name):
    """Call Groq API to generate a comprehensive 15-section clinical disease monograph with robust fallback."""
    if not condition_name:
        return _generate_fallback_condition_info("General Health Condition")

    if not _is_groq_configured():
        return _generate_fallback_condition_info(condition_name)

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")

    prompt = f"""You are a senior clinical consultant and medical encyclopedia editor. Provide a strictly valid JSON object (no markdown code fences, no extra conversational text) providing an exhaustive, medically accurate monograph for the condition: "{condition_name}".

The JSON MUST contain exactly these 15 keys:
1. "overview": (string) 1-2 paragraphs explaining what the condition is, clinical definition, pathophysiology, and who is affected.
2. "key_facts": (list of 4 strings) Concise clinical facts, prevalence, or key demographic insights.
3. "symptoms": (object with "description" string and "list" array of 4-6 strings) Detailed symptom presentation.
4. "causes": (list of 4 strings) Underlying etiology, biological triggers, pathogens, or physiological mechanisms.
5. "risk_factors": (list of 4 strings) Predisposing factors (age, lifestyle, comorbidities).
6. "diagnosis": (list of 4 strings) Clinical evaluation methods, physical exams, and lab/imaging tests.
7. "prevention": (list of 4 strings) Evidence-based prevention strategies and lifestyle modifications.
8. "specialist_to_visit": (object with "primary_specialist" string, "department" string, and "when_urgent" string) Recommended medical specialty and urgency guidance.
9. "treatment": (object with "overview" string, "medications" list of 3-4 strings, "procedures" list of 2-3 strings, and "therapies" list of 2-3 strings).
10. "complications": (list of 3-4 strings) Serious acute or chronic sequelae if unmanaged.
11. "alternative_therapies": (list of 3 strings) Evidence-based supportive modalities.
12. "home_care": (list of 4 strings) Actionable at-home self-care measures and rest protocols.
13. "living_with": (list of 3 strings) Long-term management and daily lifestyle adjustments.
14. "faqs": (list of 2-3 objects with "question" string and "answer" string) Common patient questions.
15. "references": (list of 3 strings) Authoritative medical references (e.g. WHO, NIH, CDC).

Ensure the output is 100% valid JSON."""

    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [
            {'role': 'system', 'content': 'You are a medical database API. You must respond strictly with valid JSON. Do not include markdown formatting or commentary.'},
            {'role': 'user', 'content': prompt}
        ],
        'response_format': {'type': 'json_object'},
        'temperature': 0.2,
        'max_tokens': 3500
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()

        output_text = payload_json.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not output_text:
            raise ValueError('Groq response has no content')

        parsed = _extract_json_payload(output_text)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError('Groq response could not be parsed as JSON')

        # Populate legacy & helper keys for seamless template rendering
        parsed['condition_name'] = condition_name
        if not parsed.get('description'):
            parsed['description'] = parsed.get('overview', '')
        if not parsed.get('self_care'):
            parsed['self_care'] = parsed.get('home_care', [])
        if not parsed.get('when_to_see_doctor'):
            spec = parsed.get('specialist_to_visit')
            if isinstance(spec, dict):
                parsed['when_to_see_doctor'] = spec.get('when_urgent', '')
            elif isinstance(spec, str):
                parsed['when_to_see_doctor'] = spec
        parsed['source'] = 'Groq AI Clinical Monograph'

        return parsed
    except Exception as e:
        print(f"⚠️ Groq 15-section condition monograph generation encountered issue: {e}. Falling back to structured clinical database.")
        return _generate_fallback_condition_info(condition_name)


def get_ml_analysis(symptoms_query, age=None, gender=None, image_path=None, height=None, weight=None):
    """
    Primary symptom analyser: Groq API only. No local knowledge base fallback.
    """
    print(f"📚 Analyzing symptoms via {AI_PROVIDER_ACTIVE or 'local fallback'}: '{symptoms_query}' [age={age}, gender={gender}, height={height}, weight={weight}]")

    vision_findings = None
    if image_path:
        local_image_path = os.path.join(current_app.root_path, image_path.lstrip('/'))

        # Analyze image with Google Vision API using the absolute path
        if os.path.exists(local_image_path):
            vision_findings = _analyze_image_with_vision(local_image_path)

        # If Google Vision is not configured or fails, try Groq Vision API
        if not vision_findings:
            print("⚠️ Google Vision not available or failed. Attempting Groq Vision API...")
            groq_findings = _analyze_image_with_groq_vision(local_image_path) if os.path.exists(local_image_path) else None
            if groq_findings and 'analysis' in groq_findings:
                vision_findings = groq_findings
                
        if vision_findings:
            session['symptom_vision_findings'] = vision_findings
            # Enhance symptoms_query with image analysis findings
            enhanced_query = f"{symptoms_query}\n\nVisual Analysis: {vision_findings.get('analysis', '')}"
            # Use enhanced query for Groq analysis
            symptoms_query = enhanced_query
            print(f"✅ Enhanced symptom query with image analysis")
        else:
            print("⚠️ Image analysis failed, proceeding with text analysis only")

    # Check cache first
    cache_key = get_cache_key(symptoms_query, age, gender, height, weight)
    if cache_key in SYMPTOM_CACHE:
        print(f"✅ Using cached AI result for key: {cache_key}")
        cached = SYMPTOM_CACHE[cache_key]
        if vision_findings and 'vision_findings' not in cached:
            cached['vision_findings'] = vision_findings
        return cached

    # Rate limiting: ensure at least 10 seconds between API calls
    current_time = time_module.time()
    if 'global' in LAST_API_CALL_TIME:
        time_since_last = current_time - LAST_API_CALL_TIME['global']
        if time_since_last < 10:  # 10 second minimum interval
            wait_time = 10 - time_since_last
            print(f"⏳ Rate limiting: waiting {wait_time:.1f}s before API call")
            time_module.sleep(wait_time)

    if AI_PROVIDER_ACTIVE != 'GROQ' or not _is_groq_configured():
        print("⚠️ Groq API is not configured. Falling back to local SymptomAnalyzer.")
        if analyzer:
            fallback_res = analyzer.analyze(symptoms_query, age=age, gender=gender, body_part=None)
        else:
            fallback_res = analyze_symptoms_locally(symptoms_query, age=age, gender=gender)
        if vision_findings and isinstance(fallback_res, dict):
            fallback_res['vision_findings'] = vision_findings
        return fallback_res

    result = _invoke_groq_symptom_analysis(symptoms_query, age, gender, height, weight)

    if result and 'error_details' not in result:
        if vision_findings:
            result['vision_findings'] = vision_findings
        # Enrich suggested medicines with OpenFDA side effects
        if 'suggested_medicines' in result and isinstance(result['suggested_medicines'], list):
            enhanced_medicines = []
            for med in result['suggested_medicines']:
                med_name = str(med).split('-')[0].split('(')[0].split(',')[0].strip()
                skip_words = ['rest', 'hydration', 'none', 'n/a', 'consult', 'water', 'sleep', 'fluid', 'monitor', 'warm', 'tea', 'honey']
                if not any(sw in med_name.lower() for sw in skip_words) and len(med_name) > 3:
                    fda_info = _invoke_openfda_drug_info(med_name)
                    if fda_info and fda_info.get('common_side_effects'):
                        effects = [e for e in fda_info['common_side_effects'] if 'package insert' not in e.lower() and len(e) < 60]
                        if effects:
                            side_effects_str = ", ".join(effects[:2])
                            enhanced_medicines.append(f"{med} (Possible side effects: {side_effects_str.lower()})")
                            continue
                enhanced_medicines.append(med)
            result['suggested_medicines'] = enhanced_medicines

        LAST_API_CALL_TIME['global'] = time_module.time()
        SYMPTOM_CACHE[cache_key] = result
        return result

    print("❌ Groq analysis failed. Falling back to local SymptomAnalyzer.")
    if analyzer:
        return analyzer.analyze(symptoms_query, age=age, gender=gender, body_part=None)
    else:
        # Final fallback to the most basic local analyzer
        return analyze_symptoms_locally(symptoms_query, age=age, gender=gender)


def _parse_text_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r'[\n;]+', str(value)) if item.strip()]


def _normalize_text(value):
    if value is None:
        return ''
    if isinstance(value, list):
        return ' '.join(str(item) for item in value if item)
    return str(value)


def _derive_risk_level(severity, duration, when_to_see_doctor, conditions):
    if severity:
        normalized = _normalize_text(severity).lower()
        if any(token in normalized for token in ['very severe', 'severe', 'high', 'urgent', 'intense']):
            return '🔴 High'
        if any(token in normalized for token in ['moderate', 'persistent', 'ongoing']):
            return '🟡 Moderate'
        return '🟢 Low'

    if when_to_see_doctor:
        warning_text = _normalize_text(when_to_see_doctor).lower()
        if any(token in warning_text for token in ['immediate', 'emergency', 'urgent', 'difficulty breathing', 'chest pain', 'loss of consciousness']):
            return '🔴 High'
        if any(token in warning_text for token in ['monitor', 'follow up', 'persistent', 'recurring']):
            return '🟡 Moderate'

    if duration:
        normalized = _normalize_text(duration).lower()
        if any(token in normalized for token in ['week', 'month', 'persistent', 'chronic', 'ongoing']):
            return '🟡 Moderate'

    return '🟢 Low'


def _build_suggested_tests(recommended_departments, conditions, risk_level):
    tests = []
    department_text = ' '.join(recommended_departments or []).lower()
    if 'cardio' in department_text or 'heart' in department_text:
        tests.append('ECG')
    if 'ortho' in department_text or 'bone' in department_text or 'joint' in department_text:
        tests.append('X-ray')
    if 'dermat' in department_text or 'skin' in department_text:
        tests.append('Skin evaluation')
    if 'neuro' in department_text or 'brain' in department_text or 'nerv' in department_text:
        tests.append('MRI')
    if 'gastro' in department_text or 'digest' in department_text or 'abdomen' in department_text:
        tests.append('Abdominal ultrasound')
    if not tests:
        tests.append('CBC')
        if risk_level != '🟢 Low':
            tests.append('X-ray')
            tests.append('ECG')
    return tests[:4]


def _build_symptom_response(raw_result, age, gender, duration, severity, body_part, body_part_detail, worse_factors, better_factors, current_medicines, allergies, medical_history):
    conditions = raw_result.get('conditions') if isinstance(raw_result.get('conditions'), list) else []
    if raw_result.get('description'):
        clinical_summary = f"{_normalize_text(raw_result.get('description')).strip()}"
    else:
        severity_text = _normalize_text(severity).lower()
        details = [age and f"At {age} years old", gender and f"{gender}", duration and f"after {duration}", severity_text and f"with {severity_text} symptoms"]
        clinical_summary = ' '.join([d for d in details if d]) or 'This assessment reviews the reported symptoms and clinical context to identify likely explanations.'

    ai_recommendations = _parse_text_list(raw_result.get('advice'))
    if not ai_recommendations:
        ai_recommendations = ['Rest the affected area', 'Stay hydrated', 'Monitor the symptoms closely', 'Avoid activities that worsen discomfort']
    ai_recommendations = ai_recommendations[:5]

    self_care = _parse_text_list(raw_result.get('self_care'))
    if not self_care:
        self_care = ['Apply gentle cold or warm compresses as appropriate', 'Keep a regular sleep schedule', 'Practice light movement and avoid prolonged immobility']
    self_care = self_care[:5]

    supportive_relief_options = _parse_text_list(raw_result.get('suggested_medicines'))
    if not supportive_relief_options:
        supportive_relief_options = ['Acetaminophen', 'Ibuprofen', 'Topical pain-relief gels']
    if all('consult' not in option.lower() for option in supportive_relief_options):
        supportive_relief_options.append('Consult a healthcare professional before taking medication.')
    supportive_relief_options = supportive_relief_options[:5]

    warning_alerts = _parse_text_list(raw_result.get('when_to_see_doctor')) + _parse_text_list(raw_result.get('key_precautions'))
    warning_alerts = [alert for alert in warning_alerts if alert]
    if not warning_alerts:
        warning_alerts = ['Seek medical attention if symptoms worsen', 'Watch for fever or difficulty breathing', 'Consult a doctor if new numbness or weakness appears']
    warning_alerts = warning_alerts[:5]

    recommended_specialists = raw_result.get('recommended_departments') if isinstance(raw_result.get('recommended_departments'), list) else []
    if not recommended_specialists:
        recommended_specialists = ['General Practitioner']

    risk_level = _derive_risk_level(severity, duration, raw_result.get('when_to_see_doctor', ''), conditions)
    suggested_tests = _build_suggested_tests(recommended_specialists, conditions, risk_level)

    medical_disclaimer = 'This AI-generated assessment is intended for informational purposes only and should not be considered a medical diagnosis. Please consult a licensed healthcare professional for accurate evaluation and treatment.'

    pathophysiology = raw_result.get('pathophysiology') or 'Acute physiological response and cellular inflammatory mediation corresponding to the reported symptom onset.'
    differential_analysis = raw_result.get('differential_analysis') or []
    dietary_guidelines = raw_result.get('dietary_guidelines') or {
        'recommended': ['Hydrate adequately with electrolyte-balanced fluids', 'Warm broths, herbal teas, or soothing soups', 'Easily digestible, nutrient-dense whole foods'],
        'avoid': ['Excessive caffeine, refined sugars, and alcohol', 'Heavily spiced or ultra-processed irritants', 'Unpasteurized or heavy high-fat meals']
    }
    triage_timeline = raw_result.get('triage_timeline') or 'Monitor progression actively over 24-48 hours. Most non-complicated presentations show steady recovery within 5-7 days.'

    return {
        **raw_result,
        'clinical_summary': clinical_summary,
        'pathophysiology': pathophysiology,
        'differential_analysis': differential_analysis,
        'dietary_guidelines': dietary_guidelines,
        'triage_timeline': triage_timeline,
        'ai_recommendations': ai_recommendations,
        'self_care_suggestions': self_care,
        'supportive_relief_options': supportive_relief_options,
        'warning_alerts': warning_alerts,
        'recommended_specialists': recommended_specialists,
        'risk_level': risk_level,
        'suggested_tests': suggested_tests,
        'medical_disclaimer': medical_disclaimer
    }

