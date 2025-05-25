import eventlet
eventlet.monkey_patch() # Explicitly monkey-patch at the very beginning

from dotenv import load_dotenv
load_dotenv() 

# Import create_app and the socketio instance from app package
from app import create_app, socketio 

# create_app now returns both the app and the initialized socketio instance
app, socketio_instance = create_app()

if __name__ == '__main__':
   
    print("Starting Flask-SocketIO development server with eventlet...")

    socketio_instance.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
  