from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Directory where uploaded files will be stored
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/save-user-state', methods=['POST'])
def save_user_state():
    # Check if the file part is present in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    # If the user does not select a file, the browser submits an
    # empty part without a filename
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check if the file is one of the allowed types/extensions
    if file and file.filename.endswith('.png'):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    else:
        return jsonify({'error': 'Invalid file format'}), 400

    # Get user_id from headers
    user_id = request.headers.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is missing from headers'}), 400
    
    # Get JSON data from the request
    try:
        data = request.get_json()
    except Exception as e:
        return jsonify({'error': 'Invalid JSON data provided'}), 400

    # You can process the data/perform actions here as needed
    # For example, saving to a database or processing the data
    
    # Return a success response
    return jsonify({
        'message': 'File uploaded and data received successfully',
        'user_id': user_id,
        'received_data': data
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
