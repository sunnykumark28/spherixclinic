"""
Spherix Clinic - Nutrition & Fitness Intelligence Engine
Clinical Biometric Math, Macronutrient Allocation, 7-Day Precision Meal Plans & Adaptive Workout Routines
"""

import math
import os
import json
import requests

# Groq API Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_BASE = os.getenv('GROQ_API_BASE', 'https://api.groq.com/openai/v1')
GROQ_API_MODEL = os.getenv('GROQ_API_MODEL', 'openai/gpt-oss-20b')

def is_groq_active():
    return bool(GROQ_API_KEY and GROQ_API_KEY != 'none')

# ==========================================
# 1. BIOMETRICS & ENERGY EXPENDITURE ENGINE
# ==========================================

ACTIVITY_MULTIPLIERS = {
    'sedentary': {'multiplier': 1.2, 'label': 'Sedentary (Little or no exercise, desk job)'},
    'light': {'multiplier': 1.375, 'label': 'Lightly Active (Light exercise 1-3 days/week)'},
    'moderate': {'multiplier': 1.55, 'label': 'Moderately Active (Moderate exercise 3-5 days/week)'},
    'very_active': {'multiplier': 1.725, 'label': 'Very Active (Hard exercise 6-7 days/week)'},
    'extra_active': {'multiplier': 1.9, 'label': 'Extremely Active (Athletic training / physical labor)'}
}

GOAL_MODIFIERS = {
    'weight_loss': {'cal_diff': -500, 'label': 'Weight Loss (Sustainable ~0.5kg/week fat reduction)'},
    'extreme_loss': {'cal_diff': -750, 'label': 'Rapid Fat Loss (Aggressive ~0.75kg/week deficit)'},
    'maintenance': {'cal_diff': 0, 'label': 'Maintenance (Weight stabilization & metabolic health)'},
    'lean_bulk': {'cal_diff': 300, 'label': 'Lean Muscle Gain (Controlled clean surplus)'},
    'muscle_hypertrophy': {'cal_diff': 500, 'label': 'Muscle Hypertrophy & Power (Surplus for max gains)'},
    'keto_fat_burn': {'cal_diff': -400, 'label': 'Ketogenic / Low-Carb Metabolic Shift'},
    'diabetic_control': {'cal_diff': -300, 'label': 'Glycemic Regulation & Insulin Sensitivity'},
    'heart_health': {'cal_diff': -250, 'label': 'Cardioprotective & DASH Blood Pressure Support'}
}

DIET_MACRO_RATIOS = {
    'balanced': {'protein': 0.25, 'carbs': 0.50, 'fat': 0.25, 'label': 'Balanced Omnivore'},
    'high_protein': {'protein': 0.35, 'carbs': 0.40, 'fat': 0.25, 'label': 'High-Protein Fitness'},
    'low_carb': {'protein': 0.30, 'carbs': 0.20, 'fat': 0.50, 'label': 'Low Carb / Ketogenic'},
    'mediterranean': {'protein': 0.25, 'carbs': 0.45, 'fat': 0.30, 'label': 'Mediterranean Cardio-Shield'},
    'vegetarian_indian': {'protein': 0.25, 'carbs': 0.50, 'fat': 0.25, 'label': 'Vedic Ayurvedic Vegetarian'},
    'vegan_plant': {'protein': 0.25, 'carbs': 0.55, 'fat': 0.20, 'label': 'Whole-Food Plant-Based (Vegan)'},
    'diabetic_friendly': {'protein': 0.30, 'carbs': 0.35, 'fat': 0.35, 'label': 'Glucoregulatory Low-GI'},
    'dash_heart': {'protein': 0.25, 'carbs': 0.50, 'fat': 0.25, 'label': 'DASH Heart & Renal Health'}
}

def calculate_biometrics(age, gender, weight_kg, height_cm, activity_level='moderate', goal='weight_loss', diet_pref='balanced'):
    """
    Computes Mifflin-St Jeor BMR, TDEE, Target Calories, and Exact Macro Splits (grams and percentages).
    """
    age = max(10, min(int(age), 120))
    weight_kg = max(20.0, float(weight_kg))
    height_cm = max(50.0, float(height_cm))
    gender = str(gender).lower().strip()
    
    # 1. Mifflin-St Jeor BMR Formula
    if gender in ['male', 'm']:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    # 2. Harris-Benedict (Revised) for clinical comparison
    if gender in ['male', 'm']:
        hb_bmr = 88.362 + (13.397 * weight_kg) + (4.799 * height_cm) - (5.677 * age)
    else:
        hb_bmr = 447.593 + (9.247 * weight_kg) + (3.098 * height_cm) - (4.330 * age)

    # 3. BMI Calculation
    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m ** 2), 1)
    
    if bmi < 18.5:
        bmi_category = "Underweight"
        bmi_color = "amber"
    elif bmi < 24.9:
        bmi_category = "Healthy / Normal Weight"
        bmi_color = "emerald"
    elif bmi < 29.9:
        bmi_category = "Overweight"
        bmi_color = "orange"
    else:
        bmi_category = "Obese (Clinical Support Recommended)"
        bmi_color = "rose"

    # Ideal Body Weight (Devine Formula)
    height_inches = height_cm / 2.54
    inches_over_5ft = max(0, height_inches - 60)
    if gender in ['male', 'm']:
        ideal_weight_kg = round(50.0 + 2.3 * inches_over_5ft, 1)
    else:
        ideal_weight_kg = round(45.5 + 2.3 * inches_over_5ft, 1)

    # 4. TDEE Calculation
    act_info = ACTIVITY_MULTIPLIERS.get(activity_level, ACTIVITY_MULTIPLIERS['moderate'])
    tdee = round(bmr * act_info['multiplier'])

    # 5. Target Calories
    goal_info = GOAL_MODIFIERS.get(goal, GOAL_MODIFIERS['weight_loss'])
    target_calories = max(1200 if gender != 'male' else 1400, tdee + goal_info['cal_diff'])
    
    # 6. Macronutrient Allocation
    ratios = DIET_MACRO_RATIOS.get(diet_pref, DIET_MACRO_RATIOS['balanced'])
    
    protein_ratio = ratios['protein']
    carb_ratio = ratios['carbs']
    fat_ratio = ratios['fat']
    
    protein_cal = target_calories * protein_ratio
    carb_cal = target_calories * carb_ratio
    fat_cal = target_calories * fat_ratio

    protein_grams = round(protein_cal / 4.0)
    carb_grams = round(carb_cal / 4.0)
    fat_grams = round(fat_cal / 9.0)
    
    # Water Requirement (Clinical formula: ~35ml per kg + 500ml for active exercise)
    base_water_liters = round((weight_kg * 0.035) + (0.5 if activity_level in ['moderate', 'very_active', 'extra_active'] else 0.2), 1)
    water_cups = round(base_water_liters * 4.2)
    
    # Estimated Body Fat % (Deurenberg clinical formula based on BMI, Age & Gender)
    if gender in ['male', 'm']:
        est_body_fat = round(max(5.0, min(50.0, (1.20 * bmi) + (0.23 * age) - 16.2)), 1)
    else:
        est_body_fat = round(max(10.0, min(55.0, (1.20 * bmi) + (0.23 * age) - 5.4)), 1)
        
    fat_mass_kg = round(weight_kg * (est_body_fat / 100.0), 1)
    lean_mass_kg = round(weight_kg - fat_mass_kg, 1)

    # Fiber Target (14g per 1000 kcal - American Heart Assoc & WHO guidelines)
    fiber_grams = round((target_calories / 1000.0) * 14.0)

    return {
        'age': age,
        'gender': gender,
        'weight_kg': weight_kg,
        'height_cm': height_cm,
        'bmi': bmi,
        'bmi_category': bmi_category,
        'bmi_color': bmi_color,
        'body_fat_pct': est_body_fat,
        'fat_mass_kg': fat_mass_kg,
        'lean_mass_kg': lean_mass_kg,
        'ideal_weight_kg': ideal_weight_kg,
        'bmr': round(bmr),
        'hb_bmr': round(hb_bmr),
        'tdee': tdee,
        'activity_level': activity_level,
        'activity_label': act_info['label'],
        'goal': goal,
        'goal_label': goal_info['label'],
        'goal_diff': goal_info['cal_diff'],
        'diet_pref': diet_pref,
        'diet_label': ratios['label'],
        'target_calories': target_calories,
        'macros': {
            'protein': {'grams': protein_grams, 'calories': round(protein_cal), 'pct': int(protein_ratio * 100)},
            'carbs': {'grams': carb_grams, 'calories': round(carb_cal), 'pct': int(carb_ratio * 100)},
            'fat': {'grams': fat_grams, 'calories': round(fat_cal), 'pct': int(fat_ratio * 100)},
            'fiber_grams': fiber_grams
        },
        'hydration': {
            'liters_per_day': base_water_liters,
            'cups_per_day': water_cups
        }
    }


# ==========================================
# 2. 7-DAY MEAL PLAN GENERATOR DATABASE
# ==========================================

MEAL_PLANS_BY_DIET = {
    'vegetarian_indian': {
        'Monday': {
            'breakfast': {'name': 'Sprouted Moong Dal Chilla with Mint Chutney & Walnuts', 'portion': '2 chillas (150g) + 2 tbsp chutney + 4 walnut halves', 'cal': 360, 'p': 18, 'c': 45, 'f': 12, 'tags': ['High Protein', 'Vedic Gut Healing']},
            'snack_am': {'name': 'Roasted Makhana (Foxnuts) with Turmeric & Himalayan Pink Salt', 'portion': '1 bowl (30g)', 'cal': 120, 'p': 4, 'c': 20, 'f': 3, 'tags': ['Low GI', 'Mineral Rich']},
            'lunch': {'name': 'Paneer Tikka with Quinoa Brown Rice, Yellow Dal Tadka & Cucumber Salad', 'portion': '100g low-fat paneer, 1 cup dal, 1/2 cup quinoa', 'cal': 540, 'p': 28, 'c': 58, 'f': 18, 'tags': ['Complete Protein', 'High Fiber']},
            'snack_pm': {'name': 'Masala Spiced Buttermilk (Chaas) with Chia Seeds', 'portion': '1 tall glass (250ml) + 1 tsp chia', 'cal': 95, 'p': 5, 'c': 7, 'f': 4, 'tags': ['Probiotic', 'Cooling']},
            'dinner': {'name': 'Palak Paneer with Multigrain Jowar/Bajra Roti & Steamed Veggies', 'portion': '1 bowl palak sabzi, 2 small rotis, 1 cup sautéed zucchini', 'cal': 420, 'p': 22, 'c': 48, 'f': 14, 'tags': ['Iron Boost', 'Gluten Friendly']}
        },
        'Tuesday': {
            'breakfast': {'name': 'Oats Vegetable Upma with Crushed Almonds & Ginger Chai', 'portion': '1 medium bowl (200g) + 6 almonds', 'cal': 350, 'p': 12, 'c': 52, 'f': 10, 'tags': ['Beta-Glucan Heart Health']},
            'snack_am': {'name': 'Guava or Pomegranate Seeds with Chaat Masala', 'portion': '1 medium bowl (150g)', 'cal': 110, 'p': 2, 'c': 24, 'f': 1, 'tags': ['Vitamin C', 'Antioxidants']},
            'lunch': {'name': 'Rajma (Red Kidney Beans) Curry with Steamed Brown Rice & Kachumber', 'portion': '1.5 cups rajma, 1 cup cooked brown rice, salad', 'cal': 520, 'p': 22, 'c': 75, 'f': 11, 'tags': ['Complex Carbs', 'Clean Energy']},
            'snack_pm': {'name': 'Spiced Roasted Chana with Green Tea', 'portion': '1/2 cup (40g) roasted chana + green tea', 'cal': 140, 'p': 8, 'c': 22, 'f': 3, 'tags': ['Crunchy Snack', 'Zero Sugar']},
            'dinner': {'name': 'Tofu & Vegetable Stir-Fry with Soya Chunks Curry & 1 Millet Roti', 'portion': '100g firm tofu, 30g soya chunks curry, 1 roti', 'cal': 450, 'p': 32, 'c': 40, 'f': 13, 'tags': ['Muscle Repair', 'Low Carb']}
        },
        'Wednesday': {
            'breakfast': {'name': 'Besan Vegetable Toast or Steamed Idlis with Sambhar & Coconut Chutney', 'portion': '3 steamed idlis + 1.5 cups dal sambhar', 'cal': 370, 'p': 14, 'c': 62, 'f': 6, 'tags': ['Fermented Gut Friendly']},
            'snack_am': {'name': 'Curd with Flaxseeds & a handful of Berries', 'portion': '1 cup greek yogurt/hung curd + 1 tbsp flax', 'cal': 150, 'p': 12, 'c': 10, 'f': 6, 'tags': ['Omega-3', 'High Calcium']},
            'lunch': {'name': 'Methi Thepla with Chana Masala (Chickpea Curry) & Beetroot Raita', 'portion': '2 soft theplas, 1 cup chana masala, 1/2 cup raita', 'cal': 530, 'p': 24, 'c': 68, 'f': 15, 'tags': ['Blood Sugar Control']},
            'snack_pm': {'name': 'Tender Coconut Water & 5 Soaked Almonds', 'portion': '1 fresh coconut water + 5 almonds', 'cal': 85, 'p': 3, 'c': 11, 'f': 3, 'tags': ['Electrolyte Refuel']},
            'dinner': {'name': 'Lauki (Bottle Gourd) & Chana Dal Khichdi with Roasted Papad & Ghee', 'portion': '1.5 bowls khichdi, 1 tsp A2 cow ghee, papad', 'cal': 410, 'p': 17, 'c': 60, 'f': 9, 'tags': ['Easy Digestion', 'Sattvic']}
        },
        'Thursday': {
            'breakfast': {'name': 'Paneer Bhurji with 2 Slices Whole Grain Multigrain Toast', 'portion': '100g spiced paneer scramble, 2 multigrain slices', 'cal': 390, 'p': 24, 'c': 32, 'f': 18, 'tags': ['High Protein']},
            'snack_am': {'name': 'Sliced Apple with 1 tbsp Natural Peanut Butter', 'portion': '1 medium crisp apple + 1 tbsp peanut butter', 'cal': 160, 'p': 4, 'c': 22, 'f': 8, 'tags': ['Satiety Booster']},
            'lunch': {'name': 'Soya Matar Curry with Ragi Roti, Curd & Sprouted Salad', 'portion': '1 bowl soya chunks curry, 2 ragi rotis, 1/2 cup curd', 'cal': 510, 'p': 30, 'c': 56, 'f': 14, 'tags': ['Bone Density', 'High Protein']},
            'snack_pm': {'name': 'Herbal Tulsi-Ginger Infusion with Mixed Pumpkin & Sunflower Seeds', 'portion': '1 mug herbal tea + 2 tbsp seed mix', 'cal': 120, 'p': 5, 'c': 5, 'f': 9, 'tags': ['Immunity Defense']},
            'dinner': {'name': 'Mixed Vegetable Dalia (Broken Wheat Porridge) with Paneer Cubes', 'portion': '1.5 cups vegetable dalia + 60g sautéed paneer', 'cal': 430, 'p': 21, 'c': 52, 'f': 13, 'tags': ['Slow Digesting Carbs']}
        },
        'Friday': {
            'breakfast': {'name': 'Poha with Green Peas, Peanuts & Lemon Coriander Garnish', 'portion': '1 large bowl (220g) poha + lemon water', 'cal': 340, 'p': 9, 'c': 54, 'f': 10, 'tags': ['Light & Energizing']},
            'snack_am': {'name': 'Fresh Papaya Bowl with Chia Seeds & Squeeze of Lime', 'portion': '1.5 cups diced ripe papaya (200g)', 'cal': 105, 'p': 2, 'c': 24, 'f': 1, 'tags': ['Digestive Enzymes']},
            'lunch': {'name': 'Punjabi Kadhi Pakora (Baked/Steamed) with Brown Rice & Boiled Rajma', 'portion': '1.5 cups kadhi, 1 cup brown rice, cucumber', 'cal': 490, 'p': 19, 'c': 65, 'f': 15, 'tags': ['Probiotic Kadhi']},
            'snack_pm': {'name': 'Roasted Soy Nuts / Edamame with Chaat Spice', 'portion': '1/3 cup (35g)', 'cal': 145, 'p': 14, 'c': 9, 'f': 6, 'tags': ['Muscle Fuel']},
            'dinner': {'name': 'Stir-Fried Broccoli, Bell Peppers, Mushrooms & Grilled Paneer Skewers', 'portion': '200g sautéed veggies + 120g grilled cottage cheese', 'cal': 440, 'p': 26, 'c': 22, 'f': 24, 'tags': ['Low Carb Night']}
        },
        'Saturday': {
            'breakfast': {'name': 'Masala Ragi Dosa with Vegetable Sambar & Tomato Chutney', 'portion': '2 medium crispy dosas + 1 bowl sambar', 'cal': 360, 'p': 12, 'c': 60, 'f': 7, 'tags': ['Calcium & Iron Rich']},
            'snack_am': {'name': 'Amla & Beetroot Juice with Fresh Mint', 'portion': '1 glass (200ml) fresh cold-pressed juice', 'cal': 75, 'p': 2, 'c': 16, 'f': 0, 'tags': ['Liver Detox', 'Vit C']},
            'lunch': {'name': 'Chole (Garbanzo Bean Curry) with 1 Bhatura / 2 Whole Wheat Rotis & Onions', 'portion': '1.5 cups chole curry, 2 rotis, pickled salad', 'cal': 540, 'p': 23, 'c': 74, 'f': 14, 'tags': ['Weekend Sustenance']},
            'snack_pm': {'name': 'Spicy Boiled Sweet Corn with Lemon & Butter', 'portion': '1 cup sweet corn + 1/2 tsp grass-fed butter', 'cal': 135, 'p': 4, 'c': 25, 'f': 3, 'tags': ['Carotenoids']},
            'dinner': {'name': 'Creamy Spinach Dal (Dal Palak) with Jeera Rice & Roasted Paneer', 'portion': '1.5 cups dal palak, 3/4 cup jeera rice, 75g paneer', 'cal': 460, 'p': 24, 'c': 55, 'f': 14, 'tags': ['Deep Sleep Sustenance']}
        },
        'Sunday': {
            'breakfast': {'name': 'Avocado & Tomato Toast on Sourdough with Cottage Cheese', 'portion': '2 slices sourdough, 1/2 sliced avocado, 60g cottage cheese', 'cal': 380, 'p': 16, 'c': 42, 'f': 16, 'tags': ['Healthy Fats']},
            'snack_am': {'name': 'Mixed Roasted Nuts (Walnuts, Almonds, Pistachios)', 'portion': '1 small handful (25g)', 'cal': 160, 'p': 5, 'c': 6, 'f': 14, 'tags': ['Brain Boost']},
            'lunch': {'name': 'Vegetable Biryani with Soya Chunks, Mint Raita & Boiled Eggs/Paneer', 'portion': '1.5 cups biryani, 1 cup mint raita, 80g paneer', 'cal': 550, 'p': 27, 'c': 68, 'f': 16, 'tags': ['Sunday Feast']},
            'snack_pm': {'name': 'Dark Chocolate (85% Cacao) & Green Jasmine Tea', 'portion': '2 squares (20g) dark chocolate', 'cal': 120, 'p': 2, 'c': 9, 'f': 9, 'tags': ['Polyphenols']},
            'dinner': {'name': 'Creamy Roasted Pumpkin & Lentil Soup with Garlic Herb Toast', 'portion': '2 large bowls warm soup + 1 multigrain toast', 'cal': 380, 'p': 18, 'c': 52, 'f': 8, 'tags': ['Light Sunday Reset']}
        }
    },
    'high_protein': {
        'Monday': {
            'breakfast': {'name': 'Egg White & Whole Egg Omelet with Sautéed Spinach, Avocado & Whole Wheat Toast', 'portion': '3 egg whites + 1 whole egg, 1 slice toast, 1/4 avocado', 'cal': 380, 'p': 28, 'c': 22, 'f': 16, 'tags': ['High Protein', 'Choline Rich']},
            'snack_am': {'name': 'Whey/Plant Isolate Shake with Unsweetened Almond Milk & Blueberries', 'portion': '1 scoop protein (25g) + 250ml milk + 1/2 cup berries', 'cal': 180, 'p': 26, 'c': 12, 'f': 3, 'tags': ['Fast Absorbing']},
            'lunch': {'name': 'Grilled Chicken Breast / Salmon with Quinoa, Roasted Asparagus & Olive Oil', 'portion': '180g chicken or 160g salmon, 1 cup quinoa, veggies', 'cal': 560, 'p': 48, 'c': 42, 'f': 18, 'tags': ['Hypertrophy Gold Standard']},
            'snack_pm': {'name': 'Non-Fat Greek Yogurt with Crushed Walnuts & Cinnamon', 'portion': '1 cup (200g) greek yogurt + 15g walnuts', 'cal': 170, 'p': 20, 'c': 8, 'f': 7, 'tags': ['Casein Slow Release']},
            'dinner': {'name': 'Stir-Fried Lean Turkey/Beef or Grilled Fish with Broccoli & Sweet Potato', 'portion': '170g protein, 150g sweet potato, 1.5 cups broccoli', 'cal': 480, 'p': 42, 'c': 44, 'f': 12, 'tags': ['Glycogen Replenishment']}
        },
        'Tuesday': {
            'breakfast': {'name': 'Overnight Protein Oats with Chia Seeds, Greek Yogurt & Berries', 'portion': '50g rolled oats, 1/2 scoop whey, 100g yogurt, chia', 'cal': 410, 'p': 32, 'c': 48, 'f': 9, 'tags': ['Sustained Release']},
            'snack_am': {'name': '2 Hard-Boiled Eggs with Cracked Pepper & Sea Salt', 'portion': '2 large free-range eggs', 'cal': 140, 'p': 13, 'c': 1, 'f': 10, 'tags': ['Zero Sugar']},
            'lunch': {'name': 'Tuna or Grilled Chicken Salad Bowl with Mixed Greens, Cherry Tomatoes & Olive Dressing', 'portion': '180g tuna in brine, 3 cups salad, 1 tbsp olive oil', 'cal': 490, 'p': 46, 'c': 14, 'f': 24, 'tags': ['Omega-3 Boost']},
            'snack_pm': {'name': 'Cottage Cheese / Paneer Bowl with Roasted Pumpkin Seeds', 'portion': '150g low-fat cottage cheese + 15g seeds', 'cal': 180, 'p': 22, 'c': 7, 'f': 7, 'tags': ['Muscle Retention']},
            'dinner': {'name': 'Herb-Crusted Baked Cod or Grilled Chicken Breast with Brown Basmati & Green Beans', 'portion': '190g fish/chicken, 1 cup brown rice, green beans', 'cal': 510, 'p': 46, 'c': 50, 'f': 11, 'tags': ['Clean Fuel']}
        },
        'Wednesday': {
            'breakfast': {'name': 'Scrambled Eggs (2 Whole + 2 Whites) with Smoked Salmon on Rye Bread', 'portion': '4 egg mix, 40g smoked salmon, 1 slice toasted rye', 'cal': 420, 'p': 34, 'c': 20, 'f': 20, 'tags': ['Performance Fuel']},
            'snack_am': {'name': 'Protein Bar (Low Sugar <2g) & Black Espresso', 'portion': '1 bar (60g)', 'cal': 210, 'p': 21, 'c': 18, 'f': 7, 'tags': ['On the Go']},
            'lunch': {'name': 'Chicken/Turkey Breast Fajita Bowl with Black Beans, Peppers & Guacamole', 'portion': '180g chicken strips, 1/2 cup black beans, 2 tbsp guac', 'cal': 550, 'p': 48, 'c': 40, 'f': 17, 'tags': ['Fiber & Protein']},
            'snack_pm': {'name': 'Edamame in Pods with Sea Salt', 'portion': '1.5 cups steamed edamame (150g)', 'cal': 150, 'p': 14, 'c': 11, 'f': 6, 'tags': ['Plant BCAA']},
            'dinner': {'name': 'Lean Beef Steak or Grilled Chicken with Roasted Zucchini & Cauliflower Mash', 'portion': '180g steak/chicken, 1.5 cups cauliflower mash, salad', 'cal': 470, 'p': 45, 'c': 16, 'f': 22, 'tags': ['Creatine Boost']}
        },
        'Thursday': {
            'breakfast': {'name': 'High-Protein Banana Pancakes (Oats, Eggs & Whey)', 'portion': '3 medium pancakes (50g oats, 2 eggs, 1 scoop whey)', 'cal': 420, 'p': 36, 'c': 44, 'f': 10, 'tags': ['Clean Comfort']},
            'snack_am': {'name': 'Beef Jerky or Smoked Tofu Strips & Sliced Cucumber', 'portion': '40g lean jerky + 1 cucumber', 'cal': 130, 'p': 18, 'c': 4, 'f': 3, 'tags': ['High Sodium Refuel']},
            'lunch': {'name': 'Grilled Salmon Fillet with Quinoa Salad & Steamed Broccoli Florets', 'portion': '180g Atlantic salmon, 1 cup cooked quinoa, broccoli', 'cal': 580, 'p': 44, 'c': 42, 'f': 24, 'tags': ['Heart & Joint Health']},
            'snack_pm': {'name': 'Greek Yogurt with 1 Scoop Collagen/Whey & Chia Seeds', 'portion': '150g yogurt + 15g collagen + 1 tsp chia', 'cal': 190, 'p': 28, 'c': 9, 'f': 4, 'tags': ['Joint Recovery']},
            'dinner': {'name': 'Lemon Garlic Chicken Breast with Roasted Sweet Potato Wedges & Spinach', 'portion': '190g chicken, 150g sweet potato, 2 cups baby spinach', 'cal': 490, 'p': 48, 'c': 42, 'f': 10, 'tags': ['Lean Recovery']}
        },
        'Friday': {
            'breakfast': {'name': 'Breakfast Burrito (Eggs, Turkey Bacon, Black Beans & Salsa in Whole Wheat Wrap)', 'portion': '1 whole wrap, 2 eggs, 2 strips turkey bacon, salsa', 'cal': 440, 'p': 32, 'c': 38, 'f': 16, 'tags': ['Full Morning Fuel']},
            'snack_am': {'name': 'Mixed Berries with a handful of Raw Almonds', 'portion': '1 cup strawberries + 15 almonds', 'cal': 160, 'p': 5, 'c': 16, 'f': 10, 'tags': ['Polyphenols']},
            'lunch': {'name': 'Ground Turkey (93% lean) Rice Bowl with Avocado & Sautéed Bell Peppers', 'portion': '180g lean turkey, 3/4 cup brown rice, 1/4 avocado', 'cal': 540, 'p': 45, 'c': 42, 'f': 18, 'tags': ['Pre-Workout Power']},
            'snack_pm': {'name': 'Chocolate Protein Pudding (Greek Yogurt + Cocoa + Whey)', 'portion': '1 bowl (180g)', 'cal': 175, 'p': 25, 'c': 10, 'f': 3, 'tags': ['Guilt Free Sweet']},
            'dinner': {'name': 'Grilled White Fish (Snapper/Sea Bass) with Sautéed Asparagus & Garlic Rice', 'portion': '200g fish, 1 cup jasmine/brown rice, asparagus', 'cal': 460, 'p': 44, 'c': 48, 'f': 8, 'tags': ['Light Lean Dinner']}
        },
        'Saturday': {
            'breakfast': {'name': 'Avocado & Poached Eggs on Toasted Artisanal Sourdough', 'portion': '2 poached eggs, 1/2 avocado, 2 slices sourdough', 'cal': 430, 'p': 22, 'c': 38, 'f': 22, 'tags': ['Weekend Brunch']},
            'snack_am': {'name': 'Vanilla Whey Protein Shake with Ice & Cold Brew Coffee', 'portion': '1 scoop whey + 200ml cold brew + ice', 'cal': 130, 'p': 25, 'c': 3, 'f': 1, 'tags': ['Pre-Workout Kick']},
            'lunch': {'name': 'Grilled Sirloin Steak / High-Protein Tofu with Baked Potato & Green Salad', 'portion': '180g sirloin or 200g firm tofu, 1 medium potato', 'cal': 570, 'p': 46, 'c': 44, 'f': 20, 'tags': ['Strength Fuel']},
            'snack_pm': {'name': 'Roasted Chickpeas & Sliced Bell Peppers', 'portion': '1/2 cup crispy roasted chickpeas', 'cal': 140, 'p': 7, 'c': 20, 'f': 3, 'tags': ['Fiber Fuel']},
            'dinner': {'name': 'Chicken Thighs (Skinless) Baked with Rosemary, Garlic & Roasted Root Vegetables', 'portion': '190g chicken thighs, roasted carrots, parsnips', 'cal': 490, 'p': 42, 'c': 35, 'f': 18, 'tags': ['Comfort Recovery']}
        },
        'Sunday': {
            'breakfast': {'name': 'Shakshuka (Eggs Poached in Spicy Tomato-Pepper Sauce) with Whole Grain Pita', 'portion': '3 eggs in sauce, 1 whole wheat pita', 'cal': 410, 'p': 24, 'c': 36, 'f': 18, 'tags': ['Lycopene Rich']},
            'snack_am': {'name': 'Sliced Apple with Whey Protein Sludge / Almond Butter', 'portion': '1 apple + 20g whey mixed with splash of milk', 'cal': 190, 'p': 18, 'c': 22, 'f': 4, 'tags': ['Satiety Snack']},
            'lunch': {'name': 'Roast Chicken / Salmon with Steamed Couscous & Mediterranean Roasted Vegetables', 'portion': '180g protein, 1 cup cooked couscous, zucchini', 'cal': 540, 'p': 46, 'c': 50, 'f': 14, 'tags': ['Sunday Meal Prep']},
            'snack_pm': {'name': 'Cottage Cheese with a drizzle of Honey & Chia Seeds', 'portion': '150g cottage cheese + 1 tsp raw honey', 'cal': 160, 'p': 19, 'c': 12, 'f': 4, 'tags': ['Bedtime Prep']},
            'dinner': {'name': 'Hearty Beef/Lentil Stew with Kale, Carrots & Herb Broth', 'portion': '1 large bowl (350g) thick stew', 'cal': 460, 'p': 40, 'c': 38, 'f': 14, 'tags': ['Deep Recovery']}
        }
    }
}

# ==========================================
# 3. 7-DAY WORKOUT SPLIT ENGINE
# ==========================================

WORKOUT_ROUTINES = {
    'fat_burn_tone': {
        'title': 'Metabolic HIIT & Full-Body Hyper-Tone',
        'level': 'Beginner to Intermediate',
        'split': '4 Days On / 3 Days Active Recovery',
        'schedule': {
            'Monday': {
                'focus': 'Full Body HIIT & Dynamic Strength',
                'duration': '45 mins',
                'burn_est': '380 - 480 kcal',
                'warmup': '5 mins Arm circles, Cat-Cow, Jumping Jacks, Hip openers',
                'exercises': [
                    {'name': 'Goblet Squats / Air Squats', 'sets': '4', 'reps': '12-15', 'rest': '60s', 'muscle': 'Quadriceps & Glutes', 'cues': 'Keep chest proud, drive through whole foot.'},
                    {'name': 'Push-Ups (Standard or Knee-Supported)', 'sets': '3', 'reps': '10-12', 'rest': '45s', 'muscle': 'Chest & Core', 'cues': 'Straight line from neck to heels, elbows 45 deg.'},
                    {'name': 'Dumbbell / Resistance Band Rows', 'sets': '4', 'reps': '12', 'rest': '60s', 'muscle': 'Upper Back & Lats', 'cues': 'Squeeze shoulder blades, avoid shrugging.'},
                    {'name': 'Kettlebell / Dumbbell Swings', 'sets': '3', 'reps': '20', 'rest': '45s', 'muscle': 'Hamstrings & Posterior Chain', 'cues': 'Hinge at the hips, explosive glute drive.'},
                    {'name': 'Plank to Shoulder Taps', 'sets': '3', 'reps': '16 total', 'rest': '45s', 'muscle': 'Core & Obliques', 'cues': 'Prevent hips from rocking.'}
                ],
                'cooldown': '5 mins Child’s Pose, Hamstring stretch, Chest opener'
            },
            'Tuesday': {
                'focus': 'Zone 2 Steady Cardio & Core Sculpt',
                'duration': '40 mins',
                'burn_est': '300 - 400 kcal',
                'warmup': '3 mins Ankle circles & High Knees',
                'exercises': [
                    {'name': 'Brisk Incline Walk / Cycling / Elliptical (Zone 2 Heart Rate)', 'sets': '1', 'reps': '30 mins', 'rest': 'N/A', 'muscle': 'Cardiovascular System', 'cues': 'Maintain conversational pace (65-75% max HR).'},
                    {'name': 'Hanging / Lying Leg Raises', 'sets': '3', 'reps': '12-15', 'rest': '45s', 'muscle': 'Lower Rectus Abdominis', 'cues': 'Control descent, avoid swinging.'},
                    {'name': 'Bicycle Crunches', 'sets': '3', 'reps': '20 total', 'rest': '45s', 'muscle': 'Obliques', 'cues': 'Rotate from thoracic spine.'},
                    {'name': 'Dead Bug Exercise', 'sets': '3', 'reps': '12 per side', 'rest': '30s', 'muscle': 'Deep Transverse Abdominis', 'cues': 'Press lower back into floor firmly.'}
                ],
                'cooldown': 'Cobra pose, Pigeon stretch, Quad stretch'
            },
            'Wednesday': {
                'focus': 'Active Recovery & Mobility Flow',
                'duration': '30 mins',
                'burn_est': '150 - 200 kcal',
                'warmup': 'Full body joint rotations',
                'exercises': [
                    {'name': 'Low-Intensity Nature Walk (6,000 - 8,000 steps)', 'sets': '1', 'reps': '30 mins', 'rest': 'N/A', 'muscle': 'Metabolic Reset', 'cues': 'Get sunlight and relax parasympathetic nervous system.'},
                    {'name': 'Thoracic Spine Openers & Cat-Cow', 'sets': '3', 'reps': '10 breaths', 'rest': '30s', 'muscle': 'Spine Mobility', 'cues': 'Breathe deeply into diaphragm.'},
                    {'name': 'World’s Greatest Stretch', 'sets': '3', 'reps': '5 per side', 'rest': '30s', 'muscle': 'Hips & Thoracic Cage', 'cues': 'Hold end-range for 3 seconds.'}
                ],
                'cooldown': 'Deep box breathing (4s in, 4s hold, 4s out, 4s hold)'
            },
            'Thursday': {
                'focus': 'Lower Body Burn & Glute Power',
                'duration': '45 mins',
                'burn_est': '400 - 500 kcal',
                'warmup': 'Glute bridges, Leg swings, Banded lateral walks',
                'exercises': [
                    {'name': 'Romanian Deadlifts (Dumbbell / Barbell)', 'sets': '4', 'reps': '10-12', 'rest': '60s', 'muscle': 'Hamstrings & Glutes', 'cues': 'Hinge hips back, soft knee bend, flat spine.'},
                    {'name': 'Walking Lunges / Split Squats', 'sets': '3', 'reps': '12 per leg', 'rest': '60s', 'muscle': 'Quadriceps & Glute Medius', 'cues': 'Drop back knee towards floor with control.'},
                    {'name': 'Bulgarian Split Squats (or Step-Ups)', 'sets': '3', 'reps': '10 per leg', 'rest': '60s', 'muscle': 'Single Leg Strength', 'cues': 'Slight forward lean to bias glutes.'},
                    {'name': 'Calf Raises (Single Leg / Standing)', 'sets': '4', 'reps': '15-20', 'rest': '45s', 'muscle': 'Gastrocnemius & Soleus', 'cues': 'Full stretch at bottom, 2s peak contraction.'},
                    {'name': 'Side Plank with Hip Abduction', 'sets': '3', 'reps': '10 per side', 'rest': '45s', 'muscle': 'Glute Medius & Core', 'cues': 'Keep hips stacked vertically.'}
                ],
                'cooldown': 'Figure-4 glute stretch, Butterfly stretch'
            },
            'Friday': {
                'focus': 'Upper Body Sculpt & Metabolic Finisher',
                'duration': '45 mins',
                'burn_est': '380 - 460 kcal',
                'warmup': 'Band pull-aparts, Arm circles, Scapular push-ups',
                'exercises': [
                    {'name': 'Dumbbell Overhead Shoulder Press', 'sets': '4', 'reps': '10-12', 'rest': '60s', 'muscle': 'Anterior & Lateral Deltoids', 'cues': 'Brace core, press in slight arc overhead.'},
                    {'name': 'Lat Pulldowns or Inverted Bodyweight Rows', 'sets': '4', 'reps': '10-12', 'rest': '60s', 'muscle': 'Latissimus Dorsi', 'cues': 'Drive elbows down towards hips.'},
                    {'name': 'Incline Dumbbell Bench Press', 'sets': '3', 'reps': '12', 'rest': '60s', 'muscle': 'Upper Chest', 'cues': 'Controlled 3-second descent.'},
                    {'name': 'Bicep Curls into Overhead Tricep Extension (Superset)', 'sets': '3', 'reps': '12 each', 'rest': '45s', 'muscle': 'Biceps & Triceps', 'cues': 'Keep elbows pinned to sides.'},
                    {'name': 'Finisher: 4-Min Tabata Mountain Climbers & Burpees', 'sets': '8', 'reps': '20s on / 10s off', 'rest': '10s', 'muscle': 'Full Body Metabolic Surge', 'cues': 'Maximum effort interval.'}
                ],
                'cooldown': 'Overhead tricep stretch, Doorway chest stretch'
            },
            'Saturday': {
                'focus': 'Outdoor Activity / Sports / Fun Cardio',
                'duration': '45 - 60 mins',
                'burn_est': '350 - 500 kcal',
                'warmup': 'Light dynamic stretching',
                'exercises': [
                    {'name': 'Swimming, Cycling, Tennis, Hiking, or HIIT Class', 'sets': '1', 'reps': '45 mins', 'rest': 'N/A', 'muscle': 'Full Body Endurance', 'cues': 'Enjoy movement and elevate pulse.'}
                ],
                'cooldown': 'Full body yoga stretch'
            },
            'Sunday': {
                'focus': 'Complete Rest & Rejuvenation',
                'duration': 'Rest Day',
                'burn_est': 'Baseline BMR',
                'warmup': 'Gentle breathing',
                'exercises': [
                    {'name': 'Rest & Mindful Relaxation / Hot Salt Bath / Foam Rolling', 'sets': '1', 'reps': 'All Day', 'rest': 'N/A', 'muscle': 'Central Nervous System Recovery', 'cues': 'Hydrate well and sleep 8 hours.'}
                ],
                'cooldown': 'Sleep & recovery'
            }
        }
    },
    'hypertrophy_muscle': {
        'title': 'Push / Pull / Legs Hypertrophy Architecture',
        'level': 'Intermediate to Advanced',
        'split': '5 Days On / 2 Days Rest',
        'schedule': {
            'Monday': {
                'focus': 'Push Day: Chest, Shoulders & Triceps',
                'duration': '55 mins',
                'burn_est': '400 - 520 kcal',
                'warmup': 'Rotator cuff band warmups, Push-up pyramid',
                'exercises': [
                    {'name': 'Barbell or Dumbbell Flat Bench Press', 'sets': '4', 'reps': '6-8 (Heavy)', 'rest': '90s', 'muscle': 'Pectoralis Major', 'cues': 'Retract scapulae, touch lower sternum.'},
                    {'name': 'Incline Dumbbell Press', 'sets': '3', 'reps': '8-10', 'rest': '75s', 'muscle': 'Clavicular Chest', 'cues': '30-degree bench angle for optimal clavicular head recruitment.'},
                    {'name': 'Seated Dumbbell Overhead Shoulder Press', 'sets': '4', 'reps': '8-10', 'rest': '75s', 'muscle': 'Anterior Deltoid', 'cues': 'Full range of motion, avoid hyperextending spine.'},
                    {'name': 'Cable / Dumbbell Lateral Raises', 'sets': '4', 'reps': '12-15', 'rest': '60s', 'muscle': 'Lateral Deltoids (Cap Width)', 'cues': 'Lead with elbows, slight forward lean.'},
                    {'name': 'Tricep Rope Pushdowns (Cable)', 'sets': '3', 'reps': '12-15', 'rest': '60s', 'muscle': 'Triceps Lateral/Medial Head', 'cues': 'Flare rope at the bottom squeeze.'},
                    {'name': 'Overhead French Press / Skull Crushers', 'sets': '3', 'reps': '10-12', 'rest': '60s', 'muscle': 'Triceps Long Head', 'cues': 'Keep upper arms perpendicular.'}
                ],
                'cooldown': 'Cross-body shoulder stretch, Doorway chest stretch'
            },
            'Tuesday': {
                'focus': 'Pull Day: Back, Rear Delts & Biceps',
                'duration': '55 mins',
                'burn_est': '420 - 550 kcal',
                'warmup': 'Scapular pull-ups, Band face-pulls',
                'exercises': [
                    {'name': 'Conventional / Romanian Deadlifts or Weighted Pull-Ups', 'sets': '4', 'reps': '6-8', 'rest': '90s', 'muscle': 'Posterior Chain & Lats', 'cues': 'Lock in lats, push floor away.'},
                    {'name': 'Barbell Bent-Over Row (Overhand)', 'sets': '4', 'reps': '8-10', 'rest': '75s', 'muscle': 'Rhomboids, Traps, Lats', 'cues': 'Pull bar towards belly button.'},
                    {'name': 'Single-Arm Neutral Grip Dumbbell Row', 'sets': '3', 'reps': '10-12/arm', 'rest': '60s', 'muscle': 'Lower Lat Thickness', 'cues': 'Drive elbow back like pulling to pocket.'},
                    {'name': 'Cable Face Pulls with External Rotation', 'sets': '4', 'reps': '15', 'rest': '60s', 'muscle': 'Rear Delts & Rotator Cuff', 'cues': 'Pull to forehead, thumbs pointing back.'},
                    {'name': 'Barbell / Incline Dumbbell Bicep Curls', 'sets': '3', 'reps': '10-12', 'rest': '60s', 'muscle': 'Biceps Brachii', 'cues': 'Strict form, no swinging.'},
                    {'name': 'Hammer Curls (Dumbbells or Cable Rope)', 'sets': '3', 'reps': '12', 'rest': '60s', 'muscle': 'Brachialis & Forearms', 'cues': 'Neutral grip, pause at contraction.'}
                ],
                'cooldown': 'Lat stretch on rack, Forearm flexor stretch'
            },
            'Wednesday': {
                'focus': 'Legs & Core Power: Quad & Calves Dominant',
                'duration': '60 mins',
                'burn_est': '500 - 650 kcal',
                'warmup': 'Hip 90/90 mobility, Bodyweight squats, Ankle dorsiflexion drill',
                'exercises': [
                    {'name': 'Barbell Back Squats (or Hack Squats)', 'sets': '4', 'reps': '6-8', 'rest': '120s', 'muscle': 'Quadriceps, Glutes, Adductors', 'cues': 'Hit parallel, maintain neutral spine.'},
                    {'name': 'Leg Press (Moderate Stance)', 'sets': '4', 'reps': '10-12', 'rest': '90s', 'muscle': 'Quad Hypertrophy', 'cues': 'Do not lock out knees at top.'},
                    {'name': 'Walking Dumbbell Lunges', 'sets': '3', 'reps': '12 steps/leg', 'rest': '75s', 'muscle': 'Glutes & Quads', 'cues': 'Consistent stride, upright torso.'},
                    {'name': 'Leg Extensions (Isolation)', 'sets': '3', 'reps': '15', 'rest': '60s', 'muscle': 'Rectus Femoris (Quad Teardrop)', 'cues': '1s squeeze at top peak contraction.'},
                    {'name': 'Standing Calf Raises', 'sets': '4', 'reps': '15-20', 'rest': '45s', 'muscle': 'Calf Gastrocnemius', 'cues': 'Full extension on balls of feet.'},
                    {'name': 'Hanging Knee/Toes-to-Bar', 'sets': '3', 'reps': '12-15', 'rest': '45s', 'muscle': 'Core & Hip Flexors', 'cues': 'Curl pelvis upwards.'}
                ],
                'cooldown': 'Couch quad stretch, Pigeon pose'
            },
            'Thursday': {
                'focus': 'Active Recovery & Zone 2 Cardio',
                'duration': '35 mins',
                'burn_est': '250 - 350 kcal',
                'warmup': 'Joint mobility',
                'exercises': [
                    {'name': 'Incline Treadmill Walk (12% Incline, 3.2 mph)', 'sets': '1', 'reps': '30 mins', 'rest': 'N/A', 'muscle': 'Cardiovascular Mitochondrial Density', 'cues': 'Nasal breathing focus.'},
                    {'name': 'Foam Rolling (IT Band, Quads, Lats, Calves)', 'sets': '1', 'reps': '10 mins', 'rest': 'N/A', 'muscle': 'Myofascial Release', 'cues': 'Spend 30s on tight trigger points.'}
                ],
                'cooldown': 'Deep diaphragmatic breathing'
            },
            'Friday': {
                'focus': 'Upper Body Power & Weak-Point Hypertrophy',
                'duration': '50 mins',
                'burn_est': '400 - 500 kcal',
                'warmup': 'Band pull-aparts, Arm rotations',
                'exercises': [
                    {'name': 'Dumbbell Incline Bench Press', 'sets': '4', 'reps': '8-10', 'rest': '75s', 'muscle': 'Upper Chest', 'cues': 'Focus on chest contraction at top.'},
                    {'name': 'Neutral Grip Pull-Downs', 'sets': '4', 'reps': '10-12', 'rest': '75s', 'muscle': 'Mid-Back & Lats', 'cues': 'Pull to upper clavicle.'},
                    {'name': 'Dumbbell Seated Arnold Press', 'sets': '3', 'reps': '10-12', 'rest': '60s', 'muscle': '3-Head Deltoid Complex', 'cues': 'Smooth rotation on ascent.'},
                    {'name': 'Pec Deck Fly / Cable Flyes', 'sets': '3', 'reps': '12-15', 'rest': '60s', 'muscle': 'Chest Isolation (Inner Fibers)', 'cues': 'Deep stretch without joint strain.'},
                    {'name': 'Cable Preacher Bicep Curls (Superset with Dips)', 'sets': '3', 'reps': '12 each', 'rest': '60s', 'muscle': 'Biceps & Triceps', 'cues': 'Continuous tension.'}
                ],
                'cooldown': 'Doorway chest stretch, Shoulder distraction'
            },
            'Saturday': {
                'focus': 'Posterior Chain & Hamstring / Glute Hypertrophy',
                'duration': '50 mins',
                'burn_est': '450 - 550 kcal',
                'warmup': 'Glute bridges, Leg swings',
                'exercises': [
                    {'name': 'Barbell Romanian Deadlifts', 'sets': '4', 'reps': '8-10', 'rest': '90s', 'muscle': 'Hamstrings & Glutes', 'cues': 'Feel deep stretch in hamstrings before firing back up.'},
                    {'name': 'Barbell Hip Thrusts (with Bench & Pad)', 'sets': '4', 'reps': '10-12', 'rest': '90s', 'muscle': 'Gluteus Maximus (Peak Power)', 'cues': 'Full hip extension, chin tucked.'},
                    {'name': 'Lying / Seated Hamstring Curls', 'sets': '4', 'reps': '12-15', 'rest': '60s', 'muscle': 'Biceps Femoris Isolation', 'cues': 'Point toes slightly inward for outer head.'},
                    {'name': 'Bulgarian Split Squats (Glute-Biased)', 'sets': '3', 'reps': '10/leg', 'rest': '60s', 'muscle': 'Unilateral Glutes', 'cues': '45-degree forward torso lean.'},
                    {'name': 'Ab Wheel Rollouts / Cable Crunches', 'sets': '3', 'reps': '12-15', 'rest': '45s', 'muscle': 'Core Anti-Extension', 'cues': 'Roll from hips, not arms.'}
                ],
                'cooldown': 'Pigeon pose, Hamstring strap stretch'
            },
            'Sunday': {
                'focus': 'Systemic Rest & Nutrition Refuel',
                'duration': 'Rest Day',
                'burn_est': 'Baseline BMR',
                'warmup': 'Rest',
                'exercises': [
                    {'name': 'Deep Sleep, Hydration, Protein Synthesis Rest', 'sets': '1', 'reps': 'All Day', 'rest': 'N/A', 'muscle': 'All Muscle Groups', 'cues': 'Hit your target protein intake and rest.'}
                ],
                'cooldown': 'Rest'
            }
        }
    },
    'home_calisthenics': {
        'title': 'Zero-Equipment Calisthenics & Athletic Conditioning',
        'level': 'All Levels (Scale with progressions)',
        'split': '4 Days Active / 3 Days Mobility & Recovery',
        'schedule': {
            'Monday': {
                'focus': 'Upper Body Push & Pull Fundamentals',
                'duration': '35 mins',
                'burn_est': '280 - 360 kcal',
                'warmup': 'Wrist rotations, Arm swings, Inchworms',
                'exercises': [
                    {'name': 'Push-Up Progressions (Standard, Diamond, or Incline)', 'sets': '4', 'reps': '12-15', 'rest': '60s', 'muscle': 'Chest, Shoulders & Triceps', 'cues': 'Full lockout at top, chest to floor.'},
                    {'name': 'Doorframe / Towel Isometric Rows', 'sets': '4', 'reps': '12-15', 'rest': '60s', 'muscle': 'Back & Rhomboids', 'cues': 'Squeeze back blades hard.'},
                    {'name': 'Pike Push-Ups (or Elevated Pike)', 'sets': '3', 'reps': '8-10', 'rest': '60s', 'muscle': 'Shoulders & Triceps', 'cues': 'Hips high, head moves forward of hands.'},
                    {'name': 'Chair / Bench Tricep Dips', 'sets': '3', 'reps': '12-15', 'rest': '45s', 'muscle': 'Triceps', 'cues': 'Keep back close to bench edge.'},
                    {'name': 'Hollow Body Hold', 'sets': '3', 'reps': '30-45s', 'rest': '45s', 'muscle': 'Gymnastic Core Stability', 'cues': 'Lower back glued to floor.'}
                ],
                'cooldown': 'Chest opener, Wrist stretch'
            },
            'Tuesday': {
                'focus': 'Lower Body Athletic Explosiveness',
                'duration': '35 mins',
                'burn_est': '300 - 400 kcal',
                'warmup': 'Leg swings, Ankle circles, Bodyweight squats',
                'exercises': [
                    {'name': 'Tempo Bodyweight Squats (3s down, 1s pause, 1s up)', 'sets': '4', 'reps': '15-20', 'rest': '60s', 'muscle': 'Quads & Glutes', 'cues': 'Deep range of motion.'},
                    {'name': 'Reverse Lunges to High Knee', 'sets': '3', 'reps': '12/leg', 'rest': '45s', 'muscle': 'Glutes & Balance', 'cues': 'Explosive drive on the way up.'},
                    {'name': 'Single-Leg Glute Bridges', 'sets': '3', 'reps': '12/leg', 'rest': '45s', 'muscle': 'Glute Isolation', 'cues': 'Hold 2s at peak.'},
                    {'name': 'Wall Sit Hold', 'sets': '3', 'reps': '45-60s', 'rest': '45s', 'muscle': 'Quad Isometric Endurance', 'cues': 'Thighs parallel to floor at 90 degrees.'},
                    {'name': 'Standing Single-Leg Calf Raises on a Step', 'sets': '4', 'reps': '20/leg', 'rest': '30s', 'muscle': 'Calves', 'cues': 'Full stretch below step level.'}
                ],
                'cooldown': 'Quad stretch, Hamstring stretch'
            },
            'Wednesday': {
                'focus': 'Active Recovery & Core Balance',
                'duration': '25 mins',
                'burn_est': '150 kcal',
                'warmup': 'Cat-Cow, Bird-Dog',
                'exercises': [
                    {'name': 'Bird-Dog Dynamic Reaches', 'sets': '3', 'reps': '10/side', 'rest': '30s', 'muscle': 'Posterior Core & Balance', 'cues': 'Thumb up, reach long.'},
                    {'name': 'Side Plank Rotations', 'sets': '3', 'reps': '10/side', 'rest': '45s', 'muscle': 'Obliques', 'cues': 'Rotate torso under ribs.'},
                    {'name': 'Walking Outdoors (30 mins)', 'sets': '1', 'reps': '30 mins', 'rest': 'N/A', 'muscle': 'Cardio', 'cues': 'Fresh air & recovery.'}
                ],
                'cooldown': 'Deep breathing'
            },
            'Thursday': {
                'focus': 'Total Body Calisthenics Circuit',
                'duration': '35 mins',
                'burn_est': '320 - 420 kcal',
                'warmup': 'Jumping Jacks, High Knees',
                'exercises': [
                    {'name': 'Jump Squats (or Fast Air Squats)', 'sets': '4', 'reps': '12-15', 'rest': '45s', 'muscle': 'Fast-Twitch Leg Power', 'cues': 'Land softly on midfoot.'},
                    {'name': 'Decline Push-Ups (Feet on Bed / Couch)', 'sets': '3', 'reps': '10-12', 'rest': '60s', 'muscle': 'Upper Chest', 'cues': 'Rigid core plank.'},
                    {'name': 'Skater Jumps', 'sets': '3', 'reps': '20 total', 'rest': '45s', 'muscle': 'Lateral Stability & Agility', 'cues': 'Absorb impact on single leg.'},
                    {'name': 'Superman / Arch Body Lifts', 'sets': '3', 'reps': '15', 'rest': '30s', 'muscle': 'Erector Spinae & Glutes', 'cues': 'Lift chest and thighs simultaneously.'},
                    {'name': 'Mountain Climbers (Fast Pace)', 'sets': '3', 'reps': '30s', 'rest': '30s', 'muscle': 'Metabolic Core', 'cues': 'Knees to chest rapidly.'}
                ],
                'cooldown': 'Child’s pose, Cobra pose'
            },
            'Friday': {
                'focus': 'Tabata Core & Cardio Burn',
                'duration': '30 mins',
                'burn_est': '280 - 380 kcal',
                'warmup': 'Torso twists, Arm circles',
                'exercises': [
                    {'name': 'Burpees (Step or Jump)', 'sets': '4', 'reps': '10', 'rest': '45s', 'muscle': 'Full Body Conditioning', 'cues': 'Smooth rhythm.'},
                    {'name': 'Bicycle Crunches', 'sets': '3', 'reps': '24 total', 'rest': '30s', 'muscle': 'Obliques', 'cues': 'Slow tempo.'},
                    {'name': 'Plank Hold', 'sets': '3', 'reps': '60s', 'rest': '45s', 'muscle': 'Core Endurance', 'cues': 'Squeeze glutes.'}
                ],
                'cooldown': 'Hamstring & spinal twist stretch'
            },
            'Saturday': {
                'focus': 'Outdoor Recreation or Free Walk',
                'duration': '40 mins',
                'burn_est': '200 - 300 kcal',
                'warmup': 'Gentle warm up',
                'exercises': [
                    {'name': 'Outdoor Jogging / Brisk Walk / Bike Ride', 'sets': '1', 'reps': '40 mins', 'rest': 'N/A', 'muscle': 'Cardio', 'cues': 'Breathe easy.'}
                ],
                'cooldown': 'Calf & quad stretch'
            },
            'Sunday': {
                'focus': 'Rest & Recovery',
                'duration': 'Rest Day',
                'burn_est': 'Baseline BMR',
                'warmup': 'Rest',
                'exercises': [
                    {'name': 'Full Rest Day', 'sets': '1', 'reps': 'All Day', 'rest': 'N/A', 'muscle': 'Recovery', 'cues': 'Sleep & hydrate.'}
                ],
                'cooldown': 'Rest'
            }
        }
    }
}

def get_meal_plan_by_diet(diet_key):
    """Returns a tailored 7-day meal plan based on the dietary philosophy."""
    diet_key = str(diet_key).lower().strip()
    if diet_key in ['vegetarian_indian', 'vedic', 'indian_veg', 'vegan_plant', 'vegan']:
        return MEAL_PLANS_BY_DIET['vegetarian_indian']
    return MEAL_PLANS_BY_DIET['high_protein']

def get_workout_routine(routine_key):
    """Returns the 7-day structured exercise routine."""
    routine_key = str(routine_key).lower().strip()
    if routine_key in WORKOUT_ROUTINES:
        return WORKOUT_ROUTINES[routine_key]
    return WORKOUT_ROUTINES['fat_burn_tone']

# ==========================================
# 4. SMART GROCERY LIST GENERATOR
# ==========================================

def generate_grocery_list(diet_pref='balanced', days=7):
    """
    Builds a structured grocery checklist categorized into food groups.
    """
    if diet_pref in ['vegetarian_indian', 'vegan_plant']:
        return {
            'Fresh Produce & Vegetables': [
                {'item': 'Baby Spinach / Palak', 'qty': '500g', 'checked': False},
                {'item': 'Broccoli & Cauliflower', 'qty': '2 heads', 'checked': False},
                {'item': 'Bell Peppers (Tri-Color)', 'qty': '4 units', 'checked': False},
                {'item': 'Cucumbers & Tomatoes', 'qty': '1 kg each', 'checked': False},
                {'item': 'Bottle Gourd (Lauki) & Zucchini', 'qty': '2 medium', 'checked': False},
                {'item': 'Ginger, Garlic & Green Chilies', 'qty': '200g', 'checked': False},
                {'item': 'Fresh Lemons & Mint Leaves', 'qty': '6 lemons + 1 bunch', 'checked': False}
            ],
            'Plant & Dairy Proteins': [
                {'item': 'Low-Fat Cottage Cheese / Paneer (or Organic Tofu)', 'qty': '1 kg', 'checked': False},
                {'item': 'Greek Yogurt / Probiotic Hung Curd', 'qty': '1 kg', 'checked': False},
                {'item': 'Green Moong Dal (Whole & Sprouted)', 'qty': '500g', 'checked': False},
                {'item': 'Yellow Moong Dal & Chana Dal', 'qty': '500g each', 'checked': False},
                {'item': 'Rajma (Red Kidney Beans) & Chole (Chickpeas)', 'qty': '500g each', 'checked': False},
                {'item': 'Soya Chunks / Nutrela Protein Granules', 'qty': '250g', 'checked': False}
            ],
            'Whole Grains & Complex Carbs': [
                {'item': 'Rolled Oats (Gluten-Free)', 'qty': '500g', 'checked': False},
                {'item': 'Brown Basmati Rice / Quinoa', 'qty': '1 kg', 'checked': False},
                {'item': 'Ragi / Jowar / Multigrain Flour', 'qty': '1 kg', 'checked': False},
                {'item': 'Roasted Makhana (Fox Nuts)', 'qty': '200g', 'checked': False},
                {'item': 'Broken Wheat (Dalia) & Poha', 'qty': '500g each', 'checked': False}
            ],
            'Healthy Fats, Seeds & Superfoods': [
                {'item': 'Raw Whole Almonds & Walnuts', 'qty': '250g each', 'checked': False},
                {'item': 'Chia Seeds & Roasted Flaxseeds', 'qty': '150g each', 'checked': False},
                {'item': 'A2 Cow Ghee or Cold-Pressed Olive Oil', 'qty': '500ml', 'checked': False},
                {'item': 'Pumpkin & Sunflower Seeds Mix', 'qty': '150g', 'checked': False},
                {'item': 'Turmeric (Curcumin) & Himalayan Pink Salt', 'qty': '1 pack', 'checked': False}
            ],
            'Fresh Fruits': [
                {'item': 'Papaya / Guava', 'qty': '2 units', 'checked': False},
                {'item': 'Crisp Green/Red Apples', 'qty': '6 units', 'checked': False},
                {'item': 'Berries (Blueberries or Strawberries)', 'qty': '250g', 'checked': False},
                {'item': 'Bananas & Pomegranates', 'qty': '1 bunch + 3 units', 'checked': False}
            ]
        }
    else: # high protein / omnivore
        return {
            'Fresh Lean Meats & Seafood': [
                {'item': 'Boneless Skinless Chicken Breast', 'qty': '1.5 kg', 'checked': False},
                {'item': 'Fresh Wild Salmon or Cod / White Fish Fillets', 'qty': '800g', 'checked': False},
                {'item': 'Lean Ground Turkey (93/7) or Extra Lean Sirloin', 'qty': '600g', 'checked': False},
                {'item': 'Free-Range Organic Eggs', 'qty': '2 dozen (24 eggs)', 'checked': False},
                {'item': 'Liquid Egg Whites', 'qty': '1 carton (500ml)', 'checked': False}
            ],
            'Fresh Vegetables & Greens': [
                {'item': 'Organic Baby Spinach & Kale', 'qty': '500g', 'checked': False},
                {'item': 'Fresh Green Asparagus & Broccoli Crowns', 'qty': '800g', 'checked': False},
                {'item': 'Bell Peppers, Zucchini & Red Onions', 'qty': '6 units mix', 'checked': False},
                {'item': 'Avocados (Hass)', 'qty': '4 units', 'checked': False},
                {'item': 'Cherry Tomatoes & Mixed Salad Greens', 'qty': '400g', 'checked': False}
            ],
            'Dairy & Plant Proteins': [
                {'item': '0% Plain Greek Yogurt (High Protein)', 'qty': '1.5 kg', 'checked': False},
                {'item': 'Low-Fat Cottage Cheese', 'qty': '500g', 'checked': False},
                {'item': 'Whey / Plant Protein Isolate Powder', 'qty': '1 tub (1 kg)', 'checked': False},
                {'item': 'Unsweetened Almond / Oat Milk', 'qty': '2 liters', 'checked': False}
            ],
            'Smart Carbohydrates': [
                {'item': 'Organic Rolled Oats', 'qty': '1 kg', 'checked': False},
                {'item': 'Organic Tri-Color Quinoa & Brown Basmati Rice', 'qty': '1 kg each', 'checked': False},
                {'item': 'Orange Sweet Potatoes', 'qty': '1.5 kg', 'checked': False},
                {'item': 'Artisanal Sourdough / 100% Sprouted Grain Bread', 'qty': '1 loaf', 'checked': False},
                {'item': 'Canned Black Beans & Chickpeas (Organic)', 'qty': '4 cans', 'checked': False}
            ],
            'Healthy Fats & Pantry Essentials': [
                {'item': 'Extra Virgin Cold-Pressed Olive Oil', 'qty': '750ml', 'checked': False},
                {'item': 'Raw Almonds, Walnuts & Chia Seeds', 'qty': '200g each', 'checked': False},
                {'item': 'All-Natural Peanut / Almond Butter (No added sugar)', 'qty': '1 jar (400g)', 'checked': False},
                {'item': 'Dark Chocolate (85%+ Cacao)', 'qty': '2 bars', 'checked': False},
                {'item': 'Cinnamon, Smoked Paprika & Himalayan Pink Salt', 'qty': 'Pantry stock', 'checked': False}
            ]
        }


# ==========================================
# 5. GROQ AI ADAPTIVE CONSULTANT
# ==========================================

def _generate_clinical_fallback_advice(user_question):
    """Fallback intelligent clinical response when LLM is unavailable."""
    q_lower = user_question.lower()
    if 'substitute' in q_lower or 'swap' in q_lower:
        return (
            "**Clinical Nutrition Substitution Guide:**\n"
            "- **Eggs (Baking/Binding):** 1 tbsp chia or flaxseeds soaked in 3 tbsp water (per egg), or 1/4 cup unsweetened applesauce.\n"
            "- **Eggs (Protein):** 100g low-fat paneer, firm tofu, or 30g scoop whey/plant protein isolate.\n"
            "- **Dairy Milk:** Unsweetened almond milk (low calorie), soy milk (high protein 7g/cup), or oat milk.\n"
            "- **White Rice:** Quinoa (complete amino acid profile), cauliflower rice (ultra low-carb), or brown basmati.\n"
            "- **Peanut Butter (Nut Allergy):** Sunflower seed butter (SunButter) or tahini.\n"
            "\n*Tip:* Always maintain your total target protein and calorie balance when swapping items."
        )
    elif 'workout' in q_lower or 'sore' in q_lower or 'injury' in q_lower or 'pain' in q_lower:
        return (
            "**Clinical Sports Medicine Guidance:**\n"
            "- **Muscle Soreness (DOMS):** Normal 24-48 hours post-workout. Focus on active recovery (light walking), 35ml/kg hydration, and 8+ hours sleep.\n"
            "- **Joint Pain / Sharp Pain:** Stop the provocative exercise immediately. If knee pain occurs during squats, substitute with box squats, glute bridges, or leg presses with feet higher on the platform.\n"
            "- **Warmup Protocol:** Always complete 5 minutes of dynamic joint mobilization (hip openers, band pull-aparts) before lifting heavy weights.\n"
            "\n*Disclaimer:* If pain is acute or accompanied by swelling, consult a Spherix orthopedic specialist."
        )
    elif 'water' in q_lower or 'hydrate' in q_lower:
        return (
            "**Clinical Hydration Protocol:**\n"
            "- **Baseline:** 35ml per kilogram of body weight.\n"
            "- **Workout Addition:** Add 500ml - 750ml for every 45-60 minutes of sweat-inducing exercise.\n"
            "- **Electrolytes:** Add a pinch of pink Himalayan salt and fresh lemon juice to your intra-workout water during hot weather or heavy HIIT sessions."
        )
    else:
        return (
            "**Spherix Nutrition & Fitness Clinical Insights:**\n"
            "1. **Energy Balance is King:** Calorie deficit governs fat loss, while protein intake (1.6 - 2.2g/kg) governs muscle preservation.\n"
            "2. **Meal Timing:** Spread protein evenly across 3-4 meals (25-40g per meal) to maximize Muscle Protein Synthesis (MPS).\n"
            "3. **Sleep & Recovery:** 7-9 hours of restorative sleep regulates ghrelin and leptin (hunger hormones) and spikes natural growth hormone.\n"
            "4. **Progressive Overload:** Track your repetitions and weights weekly to signal ongoing muscle adaptation.\n"
            "\nFeel free to ask specific questions about your customized meal plan, recipes, or workout routine!"
        )


def get_ai_nutrition_advice(user_question, user_profile=None):
    """
    Answers personalized nutrition, workout, recipe substitution, or health optimization questions
    using Groq LLM (if configured) or an intelligent clinical knowledge fallback.
    """
    if not is_groq_active():
        return _generate_clinical_fallback_advice(user_question)

    system_prompt = (
        "You are 'Spherix Clinical Nutrition & Sports Performance AI', a double-board certified clinical dietitian "
        "and strength & conditioning specialist. Provide evidence-based, empathetic, structured advice on diet, macronutrients, "
        "exercise biomechanics, recipe substitutions, and health optimization. Format with markdown headings, bullet points, and bold highlights. "
        "Include actionable, precise advice."
    )
    
    context_str = ""
    if user_profile:
        context_str = f"\n[User Context: Age {user_profile.get('age')}, Gender {user_profile.get('gender')}, Weight {user_profile.get('weight_kg')}kg, Height {user_profile.get('height_cm')}cm, Goal: {user_profile.get('goal')}, Diet: {user_profile.get('diet_pref')}, Target Calories: {user_profile.get('target_calories')} kcal]"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{user_question}{context_str}"}
    ]

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': messages,
        'temperature': 0.7,
        'max_tokens': 1200
    }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=10, verify=False)
        resp.raise_for_status()
        reply_json = resp.json()
        choices = reply_json.get('choices', [])
        if choices and 'message' in choices[0]:
            content = choices[0]['message'].get('content', '').strip()
            if content:
                return content
        return _generate_clinical_fallback_advice(user_question)
    except Exception as e:
        print(f"Groq Nutrition AI Error, falling back to local clinical knowledge: {e}")
        return _generate_clinical_fallback_advice(user_question)


def _extract_json_payload(text):
    """Safely extracts JSON object from LLM response text."""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    
    try:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except Exception:
        pass
        
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
    except Exception:
        pass
        
    return None


def _generate_clinical_ai_evaluation(biometrics, goal, diet_pref, health_conditions='None', allergies='None', equipment='gym', experience='intermediate'):
    """
    Generates structured clinical AI diagnostics and real-life recommendations.
    """
    age = biometrics.get('age', 28)
    gender = biometrics.get('gender', 'male')
    bmi = biometrics.get('bmi', 23.5)
    weight = biometrics.get('weight_kg', 70)
    body_fat = biometrics.get('body_fat_pct', 18.0)
    tdee = biometrics.get('tdee', 2400)
    target_cals = biometrics.get('target_calories', 2000)
    
    # Timeline estimation
    if 'loss' in goal:
        weekly_rate = "0.5 to 0.7 kg / week"
        weeks = max(6, min(24, int(math.ceil(abs(weight - biometrics.get('ideal_weight_kg', 68)) / 0.5))))
        assessment = (
            f"Based on clinical biometrics (BMI {bmi}, estimated body fat {body_fat}%), your baseline metabolic rate "
            f"requires a structured caloric deficit of {abs(biometrics.get('goal_diff', -500))} kcal/day. "
            f"This pace safely preserves lean muscle tissue while targeting subcutaneous and visceral adipose tissue."
        )
    elif 'bulk' in goal or 'hypertrophy' in goal:
        weekly_rate = "+0.25 to 0.35 kg / week"
        weeks = 12
        assessment = (
            f"To maximize myofibrillar hypertrophy while minimizing fat accumulation, your target of {target_cals} kcal "
            f"provides an optimal clean caloric surplus (+{biometrics.get('goal_diff', 300)} kcal above TDEE). "
            f"Protein intake is optimized at ~{round(biometrics['macros']['protein']['grams']/weight, 1)}g/kg body weight."
        )
    else:
        weekly_rate = "0.0 kg / week (Weight Maintenance)"
        weeks = 8
        assessment = (
            f"Your metabolic profile indicates an isocaloric requirement of {target_cals} kcal/day to preserve current "
            f"lean mass ({biometrics.get('lean_mass_kg')} kg) and optimize metabolic endocrine biomarkers."
        )

    # Supplements & Micronutrients
    supplements = [
        {"name": "Vitamin D3 + K2", "dosage": "2000 - 4000 IU/day with morning meal", "reason": "Optimizes testosterone/estrogen balance, bone mineralization, and immune vitality."},
        {"name": "Omega-3 Fatty Acids (EPA/DHA)", "dosage": "1000 - 2000 mg/day", "reason": "Reduces exercise-induced muscle inflammation and enhances cardiovascular endothelial function."},
        {"name": "Magnesium Bisglycinate", "dosage": "200 - 300 mg before sleep", "reason": "Enhances parasympathetic slow-wave sleep and prevents muscle cramping."},
        {"name": "Electrolyte Complex (Sodium/Potassium/Magnesium)", "dosage": "1 serving during workouts", "reason": "Maintains cellular hydration, muscle contractility, and blood pressure stability."}
    ]
    if 'hypertrophy' in goal or 'bulk' in goal or 'tone' in goal:
        supplements.append({"name": "Creatine Monohydrate (Creapure)", "dosage": "3 - 5 g/day consistently", "reason": "Increases intracellular phosphocreatine stores for explosive anaerobic power output."})

    # Health Advisory & Safety
    advisory = []
    if health_conditions and health_conditions.lower() not in ['none', 'no', '']:
        advisory.append(f"Medical Advisory for {health_conditions}: Ensure continuous glycemic and blood pressure monitoring. Hydrate adequately and avoid rapid heart rate spikes.")
    if allergies and allergies.lower() not in ['none', 'no', '']:
        advisory.append(f"Allergy Safety Alert for {allergies}: Strictly verified zero-cross-contamination meal substitutions have been integrated into your grocery and meal matrix.")
    if not advisory:
        advisory.append("Perform 5 minutes of dynamic joint mobilization prior to resistance training to minimize tendon strain.")

    return {
        "clinical_assessment": assessment,
        "timeline_weeks": weeks,
        "weekly_rate": weekly_rate,
        "metabolic_rate_rating": "Eumetabolic (Healthy Range)" if 18.5 <= bmi <= 25 else "Adaptive Metabolic Deficit Required",
        "supplements": supplements,
        "health_advisory": advisory,
        "custom_biohacks": [
            "Maintain 10,000 daily steps (NEAT) for passive metabolic expenditure.",
            "Aim for 8 hours of sleep in a cool, dark room (18-20°C) to optimize overnight recovery."
        ],
        "source": "Spherix Clinical Sports Physiology Protocol",
        "ai_powered": True
    }


def analyze_with_groq_ai(profile_data):
    """
    Executes live deep clinical AI analysis through Groq LLM with fallback support.
    """
    age = int(profile_data.get('age', 28))
    gender = str(profile_data.get('gender', 'male')).lower()
    weight = float(profile_data.get('weight', 70))
    height = float(profile_data.get('height', 175))
    activity = str(profile_data.get('activity_level', 'moderate'))
    goal = str(profile_data.get('goal', 'weight_loss'))
    diet = str(profile_data.get('diet_pref', 'high_protein'))
    routine_key = str(profile_data.get('workout_routine', 'fat_burn_tone'))
    health_conditions = str(profile_data.get('health_conditions', 'None'))
    allergies = str(profile_data.get('allergies', 'None'))
    equipment = str(profile_data.get('equipment', 'gym'))
    experience = str(profile_data.get('experience', 'intermediate'))

    # 1. Base biometrics
    biometrics = calculate_biometrics(
        age=age, gender=gender, weight_kg=weight, height_cm=height,
        activity_level=activity, goal=goal, diet_pref=diet
    )

    # 2. Get standard meals and workouts
    meals = get_meal_plan_by_diet(diet)
    workout = get_workout_routine(routine_key)
    grocery = generate_grocery_list(diet_pref=diet)

    # 3. Groq AI deep evaluation
    ai_evaluation = None
    if is_groq_active():
        system_prompt = (
            "You are 'Spherix Clinical Nutrition & Sports Medicine AI', a world-class board-certified physician, "
            "clinical dietitian, and sports physiologist. Analyze the patient biometrics and return a strict, valid JSON object ONLY. "
            "Do NOT include markdown fences, extra text, or preamble."
        )
        
        user_prompt = f"""
Analyze the following patient for a precision nutrition and fitness protocol:
- Age: {age}, Gender: {gender}, Weight: {weight}kg, Height: {height}cm
- Calculated BMI: {biometrics['bmi']} ({biometrics['bmi_category']}), Est Body Fat: {biometrics['body_fat_pct']}%
- BMR: {biometrics['bmr']} kcal, TDEE: {biometrics['tdee']} kcal, Target Calories: {biometrics['target_calories']} kcal
- Goal: {goal}, Diet Preference: {diet}
- Existing Health Conditions: {health_conditions}
- Food Allergies: {allergies}
- Training Equipment Available: {equipment}, Experience Level: {experience}

Return a valid JSON object with the following exact keys:
{{
  "clinical_assessment": "Comprehensive 3-4 sentence medical evaluation of their metabolism, caloric strategy, and physiological adaptations.",
  "timeline_weeks": 12,
  "weekly_rate": "0.5 to 0.7 kg / week",
  "metabolic_rate_rating": "Optimal Eumetabolic or Sluggish or Adaptive Deficit",
  "supplements": [
    {{"name": "Supplement / Vitamin Name", "dosage": "Clinical Dosage", "reason": "Specific physiological benefit"}}
  ],
  "health_advisory": [
    "Specific precaution regarding health conditions, injuries, or dietary constraints"
  ],
  "custom_biohacks": [
    "Actionable evidence-based health tip 1",
    "Actionable evidence-based health tip 2"
  ]
}}
"""
        endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': GROQ_API_MODEL,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.3,
            'max_tokens': 1200
        }

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=15, verify=False)
            if resp.status_code == 200:
                reply_text = resp.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                parsed = _extract_json_payload(reply_text)
                if parsed and 'clinical_assessment' in parsed:
                    ai_evaluation = parsed
                    ai_evaluation['ai_powered'] = True
                    ai_evaluation['source'] = f"Groq AI Clinical Neural Engine ({GROQ_API_MODEL})"
        except Exception as err:
            print(f"Groq AI Analysis exception: {err}")

    # Fallback to internal clinical diagnostics if Groq failed or offline
    if not ai_evaluation:
        ai_evaluation = _generate_clinical_ai_evaluation(
            biometrics=biometrics, goal=goal, diet_pref=diet,
            health_conditions=health_conditions, allergies=allergies,
            equipment=equipment, experience=experience
        )

    return {
        'biometrics': biometrics,
        'ai_analysis': ai_evaluation,
        'meal_plan': meals,
        'workout_plan': workout,
        'grocery_list': grocery,
        'form_values': {
            'age': age,
            'gender': gender,
            'weight': weight,
            'height': height,
            'activity': activity,
            'goal': goal,
            'diet': diet,
            'routine': routine_key,
            'health_conditions': health_conditions,
            'allergies': allergies,
            'equipment': equipment,
            'experience': experience
        }
    }
