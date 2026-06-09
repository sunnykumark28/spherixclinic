import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import joblib

try:
    # Read the training data from the CSV file
    df = pd.read_csv('symptoms_dataset.csv')
    print("✅ Successfully loaded 'symptoms_dataset.csv'.")
except FileNotFoundError:
    print("❌ Error: 'symptoms_dataset.csv' not found. Please create it and add training data.")
    exit() # Exit the script if the data file is not found

# Create and train the model pipeline
model_pipeline = Pipeline([('vectorizer', TfidfVectorizer()), ('classifier', MultinomialNB())])

# Use the 'symptoms' and 'condition' columns from the CSV data
model_pipeline.fit(df['symptoms'], df['condition'])

# Save the trained model to a file
joblib.dump(model_pipeline, 'symptom_classifier.pkl')
print("✅ Model trained and saved as symptom_classifier.pkl")