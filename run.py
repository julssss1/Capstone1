from dotenv import load_dotenv
load_dotenv() 

from app import create_app 

app = create_app()

if __name__ == '__main__':
    print("Starting Flask development server...")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
