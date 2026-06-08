from src.domain.section import Section
from src.domain.toc_node import TocNode
from src.ingestion import TOCService


def node(
    node_id: str,
    title: str,
    level: int,
    section_id: str,
    href: str | None = None,
    children: list[TocNode] | None = None,
) -> TocNode:
    section = Section(id=section_id, raw_text="Text")
    return TocNode(
        id=node_id,
        title=title,
        section_id=section.id,
        href=href,
        level=level,
        order=0,
        section=section,
        children=children or [],
    )


def root(children: list[TocNode]) -> TocNode:
    return TocNode(
        id="fake_root",
        title="Root",
        level=0,
        order=0,
        children=children,
    )


def sections_from(node: TocNode) -> list[Section]:
    return node.get_all_sections()


def test_to_toc_node_tree_builds_flat_children_from_book_toc():
    toc_root = root(
        [
            node("toc-1", "One", 1, "section-1"),
            node("toc-2", "Two", 1, "section-2"),
            node("toc-3", "Three", 1, "section-3"),
        ]
    )
    toc_data = TOCService.to_book_toc(toc_root, "book-1")

    restored = TOCService.to_toc_node_tree(toc_data, sections_from(toc_root))

    assert restored is not None
    assert [child.title for child in restored.children] == ["One", "Two", "Three"]
    assert all(child.children == [] for child in restored.children)


def test_to_toc_node_tree_builds_nested_children_from_book_toc():
    toc_root = root(
        [
            node(
                "toc-1",
                "Chapter 1",
                1,
                "section-1",
                children=[
                    node("toc-2", "Section 1.1", 2, "section-2"),
                    node("toc-3", "Section 1.2", 2, "section-3"),
                ],
            ),
            node(
                "toc-4",
                "Chapter 2",
                1,
                "section-4",
                children=[node("toc-5", "Section 2.1", 2, "section-5")],
            ),
        ]
    )
    toc_data = TOCService.to_book_toc(toc_root, "book-1")

    restored = TOCService.to_toc_node_tree(toc_data, sections_from(toc_root))

    assert restored is not None
    assert [child.title for child in restored.children] == ["Chapter 1", "Chapter 2"]
    assert [child.title for child in restored.children[0].children] == [
        "Section 1.1",
        "Section 1.2",
    ]
    assert [child.title for child in restored.children[1].children] == ["Section 2.1"]


def test_to_book_toc_stores_structure_and_leaves_title_on_section():
    section = Section(id="section-1", raw_text="Text")
    toc_root = root(
        [
            TocNode(
                id="toc-1",
                title="Chapter 1",
                section_id=section.id,
                href="chapter.xhtml",
                level=1,
                order=0,
                section=section,
            )
        ]
    )

    toc_data = TOCService.to_book_toc(toc_root, "book-1")

    assert toc_data == [
        {
            "id": "toc-1",
            "section_id": "section-1",
            "href": "chapter.xhtml",
            "level": 1,
            "order": 1,
            "children": [],
        }
    ]
    assert "title" not in toc_data[0]
    assert section.book_id == "book-1"
    assert section.title == "Chapter 1"
    assert section.level == 1
    assert section.order == 1
    assert section.href == "chapter.xhtml"


def test_to_book_toc_creates_empty_section_for_title_only_node():
    toc_root = root(
        [
            TocNode(
                id="toc-1",
                title="Part 1",
                href=None,
                level=1,
                order=0,
                children=[],
            )
        ]
    )

    toc_data = TOCService.to_book_toc(toc_root, "book-1")
    sections = toc_root.get_all_sections()
    restored = TOCService.from_book_toc(toc_data, sections)

    assert "title" not in toc_data[0]
    assert len(sections) == 1
    assert sections[0].title == "Part 1"
    assert sections[0].book_id == "book-1"
    assert restored is not None
    assert restored.children[0].title == "Part 1"


def test_from_book_toc_resolves_titles_from_sections():
    section = Section(
        id="section-1",
        book_id="book-1",
        title="Section Title",
        level=1,
        order=1,
        href="chapter.xhtml",
    )
    toc_data = [
        {
            "id": "toc-1",
            "section_id": section.id,
            "href": "chapter.xhtml",
            "level": 1,
            "order": 1,
            "children": [],
        }
    ]

    restored = TOCService.from_book_toc(toc_data, [section])

    assert restored is not None
    assert restored.children[0].title == "Section Title"
    assert restored.children[0].section is section


def test_to_tree_returns_response_model_from_book_toc():
    toc_root = root([node("toc-1", "Chapter 1", 1, "section-1")])
    toc_data = TOCService.to_book_toc(toc_root, "book-1")

    model = TOCService.to_tree(toc_data, sections_from(toc_root))

    assert model is not None
    assert model.children[0].title == "Chapter 1"
    assert model.children[0].section_id == "section-1"
