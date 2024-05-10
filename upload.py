from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime

app = Flask(__name__)

# Base upload folder
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/save-user-state', methods=['POST'])
def save_user_state():
    # Validate and retrieve user_id from headers
    user_id = request.headers.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is missing from headers'}), 400

    # Generate timestamp and folder paths
    timestamp = datetime.now()
    date_path = timestamp.strftime('%Y/%m/%d')
    time_stamp_str = timestamp.strftime('%Y%m%d%H%M%S')
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id, date_path)

    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    # Check for file in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Validate and save the file
    if file and file.filename.endswith('.png'):
        filename = f"filename_{time_stamp_str}.png"
        file_path = os.path.join(user_folder, secure_filename(filename))
        file.save(file_path)
    else:
        return jsonify({'error': 'Invalid file format'}), 400

    # Process the JSON data
    try:
        data = request.get_json()
        # Validate or process the received JSON data if necessary
    except Exception as e:
        return jsonify({'error': 'Invalid JSON data provided'}), 400

    # Save JSON data to file
    data_filename = f"state_{time_stamp_str}.json"
    data_file_path = os.path.join(user_folder, data_filename)
    with open(data_file_path, 'w') as json_file:
        json.dump(data, json_file)

    # Return success response
    return jsonify({
        'message': 'File uploaded and data saved successfully',
        'user_id': user_id,
        'file_path': file_path,
        'data_file_path': data_file_path
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
