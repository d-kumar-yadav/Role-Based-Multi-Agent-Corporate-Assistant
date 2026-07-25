import re
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()

def detect_pii(text: str) -> bool:
    """
    Returns True if critical PII is detected in the input text.
    """
    # Expanded list of Enterprise PII entities to block
    entities_to_block = [
        "EMAIL_ADDRESS", 
        "PHONE_NUMBER", 
        "CREDIT_CARD",
        "US_SSN",            
        "US_BANK_NUMBER",    
        
        "IBAN_CODE",         
        "IP_ADDRESS"         
    ]
    
    # Using Presidio to detect entities
    results = analyzer.analyze(text=text, entities=entities_to_block, language='en')
    
    return len(results) > 0



# The PII (Personally Identifiable Information) checking in your code is powered by a library called Microsoft Presidio. It doesn't just blindly search for exact text matches; it uses a multi-layered approach to intelligently figure out if a string of text is sensitive data.

# Here is a simple breakdown of exactly how it checks your text:

# 1. Pattern Matching (Regex)
# For highly structured data (like Phone Numbers, IP Addresses, or Social Security Numbers), Presidio has hundreds of built-in Regular Expressions (Regex). It scans the text looking for specific shapes—like a 3-digit number, a dash, a 2-digit number, a dash, and a 4-digit number (SSN).

# 2. Checksums & Validation Logic
# Presidio is smart enough to know that not every 16-digit number is a Credit Card. When it finds a 16-digit number, it actually runs it through the Luhn Algorithm (the mathematical formula used by Visa/Mastercard to verify card numbers). If the math fails, Presidio ignores it. It does similar validation checks for IBAN bank numbers.

# 3. Machine Learning (NLP & NER)
# This is where it shines. Presidio uses a Natural Language Processing (NLP) model called spaCy (which is why you had to run python -m spacy download en_core_web_lg earlier). This ML model understands English grammar and context. It reads the sentence to recognize "Named Entities" (NER). It knows the difference between an email address structure and a website link.

# 4. Context Enhancers
# Presidio looks at the words surrounding a number. For example, a random 9-digit number might just be a serial number. But if the sentence says, "My social is 123456789," Presidio detects the context word "social", drastically increases its confidence score, and flags it as a US_SSN.





# If a user sends the prompt: "Please update the direct deposit for my account at 555-123-4567"

# The results list returned by Presidio will look something like this:

# python
# [
#     type: PHONE_NUMBER, start: 45, end: 57, score: 0.85
# ]

# Here is what each of those pieces of data means:

# type (PHONE_NUMBER): Which specific entity triggered the alert from our blocked list.
# start (45): The exact character index in the sentence where the sensitive data begins.
# end (57): The exact character index where the sensitive data ends.
# score (0.85): A confidence score from 0.0 to 1.0. In this case, Presidio is 85% confident that "555-123-4567" is a phone number based on its shape and the context of the sentence.
# Because Presidio gives us the exact start and end positions, many companies don't just "block" the prompt—they actually use a companion tool called presidio-anonymizer to replace those exact characters with a placeholder like <PHONE_NUMBER>, allowing the rest of the prompt to safely pass through to the LLM!