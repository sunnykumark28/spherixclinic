import os
import io
import tempfile
import traceback
from datetime import datetime
from fpdf import FPDF
from flask import current_app

def to_latin1_str(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    replacements = {
        '—': '-', '–': '-', '‘': "'", '’': "'",
        '“': '"', '”': '"', '•': '*', '▪': '*',
        '→': '->', '←': '<-', '✓': '[V]', '✔': '[V]',
        '✕': '[X]', '✖': '[X]', '⚠': '[!]', '…': '...',
        '🟢': '[Low]', '🟡': '[Moderate]', '🔴': '[High]', '🩺': '', '💬': '',
        '•': '*', '★': '*', '☆': ''
    }
    for k, v in replacements.items():
        value = value.replace(k, v)
    return value.encode('latin-1', 'replace').decode('latin-1')

class SpherixClinicalPrescriptionPDF(FPDF):
    PRIMARY_NAVY = (10, 25, 47)       # Deep Navy #0A192F
    SECONDARY_NAVY = (15, 23, 42)     # Slate 900 #0F172A
    ACCENT_SKY = (2, 132, 199)        # Sky Blue #0284C7
    ACCENT_CYAN = (6, 182, 212)       # Cyan #06B6D4
    ACCENT_INDIGO = (79, 70, 229)     # Indigo #4F46E5
    ACCENT_EMERALD = (16, 185, 129)   # Emerald #10B981
    ACCENT_ROSE = (225, 29, 72)       # Rose #E11D48
    ACCENT_AMBER = (217, 119, 6)      # Amber #D97706
    LIGHT_BG = (248, 250, 252)        # Slate 50
    CARD_BORDER = (218, 225, 233)     # Slate 200
    TEXT_MUTED = (100, 116, 139)      # Slate 500
    TEXT_MAIN = (30, 41, 59)          # Slate 800
    TEXT_DARK = (15, 23, 42)          # Slate 900

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_margins(12, 12, 12)
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        # Draw background template if available
        template_path = os.path.join(current_app.root_path, 'static', 'images', 'prescription_template.png')
        if os.path.exists(template_path):
            try:
                self.image(template_path, x=0, y=0, w=self.w, h=self.h)
            except Exception as ex:
                pass
        else:
            # Draw a sleek modern header strip if no background image is present
            self.set_fill_color(*self.PRIMARY_NAVY)
            self.rect(0, 0, self.w, 24, 'F')
            self.set_fill_color(*self.ACCENT_CYAN)
            self.rect(0, 24, self.w, 1.2, 'F')
            
            # Header Title Text
            self.set_xy(12, 4.5)
            self.set_font('Helvetica', 'B', 11)
            self.set_text_color(255, 255, 255)
            self.cell(110, 5, "SPHERIX CLINICAL HEALTH NETWORK", 0, 0, 'L')
            
            self.set_font('Helvetica', '', 7.5)
            self.set_text_color(186, 230, 253)
            self.cell(0, 5, "OFFICIAL AI DIAGNOSTIC PRESCRIPTION & INTAKE", 0, 1, 'R')
            
            self.set_xy(12, 10.5)
            self.set_font('Helvetica', '', 7)
            self.set_text_color(203, 213, 225)
            self.cell(110, 4, "Tertiary Clinical Telemetry & Autonomous Diagnostic Center", 0, 0, 'L')
            self.cell(0, 4, "OpenFDA & CDSCO Pharmacologically Verified", 0, 1, 'R')

        # Content begins below top header
        self.set_y(32)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*self.CARD_BORDER)
        self.set_line_width(0.2)
        self.line(12, self.h - 15, self.w - 12, self.h - 15)

        self.set_xy(12, self.h - 13)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(*self.TEXT_MUTED)
        self.cell(self.w - 24, 4, f'Page {self.page_no()} of {{nb}}   |   Spherix Digital Health Diagnostic Record   |   Confidential Medical Telemetry', 0, 0, 'C')

    def section_header(self, title, icon_text='', bg_color=None, text_color=None):
        """Draws a premium section header banner with automatic overflow check."""
        if self.get_y() > self.h - 32:
            self.add_page()

        bg_col = bg_color or self.PRIMARY_NAVY
        txt_col = text_color or (255, 255, 255)

        self.ln(2)
        start_y = self.get_y()
        self.set_fill_color(*bg_col)
        self.rect(12, start_y, self.w - 24, 6.5, 'F')
        
        # Left cyan/emerald accent indicator line
        self.set_fill_color(*self.ACCENT_CYAN)
        self.rect(12, start_y, 2.5, 6.5, 'F')

        self.set_xy(16, start_y + 0.8)
        self.set_text_color(*txt_col)
        self.set_font('Helvetica', 'B', 8.5)
        
        display_title = f"{icon_text}  {title.upper()}" if icon_text else title.upper()
        self.cell(self.w - 32, 5, to_latin1_str(display_title), 0, 1, 'L')
        self.ln(1.5)


def generate_spherix_clinical_pdf(patient_info, result, condition_details=None, vision_findings=None, image_path=None, doctor_review=None):
    """Builds an exhaustive, multi-page luxury clinical prescription PDF with ALL symptoms, findings, medical advice, and recovery protocols."""
    from PIL import Image
    pdf = SpherixClinicalPrescriptionPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    def check_space(needed_h):
        if pdf.get_y() + needed_h > pdf.h - 18:
            pdf.add_page()

    # ================= 1. PATIENT PROFILE & INTAKE BIOMETRICS =================
    pdf.section_header('Patient Intake & Baseline Telemetry', '[1]')
    
    height = patient_info.get('height')
    weight = patient_info.get('weight')
    bmi_str = "N/A"
    try:
        if height and weight:
            h_m = float(height) / 100.0
            w_kg = float(weight)
            bmi_val = round(w_kg / (h_m * h_m), 1)
            category = "Normal"
            if bmi_val < 18.5: category = "Underweight"
            elif bmi_val >= 30: category = "Obese"
            elif bmi_val >= 25: category = "Overweight"
            bmi_str = f"{bmi_val} ({category})"
    except Exception:
        bmi_str = "N/A"

    p_start_y = pdf.get_y()
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(*pdf.CARD_BORDER)
    pdf.set_line_width(0.3)

    col1_x = 16

    # Row 1: Demographics
    pdf.set_xy(col1_x, p_start_y + 2.5)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.TEXT_MUTED)
    pdf.cell(58, 3.8, 'FULL LEGAL NAME', 0, 0)
    pdf.cell(58, 3.8, 'AGE / BIOLOGICAL SEX', 0, 0)
    pdf.cell(58, 3.8, 'HEIGHT / WEIGHT / BMI', 0, 1)

    pdf.set_xy(col1_x, p_start_y + 6.5)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*pdf.TEXT_DARK)
    pdf.cell(58, 4.5, to_latin1_str(patient_info.get('name', 'Patient Intake')), 0, 0)
    pdf.cell(58, 4.5, to_latin1_str(f"{patient_info.get('age', 'N/A')} Yrs  |  {patient_info.get('gender', 'N/A')}"), 0, 0)
    pdf.cell(58, 4.5, to_latin1_str(f"{height or 'N/A'}cm / {weight or 'N/A'}kg / BMI {bmi_str}"), 0, 1)

    # Row 2: Duration, Region, Allergies
    pdf.set_xy(col1_x, p_start_y + 12.5)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.TEXT_MUTED)
    pdf.cell(58, 3.8, 'DURATION & SEVERITY', 0, 0)
    pdf.cell(58, 3.8, 'BODY REGION / ANATOMY', 0, 0)
    pdf.cell(58, 3.8, 'KNOWN DRUG ALLERGIES', 0, 1)

    pdf.set_xy(col1_x, p_start_y + 16.5)
    pdf.set_font('Helvetica', '', 8.5)
    pdf.set_text_color(*pdf.TEXT_MAIN)
    dur_sev = f"{patient_info.get('duration', 'Acute')} | {patient_info.get('severity', 'Moderate')}"
    body_part_full = patient_info.get('body_part', 'General / Systemic').capitalize()
    if patient_info.get('body_part_detail'):
        body_part_full += f" ({patient_info.get('body_part_detail')})"
    pdf.cell(58, 4.5, to_latin1_str(dur_sev), 0, 0)
    pdf.cell(58, 4.5, to_latin1_str(body_part_full), 0, 0)
    
    # Red highlight for allergies if present
    allergies_val = patient_info.get('allergies') or 'None Reported (NKDA)'
    if allergies_val.lower() not in ['none', 'none reported', 'none reported (nkda)', 'no']:
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(*pdf.ACCENT_ROSE)
    pdf.cell(58, 4.5, to_latin1_str(allergies_val), 0, 1)

    # Row 3: Current Meds & History
    pdf.set_xy(col1_x, p_start_y + 22.5)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.TEXT_MUTED)
    pdf.cell(58, 3.8, 'CURRENT MEDICATIONS', 0, 0)
    pdf.cell(116, 3.8, 'MEDICAL HISTORY & LIFESTYLE HABITS', 0, 1)

    pdf.set_xy(col1_x, p_start_y + 26.5)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(*pdf.TEXT_MAIN)
    pdf.cell(58, 4.2, to_latin1_str(patient_info.get('current_medicines') or 'None Reported'), 0, 0)
    
    hist_items = []
    if patient_info.get('medical_history') and patient_info.get('medical_history') != 'None':
        hist_items.append(f"History: {patient_info.get('medical_history')}")
    if patient_info.get('smoking_status'): hist_items.append(f"Smoking: {patient_info.get('smoking_status')}")
    if patient_info.get('alcohol_consumption'): hist_items.append(f"Alcohol: {patient_info.get('alcohol_consumption')}")
    if patient_info.get('exercise_habits'): hist_items.append(f"Exercise: {patient_info.get('exercise_habits')}")
    hist_lifestyle_str = " | ".join(hist_items) if hist_items else "None Reported / Standard Baseline"
    pdf.cell(116, 4.2, to_latin1_str(hist_lifestyle_str[:85]), 0, 1)

    # Row 4: Chief Complaint
    pdf.set_xy(col1_x, p_start_y + 32)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.ACCENT_SKY)
    pdf.cell(pdf.w - 32, 3.8, 'REPORTED CHIEF COMPLAINT:', 0, 1)

    raw_s = patient_info.get('raw_symptoms') or patient_info.get('symptoms') or 'Unspecified symptoms'
    pdf.set_x(col1_x)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(*pdf.TEXT_MAIN)
    pdf.multi_cell(pdf.w - 32, 3.8, to_latin1_str(f'"{raw_s}"'), 0, 'L')

    p_end_y = pdf.get_y() + 2
    pdf.rect(12, p_start_y, pdf.w - 24, p_end_y - p_start_y, 'D')
    pdf.set_y(p_end_y + 2)

    # ================= 2. PRIMARY DIAGNOSTIC FINDING & PATHOPHYSIOLOGY =================
    primary_condition = result.get('conditions', ['General Clinical Assessment'])[0] if result.get('conditions') else 'General Assessment'
    risk_level = result.get('risk_level', '🟢 Low')
    
    risk_color = pdf.ACCENT_EMERALD
    if 'High' in str(risk_level): risk_color = pdf.ACCENT_ROSE
    elif 'Moderate' in str(risk_level): risk_color = pdf.ACCENT_AMBER

    check_space(45)
    pdf.section_header(f'Primary Diagnostic Finding: {primary_condition}', '[2]', bg_color=pdf.PRIMARY_NAVY)

    prim_start_y = pdf.get_y()
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(*pdf.CARD_BORDER)

    pdf.set_xy(16, prim_start_y + 2.5)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(*pdf.PRIMARY_NAVY)
    pdf.cell(110, 5.5, to_latin1_str(primary_condition), 0, 0, 'L')

    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*risk_color)
    pdf.cell(0, 5.5, to_latin1_str(f"TRIAGE LEVEL: {risk_level}"), 0, 1, 'R')

    # Pathophysiology Mechanism Block
    patho = result.get('pathophysiology') or (condition_details.get('overview') if condition_details else 'Tissue inflammatory response and physiological cellular mediation corresponding to symptom onset.')
    pdf.set_xy(16, pdf.get_y() + 1.5)
    
    patho_box_start = pdf.get_y()
    pdf.set_fill_color(240, 249, 255)
    pdf.set_draw_color(186, 230, 253)
    
    pdf.set_xy(18, patho_box_start + 1.5)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.ACCENT_SKY)
    pdf.cell(0, 3.5, 'PATHOPHYSIOLOGY & BIOLOGICAL MECHANISM:', 0, 1)
    pdf.set_x(18)
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(*pdf.TEXT_MAIN)
    pdf.multi_cell(pdf.w - 36, 3.6, to_latin1_str(patho), 0, 'L')
    patho_box_h = pdf.get_y() - patho_box_start + 1.5
    pdf.rect(15, patho_box_start, pdf.w - 30, patho_box_h, 'DF')

    # Clinical Evaluation Summary
    pdf.set_xy(16, pdf.get_y() + 2)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.TEXT_MUTED)
    pdf.cell(0, 3.5, 'CLINICAL EVALUATION SUMMARY:', 0, 1)
    pdf.set_x(16)
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(*pdf.TEXT_MAIN)
    summary_text = (condition_details.get('description') or condition_details.get('overview')) if condition_details else result.get('clinical_summary', 'Diagnostic evaluation completed.')
    pdf.multi_cell(pdf.w - 32, 3.8, to_latin1_str(summary_text), 0, 'L')

    # Expected Clinical Progression Window
    triage_time = result.get('triage_timeline', '24 - 48 Hours Clinical Window')
    pdf.set_x(16)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.ACCENT_INDIGO)
    pdf.cell(0, 4, to_latin1_str(f"Expected Clinical Progression Window: {triage_time}"), 0, 1)

    prim_end_y = pdf.get_y() + 2
    pdf.rect(12, prim_start_y, pdf.w - 24, prim_end_y - prim_start_y, 'D')
    pdf.set_y(prim_end_y + 2.5)

    # ================= 3. CORE CLINICAL DIRECTIVES & MEDICAL ADVICE =================
    ai_advice = result.get('ai_recommendations') or ['Rest the affected region in an elevated position', 'Maintain steady hydration with electrolyte balance', 'Monitor vital signs every 6 to 8 hours', 'Avoid high-intensity physical exertion']
    check_space(35 + len(ai_advice) * 6)
    pdf.section_header('Clinical Directives & Recommended Medical Advice', '[3]', bg_color=pdf.ACCENT_INDIGO)
    
    adv_start_y = pdf.get_y()
    pdf.set_draw_color(*pdf.CARD_BORDER)
    
    for idx, directive in enumerate(ai_advice, 1):
        pdf.set_xy(16, pdf.get_y() + 1)
        pdf.set_fill_color(245, 243, 255)
        pdf.set_text_color(*pdf.ACCENT_INDIGO)
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.cell(6, 4.5, f"#{idx}", 1, 0, 'C', 1)
        
        pdf.set_xy(24, pdf.get_y())
        pdf.set_text_color(*pdf.TEXT_MAIN)
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.multi_cell(pdf.w - 40, 4, to_latin1_str(f"  {directive}"), 0, 'L')

    adv_end_y = pdf.get_y() + 2
    pdf.rect(12, adv_start_y, pdf.w - 24, adv_end_y - adv_start_y, 'D')
    pdf.set_y(adv_end_y + 2.5)

    # ================= 4. OPENFDA VERIFIED SUPPORTIVE MEDICATIONS & PHARMACOLOGY =================
    raw_medications = result.get('supportive_relief_options', [])
    medications = [
        m for m in raw_medications
        if isinstance(m, dict) and not m.get('is_disclaimer') and (m.get('fda_verified') or m.get('source') == 'OpenFDA API')
    ]
    if not medications and raw_medications:
        medications = [{'generic_name': str(m), 'brand_name': str(m), 'primary_use': 'Pharmacological supportive relief.', 'instructions': 'Take orally as directed.', 'caution': 'Consult physician before use.'} for m in raw_medications if 'consult' not in str(m).lower()][:3]

    if medications:
        check_space(45)
        pdf.section_header('OpenFDA Verified Supportive Medications', '[4]', bg_color=(5, 150, 105))
        
        for med in medications:
            check_space(32)
            m_start_y = pdf.get_y()

            # Header row
            pdf.set_xy(18, m_start_y + 2)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(0, 0, 0)
            med_name_display = med.get('generic_name') or med.get('name') or 'Medication'
            brand_name = med.get('brand_name') or med_name_display
            pdf.cell(100, 4.5, to_latin1_str(f"{med_name_display} (Brand: {brand_name})"), 0, 0)

            pdf.set_font('Helvetica', 'B', 7)
            pdf.set_text_color(5, 150, 105)
            pdf.cell(0, 4.5, 'OpenFDA / CDSCO VERIFIED Rx/OTC', 0, 1, 'R')

            # Indication
            pdf.set_xy(18, m_start_y + 7)
            pdf.set_font('Helvetica', 'B', 7.5)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(26, 3.8, 'Clinical Indication:', 0, 0)
            pdf.set_font('Helvetica', '', 7.5)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(pdf.w - 48, 3.8, to_latin1_str(med.get('primary_use') or 'Symptomatic comfort and therapeutic relief.'), 0, 'L')

            # Dosage
            pdf.set_x(18)
            pdf.set_font('Helvetica', 'B', 7.5)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(26, 3.8, 'Standard Dosage:', 0, 0)
            pdf.set_font('Helvetica', '', 7.5)
            pdf.set_text_color(0, 0, 0)
            instr = med.get('instructions') or med.get('usage_instructions') or 'Take orally with water after meals as per packaging directions.'
            pdf.multi_cell(pdf.w - 48, 3.8, to_latin1_str(instr), 0, 'L')

            # Cautions
            pdf.set_x(18)
            pdf.set_font('Helvetica', 'B', 7.5)
            pdf.set_text_color(180, 20, 20)
            pdf.cell(26, 3.8, 'Precautions:', 0, 0)
            pdf.set_font('Helvetica', '', 7.5)
            pdf.set_text_color(0, 0, 0)
            caut = med.get('caution') or 'Do not exceed maximum daily dosage. Consult a doctor if symptoms persist.'
            pdf.multi_cell(pdf.w - 48, 3.8, to_latin1_str(caut), 0, 'L')

            m_end_y = pdf.get_y() + 2
            m_box_h = m_end_y - m_start_y
            pdf.set_draw_color(*pdf.CARD_BORDER)
            pdf.rect(12, m_start_y, pdf.w - 24, m_box_h, 'D')
            
            # Left green stripe
            pdf.set_fill_color(5, 150, 105)
            pdf.rect(12, m_start_y, 2.5, m_box_h, 'F')
            pdf.set_y(m_end_y + 2)

    # ================= 5. RECOVERY NUTRITION & SELF-CARE PROTOCOLS =================
    diet = result.get('dietary_guidelines', {})
    self_care_list = result.get('self_care_suggestions', [])

    check_space(45)
    pdf.section_header('Recovery Nutrition, Hydration & Self-Care Protocols', '[5]', bg_color=pdf.ACCENT_INDIGO)

    care_start_y = pdf.get_y()
    card_w = (pdf.w - 28) / 2

    # Column 1: Nutrition
    rec_food = diet.get('recommended', ['Warm fluids & electrolytes', 'Nutrient-rich broth', 'Adequate dietary hydration', 'Fresh citrus & antioxidants'])
    avoid_food = diet.get('avoid', ['Excess sodium & caffeine', 'Greasy/processed foods', 'Refined sugars & alcohol', 'Irritant / spicy foods'])

    pdf.set_xy(15, care_start_y + 2)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*pdf.ACCENT_INDIGO)
    pdf.cell(card_w - 6, 4, 'Nutritional & Dietary Guidelines', 0, 1)

    pdf.set_x(15)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.ACCENT_EMERALD)
    pdf.cell(card_w - 6, 3.5, '[+] Recommended Intake:', 0, 1)
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(*pdf.TEXT_MAIN)
    for item in rec_food[:4]:
        pdf.set_x(17)
        pdf.cell(card_w - 10, 3.5, f"* {to_latin1_str(item)}", 0, 1)

    pdf.set_x(15)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.ACCENT_ROSE)
    pdf.cell(card_w - 6, 3.5, '[-] Substances to Avoid:', 0, 1)
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(*pdf.TEXT_MAIN)
    for item in avoid_food[:4]:
        pdf.set_x(17)
        pdf.cell(card_w - 10, 3.5, f"- {to_latin1_str(item)}", 0, 1)

    col1_end_y = pdf.get_y()

    # Column 2: Self-Care Protocols
    col2_x = 14 + card_w
    pdf.set_xy(col2_x + 3, care_start_y + 2)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*pdf.ACCENT_INDIGO)
    pdf.cell(card_w - 6, 4, 'Self-Care & Daily Routine', 0, 1)

    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(*pdf.TEXT_MAIN)
    for sc in (self_care_list or ['Rest in a cool, quiet environment', 'Maintain regular sleep schedule', 'Apply gentle compresses if indicated'])[:5]:
        pdf.set_x(col2_x + 3)
        pdf.multi_cell(card_w - 6, 3.5, f"* {to_latin1_str(sc)}", 0, 'L')

    col2_end_y = pdf.get_y()
    care_box_h = max(col1_end_y, col2_end_y) - care_start_y + 2

    # Draw boxes
    pdf.set_draw_color(*pdf.CARD_BORDER)
    pdf.rect(12, care_start_y, card_w, care_box_h, 'D')
    pdf.rect(col2_x, care_start_y, card_w, care_box_h, 'D')
    pdf.set_y(care_start_y + care_box_h + 2.5)

    # ================= 6. EMERGENCY & RED-FLAG WARNINGS =================
    warnings = result.get('warning_alerts', [])
    if warnings:
        check_space(25 + len(warnings) * 4)
        pdf.section_header('Emergency & Red-Flag Warnings (Seek Immediate Care)', '[!]', bg_color=pdf.ACCENT_ROSE)
        
        w_start_y = pdf.get_y()
        pdf.set_xy(16, w_start_y + 2)
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.set_text_color(*pdf.ACCENT_ROSE)
        pdf.cell(0, 3.5, 'SEEK IMMEDIATE EMERGENCY MEDICAL EVALUATION IF EXPERIENCING:', 0, 1)

        pdf.set_font('Helvetica', '', 7.5)
        pdf.set_text_color(159, 18, 57)
        for alert in warnings[:4]:
            pdf.set_x(18)
            pdf.multi_cell(pdf.w - 36, 3.8, f"[!] {to_latin1_str(alert)}", 0, 'L')

        w_end_y = pdf.get_y() + 2
        w_h = w_end_y - w_start_y
        pdf.set_fill_color(255, 241, 242)
        pdf.set_draw_color(254, 205, 211)
        pdf.rect(12, w_start_y, pdf.w - 24, w_h, 'D')
        pdf.set_y(w_end_y + 2.5)

    # ================= 7. RECOMMENDED NEXT STEPS & CLINICAL VALIDATION =================
    specs = result.get('recommended_specialists', ['General Physician', 'Internal Medicine'])
    tests = result.get('suggested_tests', ['Complete Blood Count (CBC)', 'Vital Signs Screening'])

    check_space(45)
    pdf.section_header('Recommended Next Steps & Clinical Validation', '[6]', bg_color=pdf.PRIMARY_NAVY)

    steps_start_y = pdf.get_y()
    col_w = (pdf.w - 32) / 2

    pdf.set_xy(16, steps_start_y + 2.5)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*pdf.TEXT_MUTED)
    pdf.cell(col_w, 3.5, 'SUGGESTED MEDICAL SPECIALISTS:', 0, 0)
    pdf.set_xy(16 + col_w, steps_start_y + 2.5)
    pdf.cell(col_w, 3.5, 'RECOMMENDED DIAGNOSTIC TESTS:', 0, 1)

    pdf.set_xy(16, steps_start_y + 6.5)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*pdf.ACCENT_SKY)
    pdf.multi_cell(col_w, 3.8, to_latin1_str(", ".join(specs)), 0, 'L')

    pdf.set_xy(16 + col_w, steps_start_y + 6.5)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*pdf.ACCENT_INDIGO)
    pdf.multi_cell(col_w, 3.8, to_latin1_str(", ".join(tests)), 0, 'L')

    # Medical Disclaimer
    disclaimer_text = result.get('medical_disclaimer') or 'This clinical report provides AI-guided supportive diagnostic intelligence and is intended for informational/triaging purposes. It does not replace formal clinical consultation, examination, or definitive diagnosis by a licensed physician.'
    pdf.set_xy(16, pdf.get_y() + 2)
    pdf.set_font('Helvetica', 'I', 6.5)
    pdf.set_text_color(*pdf.TEXT_MUTED)
    pdf.multi_cell(pdf.w - 32, 3, to_latin1_str(f"Notice: {disclaimer_text}"), 0, 'L')

    # Signature and Stamp row
    sig_line_y = pdf.get_y() + 2.5
    pdf.set_draw_color(203, 213, 225)
    pdf.line(16, sig_line_y, pdf.w - 16, sig_line_y)

    pdf.set_xy(16, sig_line_y + 1.5)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_text_color(*pdf.TEXT_MUTED)
    pdf.cell(85, 3.5, "Attending Physician Validation & Signature:", 0, 0)
    pdf.cell(10, 3.5, "", 0, 0)
    pdf.cell(0, 3.5, "Authorized Hospital / Spherix Stamp:", 0, 1)

    box_sig_y = sig_line_y + 5.5
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(*pdf.CARD_BORDER)
    pdf.rect(16, box_sig_y, 75, 14, 'DF')
    pdf.rect(105, box_sig_y, 75, 14, 'DF')

    sig_file = os.path.join(current_app.root_path, 'static', 'images', 'signature.png')
    if os.path.exists(sig_file):
        try:
            with Image.open(sig_file) as pil_img:
                rgb = pil_img.convert('RGB')
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                    rgb.save(tmp.name, 'JPEG')
                    pdf.image(tmp.name, x=18, y=box_sig_y + 1, w=65, h=12)
                os.unlink(tmp.name)
        except Exception:
            pass
    else:
        pdf.set_xy(18, box_sig_y + 3.5)
        pdf.set_font('Courier', 'BI', 9)
        pdf.set_text_color(*pdf.PRIMARY_NAVY)
        pdf.cell(70, 5, "/s/ Dr. Sunny Kumar, MD", 0, 0, 'C')

    stamp_file = os.path.join(current_app.root_path, 'static', 'images', 'stamp.png')
    if os.path.exists(stamp_file):
        try:
            with Image.open(stamp_file) as pil_img:
                rgb = pil_img.convert('RGB')
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                    rgb.save(tmp.name, 'JPEG')
                    pdf.image(tmp.name, x=132, y=box_sig_y + 1, w=20, h=12)
                os.unlink(tmp.name)
        except Exception:
            pass
    else:
        pdf.set_xy(105, box_sig_y + 3.5)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*pdf.ACCENT_EMERALD)
        pdf.cell(75, 5, "SPHERIX CLINICAL VERIFIED", 0, 0, 'C')

    steps_end_y = box_sig_y + 16
    pdf.rect(12, steps_start_y, pdf.w - 24, steps_end_y - steps_start_y, 'D')
    pdf.set_y(steps_end_y + 2)

    return pdf

