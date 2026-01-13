import requests

url = "https://r.jina.ai/https://kevgroup.com/open-positions/?gh_jid=4859774007&gh_src=my.greenhouse.search"
headers = {
    "Authorization": "Bearer jina_41a854a487304054bf61d7b4c8565110rxtedNhsQ3HvHynxIaqvhYP1K7on",
    "X-Remove-Selector": "header, .class, #id",
    "X-Retain-Images": "none",
    "X-Wait-For-Selector": "body, .class, #id",
    "X-Wait-For-Timeout": "20000",  # Wait 5 seconds for selector
    "x-timeout": "120"  # 60 second overall timeout
}

response = requests.get(url, headers=headers)
print(response.text)
