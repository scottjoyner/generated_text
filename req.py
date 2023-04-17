import requests

url = 'http://localhost:5000/upload-report'
uuid = 'your-unique-id-here' # replace this with your own unique ID

file = {'file': open('example.csv', 'rb')}
data = {'uuid': uuid}

response = requests.post(url, files=file, data=data)

print(response.json())
