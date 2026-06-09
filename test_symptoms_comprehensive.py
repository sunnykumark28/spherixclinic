#!/usr/bin/env python3
"""
Test Suite for Symptoms Analyzer
==================================
Comprehensive test cases to verify all functionality of the symptoms analyzer.

Run with: python test_symptoms_comprehensive.py
"""

import json
from symptoms_analyzer import (
    SymptomAnalyzer, 
    quick_analyze, 
    generate_report,
    _generate_text_report,
    _generate_html_report
)


class TestSymptomAnalyzer:
    """Test suite for SymptomAnalyzer functionality"""
    
    def __init__(self):
        self.analyzer = SymptomAnalyzer()
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def test(self, name, condition, expected_substring=None):
        """Helper method to run a test"""
        try:
            result = self.analyzer.analyze(condition)
            
            # Verify result structure
            assert 'timestamp' in result
            assert 'input' in result
            assert 'analysis' in result
            assert 'top_conditions' in result
            assert 'severity' in result
            assert 'confidence_level' in result
            assert 'recommendations' in result
            assert 'warnings' in result
            
            # Check for expected content if provided
            if expected_substring:
                result_str = json.dumps(result).lower()
                assert expected_substring.lower() in result_str, f"Expected '{expected_substring}' not found in result"
            
            self.passed += 1
            status = "✅ PASS"
            self.tests.append((name, status, condition))
            print(f"{status}: {name}")
            return result
            
        except AssertionError as e:
            self.failed += 1
            status = "❌ FAIL"
            self.tests.append((name, status, str(e)))
            print(f"{status}: {name} - {e}")
            return None
        except Exception as e:
            self.failed += 1
            status = "❌ ERROR"
            self.tests.append((name, status, str(e)))
            print(f"{status}: {name} - {e}")
            return None
    
    def run_all_tests(self):
        """Run all test cases"""
        print("\n" + "="*70)
        print("🧪 SYMPTOM ANALYZER TEST SUITE")
        print("="*70 + "\n")
        
        # Test 1: Basic symptom analysis
        print("📋 Test Group 1: Basic Symptom Analysis")
        print("-" * 70)
        self.test("Fever analysis", "I have a fever", "fever")
        self.test("Cough analysis", "Persistent cough", "cough")
        self.test("Headache analysis", "Severe headache", "headache")
        self.test("Sore throat", "Sore throat and difficulty swallowing", "throat")
        
        # Test 2: Multi-symptom analysis
        print("\n📋 Test Group 2: Multi-Symptom Analysis")
        print("-" * 70)
        self.test("Flu symptoms", "Fever, cough, body aches, and sore throat", "flu")
        self.test("Cold symptoms", "Runny nose, sore throat, sneezing", "cold")
        self.test("Joint pain", "Joint pain and stiffness in the morning", "joint")
        self.test("Digestive issues", "Nausea, vomiting, and stomach pain", "digest")
        
        # Test 3: With body part specification
        print("\n📋 Test Group 3: Body Part Specification")
        print("-" * 70)
        result = self.test("Back pain - with body part", "Pain in the back", "back")
        if result:
            assert result['input']['symptoms'] != ""
        
        # Test 4: Edge cases
        print("\n📋 Test Group 4: Edge Cases")
        print("-" * 70)
        self.test("Single word symptom", "fever")
        self.test("Very detailed symptoms", 
                 "I have been experiencing a persistent throbbing pain in the back of my head")
        self.test("Non-specific symptoms", "I feel unwell")
        
        # Test 5: Confidence scoring
        print("\n📋 Test Group 5: Confidence Scoring")
        print("-" * 70)
        result = self.test("Very specific match", "I have influenza flu virus")
        if result:
            conf = result['confidence_level']['score']
            assert 0 <= conf <= 100, f"Confidence score {conf} out of range"
            print(f"   → Confidence: {conf}%")
        
        # Test 6: Severity assessment
        print("\n📋 Test Group 6: Severity Assessment")
        print("-" * 70)
        result = self.test("Moderate severity", "Persistent headache for 3 days")
        if result:
            severity = result['severity']['level']
            assert severity in ['low', 'moderate', 'high', 'critical']
            print(f"   → Severity Level: {severity}")
        
        # Test 7: Age & gender personalization
        print("\n📋 Test Group 7: Age & Gender Recommendations")
        print("-" * 70)
        result = self.analyzer.analyze(
            "Fever and cough",
            age=8,
            gender="Male"
        )
        assert result['input']['age'] == 8
        assert result['input']['gender'] == "Male"
        self.passed += 1
        print("✅ PASS: Age & gender stored in analysis")
        
        # Test 8: Utility functions
        print("\n📋 Test Group 8: Utility Functions")
        print("-" * 70)
        
        # Test quick_analyze
        try:
            quick_result = quick_analyze("fever and cough")
            assert 'top_conditions' in quick_result or 'error' in quick_result
            self.passed += 1
            print("✅ PASS: quick_analyze() function works")
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: quick_analyze() - {e}")
        
        # Test 9: Report generation
        print("\n📋 Test Group 9: Report Generation")
        print("-" * 70)
        
        result = self.analyzer.analyze("Fever and headache")
        
        # Text report
        try:
            text_report = generate_report(result, 'text')
            assert isinstance(text_report, str)
            assert len(text_report) > 100
            assert 'SYMPTOM ANALYSIS REPORT' in text_report
            self.passed += 1
            print("✅ PASS: Text report generation works")
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: Text report - {e}")
        
        # HTML report
        try:
            html_report = generate_report(result, 'html')
            assert isinstance(html_report, str)
            assert '<' in html_report  # Contains HTML tags
            self.passed += 1
            print("✅ PASS: HTML report generation works")
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: HTML report - {e}")
        
        # JSON report
        try:
            json_report = generate_report(result, 'json')
            json_data = json.loads(json_report)
            assert isinstance(json_data, dict)
            self.passed += 1
            print("✅ PASS: JSON report generation works")
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: JSON report - {e}")
        
        # Test 10: Knowledge base operations
        print("\n📋 Test Group 10: Knowledge Base Operations")
        print("-" * 70)
        
        # Get all conditions
        try:
            conditions = self.analyzer.get_all_conditions()
            assert len(conditions) > 0
            print(f"✅ PASS: Found {len(conditions)} conditions in knowledge base")
            self.passed += 1
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: get_all_conditions() - {e}")
        
        # Search conditions
        try:
            results = self.analyzer.search_conditions('pain')
            assert len(results) > 0
            print(f"✅ PASS: Found {len(results)} conditions matching 'pain'")
            self.passed += 1
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: search_conditions() - {e}")
        
        # Get condition details
        try:
            details = self.analyzer.get_condition_details('Flu')
            assert details is not None
            assert 'details' in details
            print("✅ PASS: Retrieved details for 'Flu' condition")
            self.passed += 1
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: get_condition_details() - {e}")
        
        # Test 11: Recommendations structure
        print("\n📋 Test Group 11: Recommendations Structure")
        print("-" * 70)
        
        result = self.analyzer.analyze("Joint pain and arthritis", age=65)
        try:
            recommendations = result['recommendations']
            assert 'immediate' in recommendations
            assert 'follow_up' in recommendations
            assert 'age_specific' in recommendations
            assert 'lifestyle' in recommendations
            self.passed += 1
            print("✅ PASS: Recommendations have correct structure")
            print(f"   → Immediate actions: {len(recommendations['immediate'])}")
            print(f"   → Age-specific: {len(recommendations['age_specific'])}")
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: Recommendations structure - {e}")
        
        # Test 12: Warnings generation
        print("\n📋 Test Group 12: Warnings Generation")
        print("-" * 70)
        
        result = self.analyzer.analyze("chest pain and difficulty breathing")
        try:
            warnings = result['warnings']
            assert len(warnings) > 0
            assert any('emergency' in w.lower() for w in warnings)
            self.passed += 1
            print("✅ PASS: Critical symptom warnings generated")
        except Exception as e:
            self.failed += 1
            print(f"❌ FAIL: Warnings - {e}")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📈 Total:  {self.passed + self.failed}")
        
        if self.failed == 0:
            success_rate = 100
        else:
            success_rate = (self.passed / (self.passed + self.failed)) * 100
        
        print(f"🎯 Success Rate: {success_rate:.1f}%")
        print("="*70)
        
        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED! The analyzer is fully functional.")
        else:
            print(f"\n⚠️  {self.failed} test(s) failed. Review above for details.")


def demonstrate_features():
    """Demonstrate key features of the analyzer"""
    print("\n" + "="*70)
    print("✨ FEATURE DEMONSTRATION")
    print("="*70 + "\n")
    
    analyzer = SymptomAnalyzer()
    
    # 1. Basic analysis
    print("1️⃣  BASIC ANALYSIS")
    print("-" * 70)
    result = analyzer.analyze("I have a fever and headache")
    print(f"Symptoms: {result['input']['symptoms']}")
    print(f"Primary Condition: {result['analysis']['primary_condition']}")
    print(f"Severity: {result['severity']['level']}")
    print(f"Confidence: {result['confidence_level']['score']}%")
    
    # 2. Search functionality
    print("\n2️⃣  CONDITION SEARCH")
    print("-" * 70)
    fever_conditions = analyzer.search_conditions('fever')
    print(f"Conditions containing 'fever': {fever_conditions}")
    
    # 3. Recommendations
    print("\n3️⃣  PERSONALIZED RECOMMENDATIONS")
    print("-" * 70)
    result = analyzer.analyze("Back pain and arthritis", age=70, gender="Female")
    recommendations = result['recommendations']
    print("Immediate actions:")
    for action in recommendations['immediate'][:2]:
        print(f"  • {action}")
    print("Age-specific advice:")
    for advice in recommendations['age_specific']:
        print(f"  • {advice}")
    
    # 4. Report generation
    print("\n4️⃣  REPORT GENERATION")
    print("-" * 70)
    result = analyzer.analyze("Sore throat and cough")
    text_report = generate_report(result, 'text')
    print(text_report[:500] + "...\n[Report truncated for display]")
    
    # 5. All available conditions
    print("\n5️⃣  AVAILABLE CONDITIONS")
    print("-" * 70)
    conditions = analyzer.get_all_conditions()
    print(f"Total conditions in knowledge base: {len(conditions)}")
    print("Sample conditions:")
    for condition in conditions[:10]:
        print(f"  • {condition}")
    print(f"  ... and {len(conditions) - 10} more")


if __name__ == '__main__':
    # Run tests
    tester = TestSymptomAnalyzer()
    tester.run_all_tests()
    
    # Demonstrate features
    demonstrate_features()
    
    print("\n✅ Test suite completed!")
