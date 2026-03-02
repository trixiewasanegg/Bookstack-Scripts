import requests
from dotenv import dotenv_values
from datetime import datetime
import re

###########################################
# THIS IS NOT YET WORKING
###########################################

conf = dotenv_values(".env")
authHead = {'Authorization': f"Token {conf['TOKEN_ID']}:{conf['TOKEN_SECRET']}"}
endpoint = conf['ENDPOINT']

tempPageID = 3

def getBookstack(query):
    call = requests.get(f'{endpoint}/{query}', headers=authHead)
    if call.status_code != 200:
        print(f'Request {query} failed, result code {call.status_code}')
    else:
        print(f'Request {query} succeeded')
        return call

pageMeta = getBookstack(f'pages/{tempPageID}').json()
codeSearch = re.search('[0-9]{3}-[0-9]{6}',pageMeta["name"],re.IGNORECASE)

if codeSearch:
    code = codeSearch.group(0)
    print(code)

with open(f"{code}.xhtml","w",encoding="utf-8") as test:
    test.write(pageMeta["html"])
