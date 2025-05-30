from dotenv import load_dotenv
load_dotenv() 

from app import create_app 


app = create_app()

if __name__ == '__main__':

    from app import sign_logic
    if sign_logic.interpreter and sign_logic.hands:
         print("Starting Flask development server...")

         app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
    else:
         print("\n" + "="*50)
         print("FATAL: Application startup aborted due to initialization errors.")
         print("Please review the logs above for details.")
         print("="*50 + "\n")
