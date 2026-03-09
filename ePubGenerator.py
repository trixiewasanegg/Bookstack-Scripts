import requests
from dotenv import dotenv_values
from datetime import datetime
import re
import shutil
from pathlib import Path as path

###########################################
# THIS IS NOT YET WORKING
###########################################

# Environment variables
conf = dotenv_values(".env")
authHead = {'Authorization': f"Token {conf['TOKEN_ID']}:{conf['TOKEN_SECRET']}"}
endpoint = conf['ENDPOINT']
site = conf['SITEURL']
now = datetime.now()
bookUID = site[8:]+datetime.strftime(now,"%Y%m%d%H%M%S")
dir = conf['OUTPUTDIR']
siteName = str(conf['SITENAME'])
creator = conf['CREATOR']
language = conf['LANGUAGE']

# Folder structure & template files
templateFileDirectory = "epub-template-files"
try:
    shutil.copytree(path(templateFileDirectory + "/templatestructure"),path(dir))
except:
    print("Directory already exists")
contentDir = dir+"/OEBPS"
supportedTags = ['body', 'head', 'html', 'title', 'abbr', 'acronym', 'address', 'blockquote', 'br', 'cite', 'code', 'dfn', 'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'kbd', 'p', 'pre', 'q', 'samp', 'span', 'strong', 'var', 'a', 'dl', 'dt', 'dd', 'ol', 'ul', 'li', 'object', 'param', 'b', 'big', 'hr', 'i', 'small', 'sub', 'sup', 'tt', 'del', 'ins', 'bdo', 'caption', 'col', 'colgroup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'img', 'area', 'map', 'meta', 'style', 'link', 'base']

with open(path(templateFileDirectory+"/samplepage.xhtml"),'r') as template:
    pageTemplate = template.read()

# Site and page meta
siteURLRegex = site.replace("/","\\/")
regexes = {}
regexes["shelf"] = "[0-9]{3}"
regexes["book"] = "(?:[0-9]{3}-[0-9]{2})|(?:[0-9]{3}-[a-z]+)"
regexes["chapter"] = "(?:[0-9]{3}-[0-9]{2}[0-9a-z]{2})|(?:[0-9]{3}-[a-z]{5}-[0-9]{2})"
regexes["page"] = "[0-9]{3}-[0-9]{2}[0-9a-z]{4}"

imageList = []

# Extracts slug to pageCode
def slugToPageCode(slug,type="page"):
    pageCodeSearch = re.search(regexes[type],slug,re.IGNORECASE)

    if pageCodeSearch:
        pageCode = "slug-"+pageCodeSearch.group(0)
    else:
        pageCode = "slug-"+slug
    
    return pageCode

# General API query function
def getBookstack(query,fullurl=False):
    if not fullurl:
        callURL = f'{endpoint}/{query}'
    else:
        callURL = query
    call = requests.get(callURL, headers=authHead)
    if call.status_code != 200:
        print(f'Request {query} failed, result code {call.status_code}')
    else:
        print(f'Request {query} succeeded')
        return call
    
# General img download function
def getimg(url,folder):
    global imageList
    filename = "img-"+url.split('/')[-1]
    outputFileName = folder + "/images/" + filename
    with requests.get(url, headers=authHead,stream=True) as img:
        img.raise_for_status()
        with open(outputFileName, "wb") as output:
            shutil.copyfileobj(img.raw, output)
        
    imageList.append(filename)
    return(f"images/{filename}")

# Pulls page details
def pullPage(pageID):
    #Gets page contents
    pageContents = str(getBookstack(f'pages/{pageID}').json()['html'])

    # Replaces links with relative
    absLinks = re.findall(f'<a href="{siteURLRegex}\/[0-9a-z\-\/]+">',pageContents,re.IGNORECASE)
    relLinks = re.findall(f'<a href="\/[0-9a-z\-\/]+">',pageContents,re.IGNORECASE)
    links = absLinks + relLinks

    if links:
        for link in links:
            slugCode = slugToPageCode(link.split("/")[-1][0:-2])
            
            relLink = f'<a href="{slugCode}.xhtml">'
            pageContents = pageContents.replace(link,relLink)

    # Downloads images and updates references
    imageRegex = '(<img.*? src="(.+?)".*?>)'
    # Capture groups:
    # 0 - Whole tag, 1 - srcURL
    
    images = re.findall(imageRegex,pageContents,re.IGNORECASE)

    if images:
        for img in images:
            ref = getimg(img[1],contentDir)
            tag = str(img[0]).replace(img[1],ref)[0:-1]+" />"
            pageContents = pageContents.replace(img[0],tag)

    drawIORegex = '(<div.*drawio-diagram=".+?".*?>([\\s\\S]*?)<\/div>)'
    drawIO = re.findall(drawIORegex,pageContents,re.IGNORECASE)

    if drawIO:
        for div in drawIO:
            pageContents = pageContents.replace(div[0],div[1])


    # Special action for details/summary tag
    detailsSumRegex = '(<details.*?>[\\s\\S]*?(<summary>(.+?)<\\/summary>)[\\s\\S]*?<\/details>)'
    # Capture groups:
    # 0 - Whole section, 1 - Summary section, 2 - Summary text
    
    detailsSearch = re.findall(detailsSumRegex,pageContents,re.IGNORECASE)
    if detailsSearch:
        for section in detailsSearch:
            markup = str(section[0])
            markup = markup.replace("<details", "<div").replace("</details>","</div>")
            markup = markup.replace(section[1],f"<h6><i>{section[2]}</i></h6>\n")
            pageContents = pageContents.replace(str(section[0]),markup)

    # Special action for underline tag
    underlineRegex = '(<u(?: .*)?>[\\s\\S]*?<\\/u>)'
    # Capture groups:
    # 0 - Whole section

    underlineSearch = re.findall(underlineRegex,pageContents,re.IGNORECASE)
    if underlineSearch:
        for section in underlineSearch:
            markup = section.replace("<u",'<span style="text-decoration: underline;"').replace("</u>","</span>")
            pageContents = pageContents.replace(section, markup)

    # Special action for breaks
    pageContents = pageContents.replace("<br>","&#xA;")

    # Substitutes non-supported tags
    tagregex = '((?:<[\/]*([a-z0-9]+)((?:[^>]+?)*)>)+?)'
    # Capture Groups:
    # 0 - whole tag, 1 - module, 3 - meta (e.g: ' id="XYZ"')
    tags = re.findall(tagregex,pageContents,re.IGNORECASE)
    for tag in tags:
        if not tag[1] in supportedTags:
            new = str(tag[0]).replace(tag[1],"span",1)
            pageContents = pageContents.replace(tag[0],new,1)

    return pageContents

# Writes page
def writePage(pageCode,pageName,pageContents):
    xhtml = pageTemplate.replace("[[TITLE]]",pageName).replace("[[BODY]]",pageContents)
    with open(path(f"{contentDir}/{pageCode}.xhtml"),'w',encoding="utf-8") as file:
        file.write(xhtml)
    return True

tocList = []
allSlugs = []
navPointCount = 0
pageMeta = []
miscNav = {}

shelfQuery = getBookstack('shelves').json()['data']

fullShelves = {}

for shelf in shelfQuery:
    fullShelves[slugToPageCode(shelf['slug'])] = shelf

fullShelves = dict(sorted(fullShelves.items()))

for shelfDict in fullShelves:
    shelf = fullShelves[shelfDict]
    shelfSlug = slugToPageCode(shelf['slug'],'shelf')
    allSlugs.append(shelfSlug)

    bookList = []
    books = getBookstack(f'shelves/{shelf["id"]}').json()['books']
    for book in books:
        bookSlug = slugToPageCode(book['slug'],'book')
        allSlugs.append(bookSlug)

        bookMeta = getBookstack(f'books/{book["id"]}').json()
        contents = bookMeta['contents']
        contentList = []
        for item in contents:
            itemSlug = slugToPageCode(item['slug'],'page')
            allSlugs.append(itemSlug)
            if item['type'] == "chapter":
                pages = []
                for page in item['pages']:
                    pageSlug = slugToPageCode(page['slug'],'page')
                    allSlugs.append(pageSlug)

                    pages.append((pageSlug,page['name'],page['id'],False))
                    pageMeta.append((pageSlug,page['name'],page['id']))
                contentList.append((itemSlug,item['name'],item['id'],pages))
                miscNav[itemSlug] = (item['name'],getBookstack(f'chapters/{item["id"]}').json()['description_html'],pages)
            else:
                contentList.append((itemSlug,item['name'],item['id'],False))
                pageMeta.append((itemSlug,item['name'],item['id']))
        
        bookList.append((bookSlug,book['name'],book['id'],contentList))
        miscNav[bookSlug] = (bookMeta['name'],bookMeta['description_html'],contentList)
    
    tocList.append((shelfSlug,shelf['name'],shelf['id'],bookList))
    miscNav[shelfSlug] = (shelf['name'],shelf['description'],bookList)

tocList.sort()

for page in pageMeta:
    writePage(page[0],page[1],pullPage(page[2]))

navPointCount = 0

def genNavPoint(slug,title,list,template,navPoint=False):
    global navPointCount
    if navPoint:
        navPointCount = navPointCount + 1
        nav = template.replace("[[SLUG]]",slug).replace("[[TITLE]]",title).replace("[[N]]",str(navPointCount))
    else:
        nav = template.replace("[[SLUG]]",slug).replace("[[TITLE]]",title)
    
    if list:
        sp=[]
        for item in list:
            sp.append(genNavPoint(item[0],item[1],item[3],template,navPoint))
        subPoint = "\n".join(sp)
    else:
        subPoint = ""
    nav = nav.replace("[[SUBPOINT]]",subPoint)
    return nav

with open(path(templateFileDirectory+"/pageTOCTemp.xhtml"),'r') as tempFile:
    pageToC = str(tempFile.read())


for page in miscNav:
    slug = page
    name = miscNav[page][0]
    desc = miscNav[page][1]
    contList = miscNav[page][2]
    navList = genNavPoint(slug,name,contList,pageToC,False)
    pageContents = "<ul>\n"+navList.replace("<ul>\n\n</ul>","").replace("&","&amp;")+"\n</ul>"
    writePage(slug,name,pageContents)

with open(path(templateFileDirectory+"/toctemp.xml"),'r') as toc:
    navPoint = str(toc.read())

navPointList = []

for shelf in tocList:
    navPointList.append(genNavPoint(shelf[0],shelf[1],shelf[3],navPoint,True))

navPoints = "\n".join(navPointList)

with open(path(templateFileDirectory+"/toc.ncx"),'r') as ncx:
    tocNCX = ncx.read()

tocNCX = tocNCX.replace("[[navPoints]]",navPoints).replace("[[TITLE]]",siteName).replace("[[UID]]",bookUID).replace("&","&amp;")

with open(path(contentDir+"/toc.ncx"),'w',encoding='UTF-8') as toc:
    toc.write(tocNCX)

imageTemplate = '  <item id="[[FILENAME]]" href="images/[[FILENAME]]" media-type="image/[[FILETYPE]]"/>'
pageTemplate = '  <item id="[[SLUG]]" href="[[SLUG]].xhtml" media-type="application/xhtml+xml"/>'
spineTemplate = '  <itemref idref="[[SLUG]]"/>'

imageManifest = []
pageManifest = []
spineManifest = []

for image in imageList:
    fileType = image.split(".")[1]
    imageManifest.append(imageTemplate.replace("[[FILENAME]]",image).replace("[[FILETYPE]]",fileType))

for slug in allSlugs:
    pageManifest.append(pageTemplate.replace("[[SLUG]]",slug))
    spineManifest.append(spineTemplate.replace("[[SLUG]]",slug))

with open(path(templateFileDirectory+"/contentTemp.opf"),'r') as tempFile:
    opfTemp = tempFile.read()
    content = opfTemp.replace("[[TITLE]]",siteName).replace("[[CREATOR]]",creator).replace("[[LANG]]",language).replace("[[BOOKUID]]",bookUID).replace("[[IMAGES]]","\n".join(imageManifest)).replace("[[PAGES]]","\n".join(pageManifest)).replace("[[SPINE]]","\n".join(spineManifest))

with open(path(contentDir+"/content.opf"),'w',encoding='UTF-8') as output:
    output.write(content)

shutil.make_archive("book",'zip',dir)
shutil.move("book.zip","book.epub")