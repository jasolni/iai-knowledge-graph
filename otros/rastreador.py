import requests

URL = "https://sru.k10plus.de/opac-de-627"

indices = [
    "jah",
    "jhr",
    "ver",
    "tit",
    "all"
]

for idx in indices:

    params = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": f"pica.{idx}=1978",
        "maximumRecords": 1,
        "recordSchema": "picaxml"
    }

    r = requests.get(URL, params=params)

    if "<numberOfRecords>" in r.text:
        ini = r.text.find("<zs:numberOfRecords>")
        fin = r.text.find("</zs:numberOfRecords>")
        print(idx, r.text[ini:fin])