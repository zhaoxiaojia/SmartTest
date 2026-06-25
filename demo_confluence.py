from atlassian import Confluence

confluence = Confluence(
    url="https://confluence.amlogic.com",
    username="chao.li",
    password="aaa"
)

page_id = "9439863"

page = confluence.get_page_by_id(
    page_id,
    expand="body.storage,version,title"
)

title = page["title"]
html = page["body"]["storage"]["value"]

print(title)
print(html)