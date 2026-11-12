import os
import re
import pytest

def test_no_dummy_example_names_or_eg_in_form_placeholders():
    """
    Validates that across all HTML templates, form input and textarea placeholders
    do not contain dummy names (like Dr. John Doe, Jane Doe, Rahul Sharma),
    dummy example emails (like patient@example.com), or 'e.g.' text.
    """
    template_dir = 'templates'
    regex = re.compile(r'placeholder=[\"\']([^\"\']*)[\"\']', re.IGNORECASE)
    
    # Check for dummy person names or eg/example tags
    forbidden_pattern = re.compile(
        r'(\be\.?g\.?\b|\bex\b|\bex\.|\bexample\b|\bdomain\.com\b|\bjohn\b|\bdoe\b|\bjane\b|\bsmith\b|\brahul\b|\bsharma\b|\bpriya\b|\bananya\b|\bvikram\b|\bsinghania\b|\bramesh\b|\brajesh\b|\bvance\b)',
        re.IGNORECASE
    )
    
    violations = []
    
    for root, dirs, files in os.walk(template_dir):
        for f in files:
            if f.endswith('.html'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                    for idx, line in enumerate(fp, 1):
                        for match in regex.finditer(line):
                            val = match.group(1)
                            if forbidden_pattern.search(val):
                                violations.append(f"{path}:{idx} -> {val}")
                                
    assert len(violations) == 0, f"Found {len(violations)} placeholders with example or dummy text:\n" + "\n".join(violations)

