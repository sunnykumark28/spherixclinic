# Spherix Clinic Health Platform (Flask)

## Overview
A comprehensive Flask web application that serves as a multi-functional health platform. The project demonstrates a wide range of features from AI-powered diagnostics to a full e-commerce flow for a medical shop.

### Key Features:
- **AI-Powered Tools**:
  - **Symptom Checker**: Analyzes user-described symptoms using Groq API to suggest possible conditions and relevant medical departments.
    - 📷 **Image Analysis**: Optional Google Vision API integration for visual symptom analysis (rashes, injuries, etc.)
    - 💬 **Text Analysis**: Comprehensive text-based symptom description with body part selection
  - **Drug & Condition Info**: Provides AI-generated, easy-to-understand descriptions for a vast list of drugs and medical conditions.
- **Dual User Portals**:
  - **Patient Portal**: Secure registration and login, a personal dashboard to manage appointments and view order history, and the ability to book/cancel appointments.
  - **Doctor Portal**: Secure registration and login, with a dashboard for doctors to manage their professional profiles and view their schedule.
- **E-commerce Medical Shop**:
  - Browse and search a catalog of medical products.
  - Fully functional shopping cart.
  - Checkout process for logged-in patients, creating orders with shipping details.
  - Order history dashboard with the ability to view order details and print PDF invoices.
- **Core Platform Features**:
  - Search for doctors by name or specialty.
  - Detailed doctor profile pages.
  - Robust appointment booking system.
  - Rich informational pages for research, legal policies, and company info.

## Quick start
1. Create and activate the virtual environment:
   ```bash
   # First, create the environment (only needs to be done once)
   python3 -m venv venv

   # Then, activate it (needs to be done for every new terminal session)
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. **(Required)** Copy `.env.example` to `.env` and set your `GROQ_API_KEY` for symptom analysis.
4. **(Optional)** For image analysis feature, add `GOOGLE_VISION_API_KEY` to `.env`:
   ```bash
   GOOGLE_VISION_API_KEY=your-google-vision-api-key
   ENABLE_IMAGE_ANALYSIS=true
   ```
5. Run the app:
   ```bash
   python app.py
   ```
6. Open http://127.0.0.1:5000

## Notes
- This project uses the Groq API for its AI features.
- **Image Analysis**: The Symptom Checker includes optional image analysis via Google Vision API:
  - Detects visual symptoms (rashes, injuries, skin conditions, etc.)
  - Extracts text from images (medical documents, prescriptions)
  - Identifies visible objects and patterns
  - Integrates findings with Groq AI for comprehensive analysis
  - Requires a valid Google Vision API key (optional but recommended)
- The application uses an in-memory data store (Python dictionaries) for demonstration purposes, so all data (users, orders, etc.) will be reset when the server restarts.
- The UI is built with Tailwind CSS, included via a CDN in the main layout file.# spherixclinic-plus
# spherixclinic-plus
