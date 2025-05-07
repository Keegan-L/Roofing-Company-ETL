from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from queue import Queue
from scraper import GAFContractorScraper
from generate_insights import generate_insights
from pathlib import Path
import logging
import sys

# Set up logging to show in console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

logger.info("Starting server initialization...")

app = Flask(__name__)
CORS(app)

# Global queue to store requests
request_queue = Queue()
is_processing = False
current_position = 0

# Ensure data directory exists
data_dir = Path('data')
data_dir.mkdir(exist_ok=True)
logger.info("Ensured data directory exists")

def check_and_initialize_data():
    """Check if data exists and initialize if needed"""
    data_file = Path('data/contractors.json')
    logger.info(f"Checking for data file at: {data_file.absolute()}")
    if not data_file.exists() or data_file.stat().st_size == 0:
        logger.info("No data found, initializing scraping...")
        # Add the refresh request to the queue
        request_queue.put({
            'timestamp': time.time(),
            'type': 'refresh'
        })
        logger.info("Added refresh request to queue")
        
        # Wait for scraping to complete
        last_wait_message = 0
        while not request_queue.empty() or is_processing:
            current_time = time.time()
            # Only show waiting message every 5 seconds
            if current_time - last_wait_message >= 5:
                logger.info("Scraping in progress... (this may take a few minutes)")
                last_wait_message = current_time
            time.sleep(1)
            
        # Generate insights after scraping
        logger.info("Scraping completed, generating insights...")
        generate_insights()
        return True
    logger.info("Data file exists, no initialization needed")
    return False

def load_contractors():
    try:
        with open('data/contractors.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading contractors: {e}")
        return []

def process_queue():
    global is_processing, current_position
    while True:
        if not request_queue.empty():
            is_processing = True
            request = request_queue.get()
            
            try:
                if request.get('type') == 'refresh':
                    # Initialize and run the scraper
                    scraper = GAFContractorScraper(test_mode=False)
                    try:
                        logger.info("Starting scraping process...")
                        scraper.start_scraping()
                        logger.info("Scraping completed, generating insights...")
                        try:
                            generate_insights()
                            logger.info("Insights generation completed successfully")
                        except Exception as insight_error:
                            logger.error(f"Error generating insights: {insight_error}")
                    except Exception as e:
                        logger.error(f"Error during scraping: {e}")
                else:
                    # Handle other types of requests if needed
                    time.sleep(2)  # Default processing time for other requests
                    
            except Exception as e:
                logger.error(f"Error processing request: {e}")
            finally:
                request_queue.task_done()
                current_position = max(0, request_queue.qsize())
                is_processing = False
                
        time.sleep(0.1)  # Small delay to prevent CPU overuse

# Start the queue processing thread
queue_thread = threading.Thread(target=process_queue, daemon=True)
queue_thread.start()
logger.info("Queue processing thread started")

@app.route('/')
def index():
    print("\n" + "="*50)
    print("ACCESSING INDEX ROUTE")
    print("="*50 + "\n")
    
    logger.info("Index route accessed")
    # Check if data exists and initialize if needed
    data_file = Path('data/contractors.json')
    logger.info(f"Checking data file at: {data_file.absolute()}")
    logger.info(f"Data file exists: {data_file.exists()}")
    
    if not data_file.exists():
        print("\n" + "="*50)
        print("NO DATA FOUND - STARTING SCRAPING")
        print("="*50 + "\n")
        logger.info("No data file found, will initialize scraping")
        if check_and_initialize_data():
            logger.info("Initialization complete, redirecting to waiting page")
            return render_template('waiting.html')
    else:
        logger.info("Data file exists, checking if empty")
        if data_file.stat().st_size == 0:
            print("\n" + "="*50)
            print("DATA FILE IS EMPTY - STARTING SCRAPING")
            print("="*50 + "\n")
            logger.info("Data file is empty, will initialize scraping")
            if check_and_initialize_data():
                logger.info("Initialization complete, redirecting to waiting page")
                return render_template('waiting.html')
    
    # If no one is in queue and not processing, show page immediately
    if request_queue.empty() and not is_processing:
        logger.info("Showing index page")
        return render_template('index.html')
    # Otherwise, redirect to waiting page
    logger.info("Redirecting to waiting page (queue not empty or processing)")
    return render_template('waiting.html')

@app.route('/waiting')
def waiting():
    return render_template('waiting.html')

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    # Add the refresh request to the queue
    request_queue.put({
        'timestamp': time.time(),
        'type': 'refresh'
    })
    return jsonify({'status': 'success', 'message': 'Refresh request added to queue'})

@app.route('/api/queue/join', methods=['POST'])
def join_queue():
    global current_position
    # Only add to queue if not already in queue
    if request_queue.empty() and not is_processing:
        position = request_queue.qsize() + 1
        request_queue.put(position)
        current_position = position
    return jsonify({
        "position": current_position,
        "estimated_wait": 0
    })

@app.route('/api/queue/status', methods=['GET'])
def queue_status():
    if request_queue.empty():
        return jsonify({'position': 0, 'estimated_wait': 0})
    
    # Find the request's position in the queue
    position = request_queue.qsize()
    return jsonify({
        'position': position,
        'estimated_wait': 0  # No wait time since we removed the 5-second delay
    })

@app.route('/api/contractors', methods=['GET'])
def get_contractors():
    # If no one is in queue and not processing, return data immediately
    if request_queue.empty() and not is_processing:
        return jsonify(load_contractors())
    return jsonify({"error": "Please wait for your turn"}), 429

if __name__ == '__main__':
    logger.info("Starting Flask application...")
    logger.info("Server will be available at http://localhost:5001")
    app.run(debug=True, port=5001) 