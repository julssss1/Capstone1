from dotenv import load_dotenv
load_dotenv() 

from app import create_app 
from app import sign_logic
import atexit

atexit.register(sign_logic.release_resources)

app = create_app()

if __name__ == '__main__':
    print("Starting Flask development server...")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
