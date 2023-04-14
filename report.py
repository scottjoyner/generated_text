import os
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/report-files/'

ALLOWED_EXTENSIONS = {'zip', 'pdf', 'csv', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload-report', methods=['POST'])
def upload_report():
    if 'file' not in request.files:
        return jsonify({'error': 'No file was provided.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file was selected.'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed.'}), 400
    uuid = request.form.get('uuid')
    if not uuid:
        return jsonify({'error': 'UUID not provided.'}), 400
    filename = str(uuid) + '_' + file.filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    os.chmod(file_path, 0o644)  # set file permissions to not executable
    return jsonify({'message': 'File saved successfully.'}), 200
