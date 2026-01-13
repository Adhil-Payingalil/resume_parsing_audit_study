import requests

url = 'https://r.jina.ai/https://job-boards.greenhouse.io/partnerstack/jobs/4607080005?gh_src=my.greenhouse.search'
headers = {
    'Authorization': 'Bearer jina_41a854a487304054bf61d7b4c8565110rxtedNhsQ3HvHynxIaqvhYP1K7on'
}

response = requests.get(url, headers=headers)

print(response.text)
