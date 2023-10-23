CALL apoc.periodic.iterate(
  "MATCH (n) RETURN n",
  "DETACH DELETE n",
  {batchSize: 500, iterateList: true, parallel: false}
)


from flask import Flask, request, Response
import os

app = Flask(__name__)

@app.route("/")
def serve_file():
    try:
        path = os.path.join("docs", request.path[1:])
        extname = os.path.splitext(path)[-1]
        content_type = 'text/html'

        if extname == '.js':
            content_type = 'text/javascript'
        elif extname == '.css':
            content_type = 'text/css'
        elif extname == '.ico':
            content_type = 'image/x-icon'
        elif extname == '.svg':
            content_type = 'image/svg+xml'
        elif extname == '.csv':
            content_type = 'text/csv'

        if not os.path.exists(path):
            return "404 Not Found", 404

        if os.path.isdir(path):
            path = os.path.join(path, 'index.html')

        with open(path, 'rb') as file:
            file_contents = file.read()

        return Response(file_contents, content_type=content_type)
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8888))
    app.run(host="localhost", port=port)
    print("Server is running on http://localhost:" + str(port))