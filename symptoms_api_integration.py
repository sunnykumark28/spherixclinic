#!/usr/bin/env python3
"""
Symptom Analysis API Endpoints
===============================
Add these routes to your Flask app (app.py) to expose the advanced symptom analyzer.

How to integrate:
1. Copy/merge these routes into your app.py
2. Import: from symptoms_analyzer import SymptomAnalyzer, generate_report
3. Create analyzer instance: analyzer = SymptomAnalyzer()
4. Use the endpoints below

Routes added:
- /api/symptoms/analyze (POST) - Analyze symptoms and get detailed results
- /api/symptoms/quick (POST) - Quick analysis without detailed processing
- /api/symptoms/search (GET) - Search conditions by keyword
- /api/symptoms/all-conditions (GET) - Get all available conditions
- /api/symptoms/condition/<name> (GET) - Get details about specific condition
- /api/symptoms/report (POST) - Generate formatted report from analysis
"""

from flask import Flask, request, jsonify, session
from symptoms_analyzer import SymptomAnalyzer, generate_report
import json
from datetime import datetime

# Initialize analyzer (do this once at app startup)
# Place this in your app.py with other initializations:
# analyzer = SymptomAnalyzer()


# ======================== API ROUTES ========================

def init_symptom_routes(app: Flask, analyzer: SymptomAnalyzer):
    """
    Register symptom analysis routes with Flask app.
    
    Usage in app.py:
        analyzer = SymptomAnalyzer()
        init_symptom_routes(app, analyzer)
    """

    @app.route('/api/symptoms/analyze', methods=['POST'])
    def api_symptom_analyze():
        """
        Comprehensive symptom analysis with all details.
        
        Request JSON:
        {
            "symptoms": "description of symptoms",
            "age": 30,
            "gender": "M",
            "body_part": "back"
        }
        
        Response: Full analysis with top conditions, severity, recommendations, etc.
        """
        try:
            data = request.get_json() or {}
            symptoms = data.get('symptoms', '').strip()
            age = data.get('age')
            gender = data.get('gender')
            body_part = data.get('body_part')

            if not symptoms:
                return jsonify({'error': 'Symptoms field is required'}), 400

            # Perform analysis
            result = analyzer.analyze(symptoms, age=age, gender=gender, body_part=body_part)

            return jsonify({
                'success': True,
                'data': result,
                'timestamp': datetime.now().isoformat()
            }), 200

        except Exception as e:
            return jsonify({
                'error': f'Analysis failed: {str(e)}',
                'success': False
            }), 500

    @app.route('/api/symptoms/quick', methods=['POST'])
    def api_symptom_quick():
        """
        Quick symptom analysis (lightweight, minimal processing).
        
        Request JSON:
        {
            "symptoms": "description of symptoms"
        }
        
        Response: Quick top matching conditions only
        """
        try:
            data = request.get_json() or {}
            symptoms = data.get('symptoms', '').strip()

            if not symptoms:
                return jsonify({'error': 'Symptoms field is required'}), 400

            # Quick analysis - only top conditions
            analysis = analyzer.analyze(symptoms)
            quick_result = {
                'symptoms': symptoms,
                'top_condition': analysis['top_conditions'][0] if analysis['top_conditions'] else None,
                'all_matches': analysis['top_conditions'],
                'severity': analysis['severity']['level'],
                'confidence': analysis['confidence_level']['score']
            }

            return jsonify({
                'success': True,
                'data': quick_result,
                'timestamp': datetime.now().isoformat()
            }), 200

        except Exception as e:
            return jsonify({
                'error': f'Quick analysis failed: {str(e)}',
                'success': False
            }), 500

    @app.route('/api/symptoms/all-conditions', methods=['GET'])
    def api_all_conditions():
        """
        Get list of all available conditions in knowledge base.
        
        Response: List of condition names
        """
        try:
            conditions = analyzer.get_all_conditions()
            return jsonify({
                'success': True,
                'conditions': conditions,
                'total': len(conditions),
                'timestamp': datetime.now().isoformat()
            }), 200
        except Exception as e:
            return jsonify({
                'error': f'Failed to retrieve conditions: {str(e)}',
                'success': False
            }), 500

    @app.route('/api/symptoms/search', methods=['GET'])
    def api_search_conditions():
        """
        Search for conditions matching a keyword.
        
        Query Parameters:
        - keyword: Search term (e.g., 'fever', 'cough', 'pain')
        
        Response: List of matching conditions
        """
        try:
            keyword = request.args.get('keyword', '').strip()
            
            if not keyword:
                return jsonify({'error': 'Keyword parameter is required'}), 400

            if len(keyword) < 2:
                return jsonify({'error': 'Keyword must be at least 2 characters'}), 400

            results = analyzer.search_conditions(keyword)
            
            return jsonify({
                'success': True,
                'keyword': keyword,
                'results': results,
                'count': len(results),
                'timestamp': datetime.now().isoformat()
            }), 200

        except Exception as e:
            return jsonify({
                'error': f'Search failed: {str(e)}',
                'success': False
            }), 500

    @app.route('/api/symptoms/condition/<condition_name>', methods=['GET'])
    def api_condition_details(condition_name):
        """
        Get detailed information about a specific condition.
        
        URL Parameters:
        - condition_name: Name of the condition (e.g., 'Flu', 'Common Cold')
        
        Response: Full condition details with description, advice, medicines, etc.
        """
        try:
            details = analyzer.get_condition_details(condition_name)
            
            if not details:
                return jsonify({
                    'error': f'Condition "{condition_name}" not found',
                    'success': False
                }), 404

            return jsonify({
                'success': True,
                'data': details,
                'timestamp': datetime.now().isoformat()
            }), 200

        except Exception as e:
            return jsonify({
                'error': f'Failed to retrieve condition details: {str(e)}',
                'success': False
            }), 500

    @app.route('/api/symptoms/report', methods=['POST'])
    def api_generate_report():
        """
        Generate formatted report from analysis results.
        
        Request JSON:
        {
            "analysis": {...},  // Full analysis result from /api/symptoms/analyze
            "format": "text"    // or "html" or "json"
        }
        
        Response: Formatted report
        """
        try:
            data = request.get_json() or {}
            analysis = data.get('analysis')
            format_type = data.get('format', 'text').lower()

            if not analysis:
                return jsonify({'error': 'Analysis data is required'}), 400

            if format_type not in ['text', 'html', 'json']:
                return jsonify({'error': 'Format must be text, html, or json'}), 400

            report = generate_report(analysis, format_type)

            return jsonify({
                'success': True,
                'report': report,
                'format': format_type,
                'timestamp': datetime.now().isoformat()
            }), 200

        except Exception as e:
            return jsonify({
                'error': f'Report generation failed: {str(e)}',
                'success': False
            }), 500


# ======================== USAGE EXAMPLES ========================

"""
EXAMPLE CURL REQUESTS:

1. Analyze symptoms:
curl -X POST http://localhost:5000/api/symptoms/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "symptoms": "I have a severe headache and fever",
    "age": 30,
    "gender": "M",
    "body_part": "head"
  }'

2. Quick analysis:
curl -X POST http://localhost:5000/api/symptoms/quick \
  -H "Content-Type: application/json" \
  -d '{"symptoms": "sore throat and cough"}'

3. Get all conditions:
curl http://localhost:5000/api/symptoms/all-conditions

4. Search conditions:
curl "http://localhost:5000/api/symptoms/search?keyword=fever"

5. Get specific condition details:
curl http://localhost:5000/api/symptoms/condition/Flu

6. Generate report:
curl -X POST http://localhost:5000/api/symptoms/report \
  -H "Content-Type: application/json" \
  -d '{
    "analysis": {...analysis result...},
    "format": "text"
  }'


JAVASCRIPT/FETCH EXAMPLES:

1. Analyze symptoms:
fetch('/api/symptoms/analyze', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        symptoms: 'I have a severe headache and fever',
        age: 30,
        gender: 'M',
        body_part: 'head'
    })
})
.then(r => r.json())
.then(data => console.log(data.data));

2. Search conditions:
fetch('/api/symptoms/search?keyword=fever')
    .then(r => r.json())
    .then(data => console.log(data.results));

3. Get condition details:
fetch('/api/symptoms/condition/Flu')
    .then(r => r.json())
    .then(data => console.log(data.data.details));
"""


# ======================== INTEGRATION GUIDE ========================

"""
TO INTEGRATE INTO YOUR app.py:

1. At the top of app.py, add these imports:
   from symptoms_analyzer import SymptomAnalyzer, generate_report

2. After creating your Flask app, initialize the analyzer:
   app = Flask(__name__)
   analyzer = SymptomAnalyzer()

3. Register the routes (before app.run()):
   init_symptom_routes(app, analyzer)

4. Or manually add the @app.route functions from this file to your app.py

5. Update your existing symptoms routes to use the analyzer:
   - Copy the analyze() calls from the example routes above
   - Use the results in your templates

Example integration in app.py:
---
from flask import Flask
from symptoms_analyzer import SymptomAnalyzer, generate_report

app = Flask(__name__)
analyzer = SymptomAnalyzer()

# ... other setup code ...

# Add routes
init_symptom_routes(app, analyzer)

# Or add individual routes as needed:
@app.route('/api/symptoms/analyze', methods=['POST'])
def api_symptom_analyze():
    data = request.get_json() or {}
    symptoms = data.get('symptoms', '')
    result = analyzer.analyze(symptoms, 
                             age=data.get('age'),
                             gender=data.get('gender'),
                             body_part=data.get('body_part'))
    return jsonify({'success': True, 'data': result})

if __name__ == '__main__':
    app.run(debug=True)
---
"""
