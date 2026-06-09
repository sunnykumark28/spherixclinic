#!/usr/bin/env python3
"""
Quick test script to verify symptom analysis works correctly.
Tests the local knowledge base matcher with various symptoms.
"""

import json
import sys
from collections import Counter

# Load knowledge base
with open('knowledge_base.json', 'r') as f:
    KNOWLEDGE_BASE = json.load(f)

SYMPTOM_KEYWORDS = {}

# Build keyword index
for condition, data in KNOWLEDGE_BASE.items():
    description = data.get('description', '').lower()
    advice = data.get('detailed_advice', '').lower()
    combined = f"{condition.lower()} {description} {advice}"
    SYMPTOM_KEYWORDS[condition] = combined.split()

def test_symptom(symptoms_query):
    """Test symptom analysis"""
    query_lower = symptoms_query.lower()
    query_words = set(query_lower.split())
    
    print(f"\n{'='*70}")
    print(f"🔍 Testing: '{symptoms_query}'")
    print(f"{'='*70}")
    
    # Score each condition
    condition_scores = {}
    for condition, keywords in SYMPTOM_KEYWORDS.items():
        keyword_set = set(keywords)
        matches = len(query_words & keyword_set)
        if matches > 0:
            condition_scores[condition] = matches
    
    if not condition_scores:
        print("❌ No matches found")
        return False
    
    # Sort by score
    sorted_conditions = sorted(condition_scores.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n📊 Top Matches:")
    for i, (condition, score) in enumerate(sorted_conditions[:3], 1):
        data = KNOWLEDGE_BASE.get(condition, {})
        print(f"\n{i}. {condition} (Score: {score})")
        print(f"   Description: {data.get('description', 'N/A')[:80]}...")
        print(f"   Medicines: {', '.join(data.get('suggested_medicines', [])[:2])}")
        print(f"   Departments: {', '.join(data.get('recommended_departments', []))}")
        print(f"   Self-Care: {data.get('self_care', [])[0]}")
    
    return True

# Test cases
test_cases = [
    "leg pain",
    "joint pain",
    "back pain",
    "muscle pain",
    "cough fever",
    "headache",
    "stomach pain",
    "nausea vomiting",
]

print("\n" + "="*70)
print("🏥 LOCAL KNOWLEDGE BASE SYMPTOM ANALYZER - TEST SUITE")
print("="*70)

passed = 0
for symptom in test_cases:
    if test_symptom(symptom):
        passed += 1

print(f"\n{'='*70}")
print(f"✅ Tests Passed: {passed}/{len(test_cases)}")
print(f"{'='*70}\n")
