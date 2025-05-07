# GAF Contractor Data Scraper and Analyzer

This project scrapes contractor data from GAF's website, stores it locally, and generates AI-powered insights about each contractor.

## Features

- Web scraping of GAF contractor profiles using Playwright
- Data storage in JSON format
- AI-powered insights generation using OpenAI's API
- Web interface to view and refresh data
- Queue-based processing system for handling multiple requests

## Prerequisites

- Python 3.x
- OpenAI API key
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Project Structure

- `server.py`: Main Flask application and queue processing
- `scraper.py`: GAF contractor data scraping implementation
- `generate_insights.py`: AI insights generation using OpenAI
- `cache_manager.py`: Manages data caching and updates
- `data/`: Directory for storing scraped data and cache
- `templates/`: HTML templates for the web interface

## Usage

1. Start the server:
```bash
python3 server.py
```

2. Access the web interface at `http://localhost:5001`

3. The system will automatically:
   - Create necessary directories
   - Scrape contractor data if none exists
   - Generate AI insights for each contractor
   - Display the data in a web interface

## Data Collection

The scraper collects the following information for each contractor:
- Basic Information:
  - Name
  - Location
  - Phone number
  - Rating
- Detailed Information:
  - About section
  - Reviews
  - Years in business
  - State license
  - Number of employees
  - Last modified date

## AI Insights

The system uses OpenAI's API to generate insights about each contractor based on their:
- Years in business
- Location
- Customer reviews
- Company information

## Queue System

The application implements a queue-based system to handle:
- Initial data scraping
- Data refresh requests
- Multiple concurrent users

## Notes

- The server runs on port 5001 by default (to avoid conflicts with AirPlay on macOS)
- Data is stored in `data/contractors.json`
- Cache information is stored in `data/cache.json`

## Error Handling

The system includes comprehensive error handling for:
- Network issues
- Scraping failures
- API errors
- Data processing errors
