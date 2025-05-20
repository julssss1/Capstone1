from flask import Response
from . import bp  # Use . to import bp from the current package (student)
from app.utils import login_required, role_required
from app.sign_logic import generate_frames, get_stable_prediction

@bp.route('/video_feed')
@login_required
@role_required('Student')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@bp.route('/get_prediction')
@login_required
@role_required('Student')
def get_prediction():
    prediction_data = get_stable_prediction() 
    return Response(prediction_data, mimetype='application/json')
