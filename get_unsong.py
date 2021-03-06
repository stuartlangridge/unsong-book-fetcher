import urllib.request
import sys
from bs4 import BeautifulSoup
import re
import os
import json
import datetime
import base64
import magic
import io
from PIL import Image, ImageDraw, ImageFont

CHAPTERS = []
AUTHOR_NOTES = []
header = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Unsong</title>
</head>
<body>
"""
footer = """<hr><article>
<p>Made from <a href="http://unsongbook.com/">the Unsong book website</a> by
the <a href="https://github.com/stuartlangridge/unsong-book-fetcher">Unsong fetcher script</a> 
by <a href="https://kryogenix.org">Stuart Langridge</a>.</p>
</article>
</body></html>"""

def create_book():
    # create cover
    title_img_data = fetch_or_get("http://i.imgur.com/d9LvKMc.png", binary=True)
    bio = io.BytesIO(title_img_data)
    title_img = Image.open(bio)
    tw, th = title_img.size
    cw = int(tw * 1.5)
    ch = int(cw * 1.6)
    cover_img = Image.new("RGBA", (cw, ch))
    draw = ImageDraw.Draw(cover_img)
    gradient = ((180,119,14), (210,181,100))
    height = cover_img.size[1]
    rs, gs, bs = gradient[0]
    re, ge, be = gradient[1]
    rr = re - rs; gr = ge - gs; br = be - bs
    for i in range(height):
        r = rs + int(rr*i/height)
        g = gs + int(gr*i/height)
        b = bs + int(br*i/height)
        draw.line([(0,i), (cw,i)], fill=(r,g,b))

    tlx = int((cw - tw) / 2)
    tly = int((ch - th) / 2)
    cover_img.paste(title_img, (tlx, tly), title_img)

    font = None
    try:
        font = ImageFont.truetype("/usr/share/texlive/texmf-dist/fonts/truetype/public/opensans/OpenSans-Light.ttf", size=24)
    except:
        font = None

    txt = "Scott Alexander"
    txtw, txth = draw.textsize(txt, font=font)
    draw.text((int((cw - txtw) / 2), ch - 100), txt, fill=(0,0,0), font=font)

    bio = io.BytesIO()
    cover_img.save(bio, "PNG")
    cover_src = "data:image/png;base64,%s" % (base64.encodestring(bio.getvalue()).decode("utf-8"))

    # Special handling for chapter 18, which should be in book II but Alexander has done the
    # navigation links wrongly,so we manually insert it before c19
    nchapters = []
    c18 = None
    for c in CHAPTERS:
        if "Chapter 18:" in c:
            c18 = c
            continue
        elif "Chapter 19" in c:
            nchapters.append(c18)
        nchapters.append(c)

    # Strip out a few artifacts which shouldn't be in a final book.
    #print([(x, nchapters[x][60:120]) for x in range(len(nchapters))])
    nchapters[98] = nchapters[98].replace("An epilogue will be published on Wednesday.", "")

    fp = open("Unsong.html", encoding="utf-8", mode="w")
    fp.write(header)
    fp.write("<header><img src='%s' alt=''><h1>Unsong</h1><h2>Scott Alexander</h2></header>" % cover_src)
    fp.write("<main>")
    fp.write("\n\n\n".join(nchapters))
    fp.write("</main>")
    fp.write("<section>")
    fp.write("<h1>Appendix: Author Notes</h1>")
    fp.write("\n\n\n".join(AUTHOR_NOTES))
    fp.write("</section>")
    fp.write(footer)
    fp.close()

def slugify(url):
    return re.sub(r"[^A-Za-z0-9]", "_", url)

def fetch_or_get(url, binary=False):
    slug = slugify(url)
    slug = "cache/%s" % slug
    if os.path.exists(slug):
        if binary:
            fp = open(slug, mode="rb")
        else:
            fp = open(slug, encoding="utf-8")
        data = fp.read()
        fp.close()
        #print("Got", url, "from cache")
    else:
        print("Fetching", url, "from web")
        req = urllib.request.Request(
            url, 
            data=None, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
            }
        )
        fp = urllib.request.urlopen(req)
        data = fp.read()
        fp.close()
        if binary:
            fp = open(slug, mode="wb")
            fp.write(data)
            fp.close()
        else:
            fp = open(slug, encoding="utf-8", mode="w")
            fp.write(data.decode("utf-8"))
            fp.close()
    return data

def get_cached_parsed(url):
    slug = "CACHED_PARSED_%s" % (slugify(url),)
    slug = "cache/%s" % slug
    if not os.path.exists(slug): return
    fp = open(slug, encoding="utf-8")
    data = json.load(fp)
    fp.close()
    return data

def put_cached_parsed(url, data):
    slug = "CACHED_PARSED_%s" % (slugify(url),)
    slug = "cache/%s" % slug
    fp = open(slug, encoding="utf-8", mode="w")
    json.dump(data, fp)
    fp.close()

def remove_cache(url):
    # first remove the HTML cache
    slug = slugify(url)
    slug = "cache/%s" % slug
    if os.path.exists(slug): os.unlink(slug)
    # next, remove the cached parsed
    slug = "CACHED_PARSED_%s" % (slugify(url),)
    slug = "cache/%s" % slug
    if os.path.exists(slug): os.unlink(slug)

def get_url(url):
    global ALL_CACHED
    data = fetch_or_get(url, binary=False)
    cached_parsed = get_cached_parsed(url)
    if cached_parsed:
        return cached_parsed
    details = {}
    soup = BeautifulSoup(data, "lxml")
    post = soup.find_all("div", "post")
    nav = soup.find_all("div", "pjgm-navigation")
    heading = post[0].find_all("h1", "pjgm-posttitle")[0]
    if heading.text.lower().startswith("book"):
        details["type"] = "book"
    elif heading.text.lower().startswith("author"):
        details["type"] = "author note"
    else:
        details["type"] = "chapter"
    if details["type"] == "book":
        heading.name = "h1"
    else:
        heading.name = "h2"
    content = post[0].find_all("div", "pjgm-postcontent")[0]
    prev = None
    next = None
    prevs = nav[0].find_all("a", {"rel": "prev"})
    if prevs: prev = prevs[0].attrs["href"]
    nexts = nav[0].find_all("a", {"rel": "next"})
    if nexts: next = nexts[0].attrs["href"]
    share = soup.find_all("div", "sharedaddy")
    [s.extract() for s in share]

    # cache images
    for img in content.find_all("img"):
        img_url = img["src"]
        img_data = fetch_or_get(img_url, binary=True)
        magic_identifier = magic.Magic(mime=True)
        img_type = magic_identifier.from_buffer(img_data)
        img_type = img_type.split(";")[0]

        img["src"] = "data:%s;base64,%s" % (img_type, base64.encodestring(img_data).decode("utf-8"))

    html = '<article class="%s">\n%s\n%s\n</article>\n' % (details["type"], heading, content)
    output = (prev, html, details, next)
    put_cached_parsed(url, output)
    ALL_CACHED = False

    return output

def get_next(next):
    global AUTHOR_NOTES, CHAPTERS, FORCE
    last_fetched = next
    previous, html, details, next = get_url(next)
    if details["type"] == "author note":
        AUTHOR_NOTES.append(html)
    else:
        CHAPTERS.append(html)
    if next:
        get_next(next)
    else:
        if ALL_CACHED:
            if FORCE:
                print("Forcing")
                if details["type"] == "author note":
                    AUTHOR_NOTES= AUTHOR_NOTES[:-1]
                else:
                    CHAPTERS = CHAPTERS[:-1]
                remove_cache(last_fetched)
                get_next(last_fetched)
            else:
                print("Whole book retrieved from cache.")
                print("To force an update (to pull in more recent chapters), pass --force parameter.")
        create_book()

FORCE = False
ALL_CACHED = True

if __name__ == "__main__":
    if "--force" in sys.argv:
        FORCE = True
    get_next("http://unsongbook.com/prologue-2/")