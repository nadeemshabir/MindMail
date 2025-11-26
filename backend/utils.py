import json
import re

def safe_json_parse(text):
    """
    Safely parses JSON returned by Gemini.
    Handles:
    - Code fences (```json ... ```)
    - Extra whitespace
    - Prefix/suffix text
    - Partial JSON
    """
    if not text:
        return {"error": "Empty Gemini response"}

    # 1. Remove markdown code fences
    text = re.sub(r"```json|```", "", text).strip()

    # 2. Extract only the JSON inside the first { ... } block
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end != -1:
            cleaned = text[start:end]
        else:
            # If no braces found, try parsing the whole text just in case
            cleaned = text
    except:
        return {"error": "Could not find JSON brackets in response", "raw": text}

    # 3. Try loading JSON
    try:
        return json.loads(cleaned)
    except Exception as e:
        print(f"❌ JSON Parse Failed. Raw text: {text}")
        return {
            "error": f"JSON parsing failed: {e}",
            "raw": cleaned
        }