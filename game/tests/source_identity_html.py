"""Read the actual readonly Source identity blocks without a browser/session."""
from html.parser import HTMLParser


class SourceIdentityParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.rows = {}
        self.current = None
        self.depth = 0
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "div" and attrs.get("data-source-identity"):
            self.current = {
                "status": attrs["data-source-status"],
                "blocks": attrs["data-source-blocks"] == "true",
                "checked_at": attrs["data-source-checked-at"],
                "parts": [],
            }
            self.rows[attrs["data-source-identity"]] = self.current
            self.depth = 1
        elif self.current is not None:
            if tag == "div":
                self.depth += 1
            elif tag == "input":
                self.current["external_id"] = attrs.get("value", "")
                self.current["readonly"] = "readonly" in attrs

    def handle_endtag(self, tag):
        if self.current is not None and tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.current["text"] = " ".join("".join(self.current.pop("parts")).split())
                self.current = None

    def handle_data(self, text):
        if self.current is not None:
            self.current["parts"].append(text)
