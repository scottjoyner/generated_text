from flask import Flask, request, jsonify, send_from_directory
import os

app = Flask(__name__)

# save route
@app.route('/save', methods=['POST'])
def save():
    # get the JSON data from the request
    data = request.get_json()

    # get the filename from the data
    filename = data.get('filename')

    # write the JSON data to a file with the given filename
    with open(filename, 'w') as f:
        json.dump(data, f)

    return jsonify({'message': 'File saved successfully.'})

# serving route
@app.route('/view-graph/<filename>')
def view_graph(filename):
    # get the absolute path of the file
    filepath = os.path.join(app.root_path, filename)

    # check if the file exists
    if not os.path.isfile(filepath):
        return jsonify({'message': 'File not found.'}), 404

    # serve the file
    return send_from_directory(app.root_path, filename)

if __name__ == '__main__':
    app.run(debug=True)
