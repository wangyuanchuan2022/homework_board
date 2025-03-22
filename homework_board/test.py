import requests
import json

url = "http://127.0.0.1:8000/api/get_today_homework/"
data = {
    "username": "yf105",
    "password": "rdfzrdfz"
}

response = requests.post(url, json=data)
print("状态码:", response.status_code)
print("响应内容:")
print(response.text)

# 由于返回的是纯文本而不是JSON，不需要解析JSON
# 直接打印文本内容即可