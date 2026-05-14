from bs4 import BeautifulSoup, Tag
import copy

# Paste the whole EpubTextExtractor class here (or import it)
# For the test, we'll just re-implement the minimal needed methods.


class QuickExtractor:
    SKIP_TAGS = {"nav", "script", "style"}
    CONTAINER_TAGS = {"section", "article", "div", "main", "aside", "body"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    @classmethod
    def _is_heading_like(cls, el: Tag) -> bool:
        if el.name != "p":
            return False
        classes = el.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        heading_hints = {"h", "chap", "chapter-title", "section-title"}
        return any(hint in " ".join(classes).lower() for hint in heading_hints)

    @staticmethod
    def _get_heading_level(tag: Tag) -> int:
        name = tag.name.lower()
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            return int(name[1])
        return 7

    @classmethod
    def _find_next_heading_anchor(cls, heading: Tag, soup: BeautifulSoup) -> str | None:
        current_level = cls._get_heading_level(heading)
        node = heading.next_sibling
        while node:
            if isinstance(node, Tag):
                is_heading = node.name in cls.HEADING_TAGS or cls._is_heading_like(node)
                if is_heading and cls._get_heading_level(node) <= current_level:
                    return node.get("id")
                if node.name in cls.CONTAINER_TAGS:
                    inner = node.find(
                        lambda tag: (
                            tag.name in cls.HEADING_TAGS or cls._is_heading_like(tag)
                        )
                        and cls._get_heading_level(tag) <= current_level
                    )
                    if inner:
                        return inner.get("id")
            node = node.next_sibling
        return None

    @classmethod
    def _extract_siblings(cls, start_el: Tag, stop_anchor: str | None) -> str:
        parts = []
        cur = start_el
        while cur:
            if stop_anchor:
                if cur.get("id") == stop_anchor:
                    break
                if cur.find(id=stop_anchor):
                    clone = copy.copy(cur)
                    # trim is not needed for this test
                    if clone.name not in cls.SKIP_TAGS:
                        parts.append(str(clone))
                    break
            if cur.name not in cls.SKIP_TAGS:
                parts.append(str(cur))
            cur = cur.next_sibling if isinstance(cur, Tag) else None
            while cur is not None and not isinstance(cur, Tag):
                cur = cur.next_sibling
        return "".join(parts)

    @classmethod
    def extract_section(cls, html: str, target_anchor: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        target = soup.find(id=target_anchor)
        if not target:
            raise ValueError(f"Anchor {target_anchor} not found")
        # Treat as heading mode
        heading = target
        stop_anchor = cls._find_next_heading_anchor(heading, soup)
        return cls._extract_siblings(heading, stop_anchor)


# --- Test with your provided HTML snippet ---
test_html = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
  <head><title>A Philosophy of Software Design</title></head>
  <body id="9H5K0-05b6553f9a17412dac9f585e0d7ad587" class="calibre">
<div class="booksection">
<p class="chap"><a id="page_45" class="calibre3"></a><b class="calibre4">Chapter 7</b></p>
<p class="chap1b"><b class="calibre4">Different Layer, Different Abstraction</b></p>
<p class="noindent">Software systems are composed... (some text)</p>
<!-- ... content of 7.1 ... -->
<p class="h" id="sec7-1"><a id="page_46" class="calibre3"></a><b class="calibre4">7.1    Pass-through methods</b></p>
<p class="noindent">When adjacent layers have similar abstractions...</p>
<div class="code">...</div>
<div class="boxr">...</div>
<p class="h" id="sec7-2"><b class="calibre4">7.2    When is interface duplication OK?</b></p>
<p class="noindent">Having methods with the same signature...</p>
<!-- more content -->
</div>
</body></html>"""

extractor = QuickExtractor()
extracted = extractor.extract_section(test_html, "sec7-1")
print("=== EXTRACTED CONTENT ===\n")
print(extracted)
print("\n=== CHECK IF 7.2 INCLUDED ===")
if "sec7-2" in extracted or "7.2" in extracted:
    print("❌ FAIL: next section leaked")
else:
    print("✅ PASS: extraction stopped before section 7.2")
