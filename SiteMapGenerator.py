import requests
from dotenv import dotenv_values
from datetime import datetime
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("-f","--force",action='store_true',help="Forces an update")
args = parser.parse_args()

conf = dotenv_values(".env")
authHead = {'Authorization': f"Token {conf['TOKEN_ID']}:{conf['TOKEN_SECRET']}"}
outputPageID = int(conf['SITEMAP_ID'])

endpoint = conf['ENDPOINT']
lastRequest = datetime.now()

def getBookstack(query):
    # Rate limiting to 180 requests / min
    global lastRequest
    now = datetime.now()
    if ((now-lastRequest).seconds) < (1/3):
        time.sleep(0.5)
    

    call = requests.get(f'{endpoint}/{query}', headers=authHead)
    if call.status_code != 200:
        print(f'Request {query} failed, result code {call.status_code}')
    else:
        print(f'Request {query} succeeded')
        return call.json()

# Standard function to get full list of things from bookstack
# Gets list, offsets query if response is less than total pages
def getFullList(queryType,responseAtt="data"):
    query = getBookstack(queryType)
    workingData = query[responseAtt]
    saved = len(workingData)
    count = query['total']

    while saved<count:
        offsetQuery = getBookstack(f'{queryType}?offset={saved}')[responseAtt]
        workingData = workingData + offsetQuery
        saved = len(workingData)

    return workingData

fullPages = getFullList('pages')

outputPageMeta = getBookstack(f'pages/{outputPageID}')

lastRan = datetime.fromisoformat(outputPageMeta['updated_at'].strip('Z'))
lastUpdated = datetime.fromisoformat("2000-01-01T00:00:00")

if not args.force:
    for page in fullPages:
        if page['id'] != outputPageID:
            updated = datetime.fromisoformat(page['updated_at'].strip('Z'))
            if updated > lastUpdated:
                lastUpdated = updated

if lastUpdated > lastRan or args.force:
    print("Updating...")

    shelfList = []

    fullShelves = getFullList('shelves')
    for shelf in fullShelves:
        shelfList.append((shelf['name'],shelf['id'],shelf['slug'],shelf['description']))
        
    shelfList.sort()
    shelfToBooks = {}
    booksToContents = {}

    for shelf in shelfList:
        id = shelf[1]
        bookList = []
        books = getBookstack(f'shelves/{id}')['books']
        for book in books:
            bookList.append((book['name'],book['id'],book['slug']))
            
            bookID = book['id']
            contentList = []
            bookContents = getBookstack(f'books/{bookID}')['contents']
            for item in bookContents:
                if item['type'] == 'chapter':
                    contentList.append((item['name'],'chapter',item['url']))
                    for page in item['pages']:
                        contentList.append((page['name'], 'page', page['url']))
                else:
                    contentList.append((item['name'], 'page', item['url']))
            contentList.sort()
            booksToContents[bookID] = contentList

        bookList.sort()
        shelfToBooks[id] = bookList

    htmlOutput = []
    for shelf in shelfList:
        head = f'<h3 class="shelf"><a href="/shelves/{shelf[2]}">{shelf[0]}</a></h3>'
        htmlOutput.append(head)
        desc = f'<p><i>{shelf[3]}</i></p>'
        htmlOutput.append(desc)

        for books in shelfToBooks[shelf[1]]:
            htmlOutput.append(f'<h5 class="book"><a href="/books/{books[2]}">{books[0]}</a></h5>')
            htmlOutput.append("<ul>")
            for contents in booksToContents[books[1]]:
                if contents[1] == 'chapter':
                    htmlOutput.append(f'<li class="chapter"><b><u><a href={contents[2]}>{contents[0]}</b></u></li>')
                else:
                    htmlOutput.append(f'<li class="page"><a href={contents[2]}>{contents[0]}</li>')
            htmlOutput.append("</ul>")

    output = "\n".join(htmlOutput)

    postOutput = {"html": output}

    call = requests.put(f'{endpoint}/pages/{outputPageID}', headers=authHead, data=postOutput)
    if call.status_code != 200:
        print(f'Final PUT failed, result code {call.status_code}')
    else:
        print(f'Final PUT succeeded')

else:
    print("No update needed")