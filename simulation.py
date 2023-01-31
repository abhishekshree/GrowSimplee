import sys
import requests
import json

admin_id = sys.argv[0]

url = "localhost:5050/get/admin/drivers?admin_id=1"

payload={}
headers = {}

response = requests.request("GET", url, headers=headers, data=payload)

print(response.text)


