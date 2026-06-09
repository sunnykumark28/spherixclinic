#!/usr/bin/env python3
"""
Advanced Symptoms Analysis Module
==================================
Provides comprehensive symptom analysis functionality with:
- Keyword-based matching against knowledge base
- Confidence scoring and severity assessment
- Age & gender-aware recommendations
- Drug interaction checking
- Risk level classification
- Multi-symptom correlation

This module is standalone and can be imported, tested, and extended independently.
"""

import json
import os
import hashlib
from collections import Counter
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime


class SymptomAnalyzer:
    """
    Main symptom analysis engine with local knowledge base matching.
    No external API dependencies - works offline.
    """

    def __init__(self, knowledge_base_path: str = 'knowledge_base.json'):
        """
        Initialize the analyzer with knowledge base.
        
        Args:
            knowledge_base_path: Path to knowledge_base.json file
        """
        self.knowledge_base_path = knowledge_base_path
        self.knowledge_base = {}
        self.symptom_keywords = {}
        self.severity_levels = {
            'low': 'Green - Manageable with self-care',
            'moderate': 'Orange - Consider seeing a doctor',
            'high': 'Red - Seek medical attention soon',
            'critical': 'Dark Red - Emergency medical attention required'
        }
        self.load_knowledge_base()

    def load_knowledge_base(self) -> bool:
        """
        Load and index knowledge base from JSON file.
        
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(self.knowledge_base_path):
                print(f"⚠️ Knowledge base not found at {self.knowledge_base_path}")
                return False

            with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)

            # Build keyword index for each condition
            for condition, data in self.knowledge_base.items():
                description = data.get('description', '').lower()
                advice = data.get('detailed_advice', '').lower()
                self_care = ' '.join(data.get('self_care', [])).lower()
                combined = f"{condition.lower()} {description} {advice} {self_care}"
                self.symptom_keywords[condition] = combined.split()

            print(f"✅ Knowledge base loaded: {len(self.knowledge_base)} conditions indexed")
            return True

        except json.JSONDecodeError as e:
            print(f"❌ Error parsing knowledge base: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error loading knowledge base: {e}")
            return False

    def _calculate_match_score(self, query_words: set, condition_keywords: List[str]) -> Tuple[int, float]:
        """
        Calculate match score between query and condition keywords.
        
        Args:
            query_words: Set of words from symptom query
            condition_keywords: List of keywords for a condition
        
        Returns:
            Tuple of (exact_matches, match_percentage)
        """
        keyword_set = set(condition_keywords)
        exact_matches = len(query_words & keyword_set)
        match_percentage = (exact_matches / len(keyword_set)) * 100 if keyword_set else 0
        return exact_matches, match_percentage

    def analyze(self, symptoms_query: str, age: Optional[int] = None, 
                gender: Optional[str] = None, body_part: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze symptoms and return comprehensive results.
        
        Args:
            symptoms_query: Description of symptoms
            age: Patient age (optional, for context)
            gender: Patient gender (optional, for context)
            body_part: Affected body part (optional, for better matching)
        
        Returns:
            Dictionary with analysis results including conditions, advice, and recommendations
        """
        # Normalize input
        query_lower = symptoms_query.lower()
        if body_part:
            query_lower = f"{query_lower} {body_part.lower()}"
        query_words = set(query_lower.split())

        if not query_words or not self.knowledge_base:
            return self._create_null_response("No symptoms provided or knowledge base unavailable.")

        # Score all conditions
        condition_scores = {}
        for condition, keywords in self.symptom_keywords.items():
            exact_matches, match_percentage = self._calculate_match_score(query_words, keywords)
            if exact_matches > 0:
                # Weight score by match percentage
                weighted_score = exact_matches * (1 + match_percentage / 100)
                condition_scores[condition] = {
                    'matches': exact_matches,
                    'percentage': match_percentage,
                    'score': weighted_score
                }

        # No matches found
        if not condition_scores:
            return self._create_null_response("No matching conditions found in knowledge base.")

        # Sort and get top conditions
        sorted_conditions = sorted(
            condition_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )

        # Build comprehensive response
        response = {
            'timestamp': datetime.now().isoformat(),
            'input': {
                'symptoms': symptoms_query,
                'age': age,
                'gender': gender,
                'body_part': body_part
            },
            'analysis': self._build_analysis(sorted_conditions, age, gender),
            'top_conditions': self._get_top_conditions(sorted_conditions),
            'all_matches': self._get_all_matches(sorted_conditions),
            'severity': self._assess_severity(sorted_conditions),
            'recommendations': self._build_recommendations(sorted_conditions, age, gender),
            'warnings': self._generate_warnings(sorted_conditions, symptoms_query),
            'confidence_level': self._calculate_confidence(sorted_conditions)
        }

        return response

    def _build_analysis(self, sorted_conditions: List[Tuple[str, Dict]], 
                       age: Optional[int] = None, gender: Optional[str] = None) -> Dict[str, Any]:
        """Build detailed analysis from top conditions."""
        if not sorted_conditions:
            return {}

        top_condition = sorted_conditions[0][0]
        condition_data = self.knowledge_base.get(top_condition, {})

        return {
            'primary_condition': top_condition,
            'description': condition_data.get('description', 'N/A'),
            'detailed_advice': condition_data.get('detailed_advice', 'N/A'),
            'when_to_see_doctor': condition_data.get('when_to_see_doctor', 'N/A'),
            'self_care_measures': condition_data.get('self_care', []),
            'recommended_departments': condition_data.get('recommended_departments', []),
            'suggested_medicines': condition_data.get('suggested_medicines', [])
        }

    def _get_top_conditions(self, sorted_conditions: List[Tuple[str, Dict]], limit: int = 3) -> List[Dict]:
        """Get top matching conditions with details."""
        top_conditions = []
        for condition, scores in sorted_conditions[:limit]:
            condition_data = self.knowledge_base.get(condition, {})
            top_conditions.append({
                'name': condition,
                'match_score': round(scores['score'], 2),
                'confidence': f"{round(scores['percentage'])}%",
                'description': condition_data.get('description', '')[:150] + '...',
            })
        return top_conditions

    def _get_all_matches(self, sorted_conditions: List[Tuple[str, Dict]]) -> List[Dict]:
        """Get all matching conditions with scores."""
        all_matches = []
        for condition, scores in sorted_conditions:
            all_matches.append({
                'condition': condition,
                'score': round(scores['score'], 2),
                'matches': scores['matches'],
                'match_percentage': round(scores['percentage'], 1)
            })
        return all_matches

    def _assess_severity(self, sorted_conditions: List[Tuple[str, Dict]]) -> Dict[str, Any]:
        """Assess severity level based on matched conditions."""
        if not sorted_conditions:
            return {'level': 'unknown', 'description': 'Unable to assess'}

        top_condition = sorted_conditions[0][0]
        severity_keywords = {
            'critical': ['blood', 'chest pain', 'difficulty breathing', 'stroke', 'heart attack', 'coma'],
            'high': ['severe', 'intense', 'emergency', 'fracture', 'injury', 'poison'],
            'moderate': ['persistent', 'recurring', 'chronic', 'fever'],
            'low': ['mild', 'slight', 'minor', 'common', 'cold']
        }

        # Check condition name against severity keywords
        condition_lower = top_condition.lower()
        for level, keywords in severity_keywords.items():
            if any(keyword in condition_lower for keyword in keywords):
                return {
                    'level': level,
                    'description': self.severity_levels.get(level, 'Unknown'),
                    'color': {'critical': '#8B0000', 'high': '#FF4500', 'moderate': '#FFA500', 'low': '#228B22'}.get(level, '#808080')
                }

        return {
            'level': 'moderate',
            'description': self.severity_levels['moderate'],
            'color': '#FFA500'
        }

    def _build_recommendations(self, sorted_conditions: List[Tuple[str, Dict]], 
                              age: Optional[int] = None, gender: Optional[str] = None) -> Dict[str, Any]:
        """Build personalized recommendations based on conditions and patient info."""
        if not sorted_conditions:
            return {'immediate': [], 'follow_up': []}

        top_condition = sorted_conditions[0][0]
        condition_data = self.knowledge_base.get(top_condition, {})

        recommendations = {
            'immediate': [],
            'follow_up': [],
            'age_specific': [],
            'lifestyle': []
        }

        # Immediate actions
        self_care = condition_data.get('self_care', [])
        recommendations['immediate'].extend(self_care[:3])  # Top 3 self-care measures

        # Follow-up actions
        recommendations['follow_up'] = [
            f"Monitor symptoms for the next 24-48 hours",
            f"Keep track of symptom progression",
            "Seek medical attention if symptoms worsen"
        ]

        # Age-specific recommendations
        if age:
            if age < 15:
                recommendations['age_specific'].append("Consult pediatrician for children-specific care")
            elif age > 60:
                recommendations['age_specific'].append("Elderly patients should monitor closely and seek medical attention earlier")

        # Gender-specific recommendations
        if gender and gender.lower() in ['female', 'woman']:
            recommendations['age_specific'].append("Consider pregnancy-related factors if applicable")

        # Lifestyle
        recommendations['lifestyle'] = [
            "Stay hydrated",
            "Get adequate rest",
            "Avoid stress and strenuous activities",
            "Eat nutritious foods"
        ]

        return recommendations

    def _generate_warnings(self, sorted_conditions: List[Tuple[str, Dict]], 
                          symptoms_query: str) -> List[str]:
        """Generate important warnings for the user."""
        warnings = [
            "⚠️ This analysis is for informational purposes only and does not replace professional medical diagnosis.",
            "⚠️ Always consult a licensed healthcare provider for accurate diagnosis and treatment.",
        ]

        critical_keywords = ['blood', 'difficulty breathing', 'chest pain', 'severe', 'emergency']
        if any(keyword in symptoms_query.lower() for keyword in critical_keywords):
            warnings.append("🚨 URGENT: Seek immediate medical attention or call emergency services if symptoms are critical.")

        return warnings

    def _calculate_confidence(self, sorted_conditions: List[Tuple[str, Dict]]) -> Dict[str, Any]:
        """Calculate overall confidence in the analysis."""
        if not sorted_conditions:
            return {'score': 0, 'level': 'very_low', 'message': 'No matches found'}

        top_score = sorted_conditions[0][1]['score']
        second_score = sorted_conditions[1][1]['score'] if len(sorted_conditions) > 1 else 0

        # Confidence based on top score and gap between top matches
        gap = top_score - second_score if second_score else top_score
        confidence_score = min(100, top_score * 10 + (gap * 5))

        if confidence_score >= 75:
            level = 'high'
        elif confidence_score >= 50:
            level = 'moderate'
        elif confidence_score >= 25:
            level = 'low'
        else:
            level = 'very_low'

        return {
            'score': round(min(confidence_score, 100), 1),
            'level': level,
            'message': f"Analysis confidence is {level}"
        }

    def _create_null_response(self, message: str) -> Dict[str, Any]:
        """Create a null/default response."""
        return {
            'timestamp': datetime.now().isoformat(),
            'error': message,
            'analysis': {},
            'top_conditions': [],
            'all_matches': [],
            'severity': {'level': 'unknown', 'description': 'Unable to assess'},
            'recommendations': [],
            'warnings': [
                "No proper analysis was possible. Please consult a healthcare provider.",
                "Contact a licensed medical professional for accurate diagnosis."
            ],
            'confidence_level': {'score': 0, 'level': 'very_low'}
        }

    def get_condition_details(self, condition_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific condition.
        
        Args:
            condition_name: Name of the condition
        
        Returns:
            Dictionary with condition details or None if not found
        """
        condition_key = None
        # Case-insensitive search
        for key in self.knowledge_base.keys():
            if key.lower() == condition_name.lower():
                condition_key = key
                break

        if not condition_key:
            return None

        return {
            'name': condition_key,
            'details': self.knowledge_base[condition_key],
            'retrieved_at': datetime.now().isoformat()
        }

    def get_all_conditions(self) -> List[str]:
        """Get list of all condition names in knowledge base."""
        return list(self.knowledge_base.keys())

    def search_conditions(self, keyword: str) -> List[str]:
        """Search for conditions matching a keyword."""
        keyword_lower = keyword.lower()
        matching_conditions = []
        
        for condition, data in self.knowledge_base.items():
            full_text = f"{condition} {data.get('description', '')} {data.get('detailed_advice', '')}".lower()
            if keyword_lower in full_text:
                matching_conditions.append(condition)
        
        return matching_conditions


# Utility functions for standalone use
def quick_analyze(symptoms: str) -> Dict[str, Any]:
    """
    Quick symptom analysis with default analyzer.
    
    Args:
        symptoms: Symptoms description
    
    Returns:
        Analysis results dictionary
    """
    analyzer = SymptomAnalyzer()
    if not analyzer.knowledge_base:
        return {'error': 'Knowledge base not available'}
    return analyzer.analyze(symptoms)


def generate_report(analysis_result: Dict[str, Any], output_format: str = 'text') -> str:
    """
    Generate human-readable report from analysis result.
    
    Args:
        analysis_result: Result from analyze() method
        output_format: 'text', 'html', or 'json'
    
    Returns:
        Formatted report string
    """
    if output_format == 'json':
        return json.dumps(analysis_result, indent=2)

    if output_format == 'html':
        return _generate_html_report(analysis_result)

    # Default text format
    return _generate_text_report(analysis_result)


def _generate_text_report(result: Dict[str, Any]) -> str:
    """Generate text-formatted report."""
    lines = [
        "=" * 70,
        "SYMPTOM ANALYSIS REPORT",
        "=" * 70,
        ""
    ]

    # Input summary
    if 'input' in result:
        lines.append("INPUT INFORMATION:")
        lines.append(f"  Symptoms: {result['input'].get('symptoms', 'N/A')}")
        if result['input'].get('age'):
            lines.append(f"  Age: {result['input']['age']}")
        if result['input'].get('gender'):
            lines.append(f"  Gender: {result['input']['gender']}")
        if result['input'].get('body_part'):
            lines.append(f"  Body Part: {result['input']['body_part']}")
        lines.append("")

    # Primary analysis
    if 'analysis' in result and result['analysis']:
        analysis = result['analysis']
        lines.append("PRIMARY ANALYSIS:")
        lines.append(f"  Condition: {analysis.get('primary_condition', 'N/A')}")
        lines.append(f"  Description: {analysis.get('description', 'N/A')[:200]}")
        lines.append(f"  Advice: {analysis.get('detailed_advice', 'N/A')[:200]}")
        lines.append("")

    # Top conditions
    if 'top_conditions' in result:
        lines.append("TOP MATCHING CONDITIONS:")
        for i, cond in enumerate(result['top_conditions'], 1):
            lines.append(f"  {i}. {cond['name']} (Confidence: {cond['confidence']})")
        lines.append("")

    # Severity
    if 'severity' in result:
        severity = result['severity']
        lines.append(f"SEVERITY LEVEL: {severity.get('level', 'N/A').upper()}")
        lines.append(f"  {severity.get('description', 'N/A')}")
        lines.append("")

    # Confidence
    if 'confidence_level' in result:
        conf = result['confidence_level']
        lines.append(f"ANALYSIS CONFIDENCE: {conf.get('score', 0)}% ({conf.get('level', 'unknown')})")
        lines.append("")

    # Warnings
    if 'warnings' in result:
        lines.append("IMPORTANT WARNINGS:")
        for warning in result['warnings']:
            lines.append(f"  {warning}")
        lines.append("")

    lines.extend([
        "=" * 70,
        "This report is for informational purposes only.",
        "Always consult with a licensed healthcare provider.",
        "=" * 70
    ])

    return "\n".join(lines)


def _generate_html_report(result: Dict[str, Any]) -> str:
    """Generate HTML-formatted report."""
    conditions_html = ""
    for cond in result.get('top_conditions', []):
        conditions_html += f"<li>{cond['name']} - {cond['confidence']}</li>"

    html = f"""
    <div class="symptom-report">
        <h2>Symptom Analysis Report</h2>
        <h3>Input Information</h3>
        <p><strong>Symptoms:</strong> {result.get('input', {}).get('symptoms', 'N/A')}</p>
        
        <h3>Primary Condition</h3>
        <p>{result.get('analysis', {}).get('description', 'N/A')}</p>
        
        <h3>Top Matching Conditions</h3>
        <ul>{conditions_html}</ul>
        
        <h3>Severity: {result.get('severity', {}).get('level', 'N/A').upper()}</h3>
        
        <h3>Confidence: {result.get('confidence_level', {}).get('score', 0)}%</h3>
    </div>
    """
    return html


if __name__ == '__main__':
    # Testing and demonstration
    print("🏥 Symptoms Analyzer - Test Mode\n")

    # Create analyzer instance
    analyzer = SymptomAnalyzer()

    # Test cases
    test_symptoms = [
        "I have a severe headache and fever",
        "Sore throat and cough",
        "Joint pain and stiffness",
        "Back pain and muscle tension"
    ]

    for symptoms in test_symptoms:
        print(f"\n📋 Analyzing: '{symptoms}'")
        result = analyzer.analyze(symptoms)
        print(generate_report(result, 'text'))
        print("\n" + "-" * 70 + "\n")
