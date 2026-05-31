import requests
from dotenv import dotenv_values
from datetime import datetime
import argparse
import time

###########################################
# Boilerplate variables
###########################################

# Parse arguments from command line
parser = argparse.ArgumentParser()
parser.add_argument("-f","--force",action='store_true',help="Forces an update")
args = parser.parse_args()

# Load .env values into conf dict
# Environment variables
def readEnv(file):
    with open(file,'r') as envFile:
        envDict = {}
        for line in envFile.readlines():
            try:
                line = line.replace("\n","")
                key = line.split("=")[0]
                value = line.split("=")[1]
                envDict[key] = value
            except:
                print(f"envReader exception - {line} in {file} is not key/value pair separated by =")
        envFile.close()
    
    return envDict

conf = readEnv(".env")
authHead = {'Authorization': f"Token {conf['TOKEN_ID']}:{conf['TOKEN_SECRET']}"}
outputPageID = int(conf['SITEMAP_ID'])
endpoint = conf['ENDPOINT']

# Sets current time for rate limit
lastRequest = datetime.now()

# In em, indent offset and multipler for nested values
indent = 0.5
multiplier = 4

###########################################
# Query function
#
#   Standard function for querying the API, with rate limiting etc.
###########################################
def getBookstack(query):
    # Rate limiting to 180 requests / min
    global lastRequest
    now = datetime.now()
    if ((now-lastRequest).seconds) < (1/3):
        time.sleep(0.5)
    
    # GET from endpoint
    call = requests.get(f'{endpoint}/{query}', headers=authHead)
    if call.status_code != 200:
        print(f'Request {query} failed, result code {call.status_code}')
    else:
        print(f'Request {query} succeeded')
        return call.json()

###########################################
# Full item list function
#
#   Standard function to get full list of things from bookstack
#   Gets list, offsets query if response is less than total pages
###########################################
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

###########################################
# Pre-run checks
###########################################

# Sets updateNeeded to override checks if forcing an update
updateNeeded = args.force

# Checks if force argument hasn't been passed before querying for last page update
if not updateNeeded:
    # Gets full list of items on instance
    fullShelves = getFullList('shelves')
    fullBooks = getFullList('books')
    fullChapters = getFullList('chapters')
    fullPages = getFullList('pages')
    fullItems = fullShelves + fullBooks + fullChapters + fullPages

    # Gets the datetime of the last update to the output page (i.e: when was the Site Map last updated)
    # NOTE: Due to datetime being datetime, have needed to strip the "Z" when using fromisoformat
    outputPageMeta = getBookstack(f'pages/{outputPageID}')
    lastRan = datetime.fromisoformat(outputPageMeta['updated_at'].strip('Z'))
    lastUpdated = datetime.fromisoformat("2000-01-01T00:00:00")

    # Loops through all items except output page, compares update time with the current lastUpdated.
    # If later, overrides the lastUpdated variable
    for item in fullItems:
        if item['id'] != outputPageID:
            updated = datetime.fromisoformat(item['updated_at'].strip('Z'))
            if updated > lastUpdated:
                lastUpdated = updated
    
    # Compares lastUpdated (i.e: the last time anything was updated) with lastRan (i.e: when the Site Map was last updated)
    # If there was an update since the sitemap was last changed, sets updateNeeded to True
    if lastUpdated > lastRan:
        updateNeeded = True


# If no update needed, no action required
if not updateNeeded:
    print("No update needed...")

###########################################
# Update script
###########################################

# If update needed, begins script
else:
    print("Updating...")

    # Gets list of shelves and sorts by the slug
    fullShelves = getFullList('shelves')
    shelfList = []
    for shelf in fullShelves:
        shelfDict = {}
        shelfDict['id'] = shelf['id']
        shelfDict['slug'] = shelf['slug']

        # As we cannot sort a list by a dict, generates a tuple of the slug and the dict
        shelfList.append((shelf['slug'],shelfDict))

    # NOTE: We only need to sort shelves as every other query returns sorted
    shelfList.sort()

    # Creates an empty list to append formatted HTML to
    htmlOutput = []

    ###########################################
    # List generation
    #
    #   These nested "for" loops are the bulk of actions. 
    #   This is where each shelf, book, and chapter is looped through to and a list generated.
    ###########################################

    for entry in shelfList:
        
        # Extracts the shelfDict from the tuple we generated earlier.
        s = entry[1]
        
        # Queries the specific shelf (as we will need more information than we got from just calling 'shelves')
        shelf = getBookstack(f'shelves/{s['id']}')

        # Formats the shelf header as a h3 with the description_html below
        htmlOutput.append(f'<h3 class="shelf"><a href="/shelves/{shelf['slug']}">{shelf['name']}</a></h3>\n<i><u><b>{shelf['description_html']}</u></b></i>')

        # Loops through each book within the shelf
        for b in shelf['books']:
            # Queries the specific book
            book = getBookstack(f'books/{b['id']}')
            
            # Formats the shelf header as a h5
            htmlOutput.append(f'<h5 class="book" style="margin-bottom:0.3em"><a href="/books/{book['slug']}">{book['name']}</a></h5>')

            # If a description for the book has been set, adds it below the header with appropriate formatting
            if book['description_html'] != "<p></p>":
                desc = f'<p style="margin-top:0.3em;margin-bottom:0.3em"><u>{book['description_html'][3:-4]}</u></p>'
                htmlOutput.append(desc)
                
            # If there are more than 50 pages within the book, omits the content
            if len(book['contents']) > 50:
                htmlOutput.append(f'<p style="padding-left: 32px"><a href="/books/{book['slug']}"><i>Contents omitted, {len(book['contents'])} pages available.</i></a></p>')
            
            # If there are less than 50 pages, generates the content list
            else:
                # Opens the unordered lsit
                htmlOutput.append("<ul>")

                # Loops through book contents
                for item in book['contents']:

                    # If the item is a chapter, bolds the item and offsets the chapter pages as 'nested' items
                    if item['type'] == 'chapter':
                        htmlOutput.append(f'<li style="margin-left: {str(indent)}em"><b><a href="{item['url']}">{item['name']}</a></b></li>')
                        
                        for page in item['pages']:
                            htmlOutput.append(f'<li style="margin-left: {str(indent*multiplier)}em"><a href="{page['url']}">{page['name']}</a></li>')
                    
                    # Else, generates the list item
                    else:
                        htmlOutput.append(f'<li style="margin-left: {str(indent)}em"><a href="{item['url']}">{item['name']}</a></li>')
                
                # Closes the unordered list
                htmlOutput.append("</ul>")

        # Adds horizontal line between each shelf
        htmlOutput.append('<hr />')
    
    ###########################################
    # Final output
    ###########################################
    
    # Joins the htmlOutput list as a string and generates the data for the PUT request
    postOutput = {"html": "\n".join(htmlOutput)}

    # PUTs the output over the outputPage's contents
    call = requests.put(f'{endpoint}/pages/{outputPageID}', headers=authHead, data=postOutput)
    if call.status_code != 200:
        print(f'Final PUT failed, result code {call.status_code}')
    else:
        print(f'Final PUT succeeded')