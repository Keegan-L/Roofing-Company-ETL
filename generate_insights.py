import json
import openai
import os
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_contractor_data():
    """Load the contractor data from the JSON file"""
    data_file = Path("data/contractors.json")
    if not data_file.exists():
        logger.error("No contractor data file found")
        return None
    
    with open(data_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_insight(contractor):
    """Generate an AI insight for a contractor using OpenAI API"""
    # Prepare the prompt with relevant information
    prompt = f"""Please provide a 2-3 sentence summary about this roofing contractor based on their information and customer reviews:

Company Name: {contractor['name']}
Location: {contractor['location']}
Founded: {contractor.get('founding_year', 'Not specified')}
Number of Employees: {contractor.get('number_of_employees', 'Not specified')}
Rating: {contractor.get('rating', 'Not specified')}
State License: {contractor.get('state_license', 'Not specified')}

Customer Reviews:
{chr(10).join(contractor.get('reviews', []))}

Please focus on summarizing the company's experience, reliability, and what customers appreciate about their service."""

    try:
        # Call OpenAI API
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes business information and customer feedback."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0
        )
        
        # Extract the generated insight
        insight = response.choices[0].message.content.strip()
        return insight
    
    except Exception as e:
        logger.error(f"Error generating insight: {str(e)}")
        return None

def save_updated_data(data):
    """Save the updated data back to the JSON file"""
    output_file = Path("data/contractors.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Updated data saved to {output_file}")

def generate_insights():
    """Generate insights for all contractors and save the updated data"""
    # Check for OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("Please create a .env file with your OPENAI_API_KEY")
        return
    
    # Set the API key
    openai.api_key = api_key
    
    # Load the contractor data
    contractors = load_contractor_data()
    if not contractors:
        return
    
    # Process each contractor
    for contractor in contractors:
        logger.info(f"Generating insight for {contractor['name']}...")
        insight = generate_insight(contractor)
        if insight:
            contractor['ai_insight'] = insight
            logger.info(f"Generated insight: {insight}")
        else:
            contractor['ai_insight'] = None
            logger.warning(f"Failed to generate insight for {contractor['name']}")
    
    # Save the updated data
    save_updated_data(contractors)
    logger.info("Finished processing all contractors")

def main():
    generate_insights()

if __name__ == "__main__":
    main() 