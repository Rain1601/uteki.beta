from __future__ import annotations

import bisect
import hashlib
import re
from dataclasses import replace
from urllib.parse import urljoin

from lxml import etree, html

from uteki.domain.documents import (
    AssetReference,
    DocumentIndex,
    DocumentNode,
    IndexDiagnostic,
    ParsedDocument,
    SourceAnchor,
    SourceBlock,
    TableCell,
    TableStructure,
    TocEntry,
)
from uteki.infrastructure.document_sources.sec import normalize_text, text_hash


SCHEMA_VERSION = "document-index-v0.1"
PARSER_VERSION = "sec-source-blocks-v0.1.1"
_PART_RE = re.compile(r"^PART\s+([IVX]+)(?:[.\s—–:-]+(?:FINANCIAL INFORMATION|OTHER INFORMATION))?\.?$", re.IGNORECASE)
_ITEM_RE = re.compile(r"^ITEM\s+(\d+[A-Z]?)\.?\s*(.*)$", re.IGNORECASE)
_STRUCTURAL_ANCHOR_RE = re.compile(r"^i[a-f0-9]{16,}_\d+$", re.IGNORECASE)
_STYLE_KEYS = (
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "line-height",
    "margin-top",
    "padding-left",
    "text-align",
    "text-indent",
)


def _tag(element: etree._Element) -> str:
    return str(element.tag).lower() if isinstance(element.tag, str) else ""


def _style_values(element: etree._Element) -> tuple[tuple[str, str], ...]:
    values: dict[str, str] = {}
    styled = [element, *element.xpath(".//*[@style]")[:3]]
    for candidate in styled:
        for declaration in (candidate.get("style") or "").split(";"):
            if ":" not in declaration:
                continue
            key, value = (part.strip().lower() for part in declaration.split(":", 1))
            if key in _STYLE_KEYS and value and key not in values:
                values[key] = value
    return tuple(sorted(values.items()))


def _table_structure(table: etree._Element) -> TableStructure:
    cells: list[TableCell] = []
    occupied: set[tuple[int, int]] = set()
    max_column = 0
    rows = table.xpath(".//tr[not(ancestor::table[2])]")
    for row_number, row in enumerate(rows):
        column = 0
        for cell in row.xpath("./th|./td"):
            while (row_number, column) in occupied:
                column += 1
            try:
                rowspan = max(1, int(cell.get("rowspan", "1")))
            except ValueError:
                rowspan = 1
            try:
                colspan = max(1, int(cell.get("colspan", "1")))
            except ValueError:
                colspan = 1
            cells.append(
                TableCell(
                    text=normalize_text(cell.text_content()),
                    row=row_number,
                    column=column,
                    rowspan=rowspan,
                    colspan=colspan,
                    is_header=_tag(cell) == "th",
                )
            )
            for covered_row in range(row_number, row_number + rowspan):
                for covered_column in range(column, column + colspan):
                    occupied.add((covered_row, covered_column))
            column += colspan
            max_column = max(max_column, column)
    return TableStructure(row_count=len(rows), column_count=max_column, cells=tuple(cells))


def _toc_table(root: etree._Element) -> etree._Element | None:
    scored: list[tuple[int, etree._Element]] = []
    for table in root.xpath("//table"):
        count = sum(
            bool(_ITEM_RE.match(normalize_text(row.text_content())))
            for row in table.xpath(".//tr[not(ancestor::table[2])]")
        )
        if count:
            scored.append((count, table))
    return max(scored, key=lambda item: item[0])[1] if scored else None


def _toc_entries(table: etree._Element | None, blocks=(), anchors=(), verify_link_roles=False) -> tuple[tuple[TocEntry, ...], tuple[IndexDiagnostic, ...]]:
    if table is None:
        return (), (
            IndexDiagnostic("toc_missing", "warning", "No Part/Item table of contents was detected; body headings will be used."),
        )
    entries: list[TocEntry] = []
    diagnostics: list[IndexDiagnostic] = []
    seen_items: set[tuple[str, str]] = set()
    current_part = ""
    for row_number, row in enumerate(table.xpath(".//tr[not(ancestor::table[2])]") , start=1):
        cell_text = [normalize_text(cell.text_content()) for cell in row.xpath("./th|./td")]
        row_text = normalize_text(row.text_content())
        part_match = _PART_RE.match(next((value for value in cell_text if value), row_text))
        if part_match:
            current_part = part_match.group(1).upper()
            entries.append(TocEntry("part", current_part, f"PART {current_part}", None, None, len(entries) + 1))
            continue
        item_match = _ITEM_RE.match(cell_text[0] if cell_text else row_text)
        if not item_match:
            continue
        number = item_match.group(1).upper()
        title = cell_text[1] if len(cell_text) > 1 and cell_text[1] else item_match.group(2).strip()
        page_text = cell_text[-1] if cell_text else ""
        reported_page = int(page_text) if page_text.isdigit() else None
        hrefs = list(
            dict.fromkeys(
                link.get("href")
                for link in row.xpath(".//a[starts-with(@href, '#')]")
                if link.get("href")
            )
        )
        source_anchor = hrefs[0][1:] if hrefs else None
        equivalent_page_link = False
        if verify_link_roles and len(hrefs) == 2 and reported_page is not None:
            cells = row.xpath('./th|./td')
            title_links = list(dict.fromkeys(cells[1].xpath('.//a[starts-with(@href,"#")]/@href'))) if len(cells) > 2 else []
            page_links = list(dict.fromkeys(cells[-1].xpath('.//a[starts-with(@href,"#")]/@href'))) if cells else []
            if len(title_links) == len(page_links) == 1:
                by_id = {b.block_id: b for b in blocks}
                by_anchor = {a.anchor: by_id.get(a.target_block_id) for a in anchors}
                title_block = by_anchor.get(title_links[0][1:])
                page_block = by_anchor.get(page_links[0][1:])
                heading = _ITEM_RE.match(title_block.text) if title_block else None
                part_heading = _PART_RE.match(page_block.text) if page_block else None
                # A page link may land on the enclosing Part heading, but only
                # after verifying title, Part identity, order and reported page.
                equivalent_page_link = bool(
                    heading and heading.group(1).upper() == number
                    and normalize_text(heading.group(2)).casefold() == title.casefold()
                    and part_heading and part_heading.group(1).upper() == current_part
                    and title_block.reported_page == page_block.reported_page == reported_page
                    and page_block.ordinal <= title_block.ordinal
                )
                if equivalent_page_link:
                    source_anchor = title_links[0][1:]
        if len(hrefs) > 1 and not equivalent_page_link:
            diagnostics.append(
                IndexDiagnostic(
                    "toc_row_anchor_conflict",
                    "error",
                    f"TOC row {row_number} for Item {number} contains conflicting anchors: {', '.join(hrefs)}",
                )
            )
        if not source_anchor:
            diagnostics.append(IndexDiagnostic("toc_anchor_missing", "warning", f"TOC Item {number} has no body anchor."))
        identity = (current_part, number)
        if identity in seen_items:
            diagnostics.append(IndexDiagnostic("toc_item_duplicate", "error", f"Duplicate TOC entry for Part {current_part} Item {number}."))
            continue
        seen_items.add(identity)
        entries.append(TocEntry("item", number, title, source_anchor, reported_page, len(entries) + 1))
    return tuple(entries), tuple(diagnostics)


def _candidate_elements(body: etree._Element) -> list[etree._Element]:
    candidates: list[etree._Element] = []
    for child in body:
        tables = child.xpath(".//table") if _tag(child) != "table" else [child]
        images = child.xpath(".//img") if _tag(child) != "img" else [child]
        if tables or images:
            candidates.extend(tables)
            candidates.extend(images)
            continue
        if normalize_text(child.text_content()):
            candidates.append(child)
    positions = {id(element): index for index, element in enumerate(body.iter())}
    unique = {id(element): element for element in candidates}
    return sorted(unique.values(), key=lambda element: positions[id(element)])


def _nested_candidate_elements(body: etree._Element) -> list[etree._Element]:
    """Unwrap layout/XBRL containers, retaining paragraph-level inline markup.

    Tables remain atomic. Mixed direct text is kept intact rather than dropped.
    No new DOM nodes are created, so source paths remain valid.
    """
    result = []
    boundaries = {'div', 'p', 'li', 'ul', 'ol', 'table', 'img', 'section',
                  'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

    def walk(element):
        tag = _tag(element)
        if not tag or tag in {'script', 'style', 'noscript'}:
            return
        if tag in {'table', 'img'}:
            result.append(element)
            # Nested table/image assets also have their own source identities.
            result.extend(element.xpath('.//table|.//img'))
            return
        has_blocks = any(_tag(child) in boundaries for child in element.iterdescendants())
        direct_text = normalize_text(element.text or '') or any(normalize_text(c.tail or '') for c in element)
        if has_blocks and not direct_text:
            for child in element:
                walk(child)
        elif normalize_text(element.text_content()):
            result.append(element)

    for child in body:
        walk(child)
    return result


def _block_type(element: etree._Element, value: str, styles: tuple[tuple[str, str], ...]) -> str:
    tag = _tag(element)
    if tag == "table":
        return "table"
    if tag == "img":
        return "image"
    style = dict(styles)
    if re.fullmatch(r"\d{1,3}\.?", value) and style.get("text-align") == "center":
        return "page_marker"
    if tag == "li":
        return "list_item"
    weight = style.get("font-weight", "")
    is_bold = weight == "bold" or (weight.isdigit() and int(weight) >= 600)
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} or _PART_RE.match(value) or _ITEM_RE.match(value) or (is_bold and len(value) <= 180):
        return "heading_candidate"
    if tag in {"div", "p"} or tag.startswith("ix:"):
        return "paragraph"
    return "other"


def _asset_reference(element: etree._Element, source_url: str, ordinal: int, dom_path: str) -> AssetReference:
    source_path = element.get("src", "")
    digest = hashlib.sha256(f"{source_path}:{ordinal}".encode()).hexdigest()[:12]
    return AssetReference(
        asset_id=f"asset-{digest}",
        source_url=urljoin(source_url, source_path),
        source_path=source_path,
        alt=element.get("alt"),
        dom_path=dom_path,
    )


def parse_sec_source(
    document_id: str,
    source_url: str,
    raw_html: bytes,
    *,
    source_snapshot_id: str | None = None,
    form_type: str = "10-K",
    parser_version: str = PARSER_VERSION,
) -> ParsedDocument:
    """Parse SEC HTML into source-faithful blocks without changing legacy paragraphs."""
    if form_type in {"10-Q", "10-Q/A"} and parser_version == PARSER_VERSION:
        parser_version = "sec-source-blocks-v0.1.4-quarterly"
    content_hash = hashlib.sha256(raw_html).hexdigest()
    source_snapshot_id = source_snapshot_id or f"{document_id}-{content_hash[:8]}"
    parser = html.HTMLParser(encoding="utf-8", recover=True, remove_comments=False)
    root = html.document_fromstring(raw_html, parser=parser)
    body_matches = root.xpath("//body")
    if not body_matches:
        raise ValueError("SEC source HTML has no body element")
    body = body_matches[0]
    tree = root.getroottree()
    all_elements = list(body.iter())
    positions = {id(element): index for index, element in enumerate(all_elements)}
    nested = parser_version in {"sec-source-blocks-v0.1.4-quarterly", "sec-source-blocks-v0.1.5"}
    candidates = _nested_candidate_elements(body) if nested else _candidate_elements(body)
    candidate_positions = [positions[id(element)] for element in candidates]
    toc = _toc_table(root)
    toc_path = tree.getpath(toc) if toc is not None else None

    structural_anchors: list[tuple[int, str]] = []
    for element in all_elements:
        anchor = element.get("id") or (element.get("name") if _tag(element) == "a" else None)
        if anchor and (_STRUCTURAL_ANCHOR_RE.match(anchor) or not normalize_text(element.text_content())):
            structural_anchors.append((positions[id(element)], anchor))

    blocks: list[SourceBlock] = []
    assets: list[AssetReference] = []
    for ordinal, element in enumerate(candidates, start=1):
        dom_path = tree.getpath(element)
        tag = _tag(element)
        value = normalize_text(element.get("alt", "")) if tag == "img" else normalize_text(element.text_content())
        styles = _style_values(element)
        kind = _block_type(element, value, styles)
        if nested and kind not in {'table', 'image'} and value.startswith(('•', '◦')):
            kind = 'list_item'
        element_position = positions[id(element)]
        preceding = [item for item in structural_anchors if item[0] <= element_position]
        source_anchor = preceding[-1][1] if preceding else None
        table = _table_structure(element) if kind == "table" else None
        image_asset_id = None
        if kind == "image":
            asset = _asset_reference(element, source_url, ordinal, dom_path)
            assets.append(asset)
            image_asset_id = asset.asset_id
        layout_role = None
        if dom_path == toc_path:
            layout_role = "table_of_contents"
        elif kind == "page_marker":
            layout_role = "reported_page_number"
        elif kind == "table" and "Table of Contents" in value and len(value) < 100:
            layout_role = "running_header"
        digest = text_hash(value)
        blocks.append(
            SourceBlock(
                block_id=f"block-{ordinal:06d}-{digest[:8]}",
                ordinal=ordinal,
                type=kind,  # type: ignore[arg-type]
                text=value,
                text_hash=digest,
                source_anchor=source_anchor,
                dom_path=dom_path,
                reported_page=int(value.rstrip(".")) if kind == "page_marker" else None,
                style_signature=styles,
                table=table,
                image_asset_id=image_asset_id,
                layout_role=layout_role,
            )
        )

    # SEC's printed page number is a footer: it labels the blocks that precede
    # it, not the blocks that follow it. Backfill each page segment only after
    # the footer is known so Item starts do not inherit the previous page.
    paged_blocks = list(blocks)
    segment_start = 0
    for index, block in enumerate(blocks):
        if block.type != "page_marker" or block.reported_page is None:
            continue
        for segment_index in range(segment_start, index + 1):
            paged_blocks[segment_index] = replace(paged_blocks[segment_index], reported_page=block.reported_page)
        segment_start = index + 1
    blocks = paged_blocks

    block_positions = [
        (positions[id(element)], block.block_id)
        for element, block in zip(candidates, blocks, strict=True)
        if block.type != "page_marker" and block.layout_role != "running_header"
    ]
    only_positions = [position for position, _ in block_positions]
    anchors: list[SourceAnchor] = []
    for element in all_elements:
        anchor = element.get("id") or (element.get("name") if _tag(element) == "a" else None)
        if not anchor:
            continue
        index = bisect.bisect_left(only_positions, positions[id(element)])
        target_block_id = block_positions[index][1] if index < len(block_positions) else None
        anchors.append(SourceAnchor(anchor, tree.getpath(element), target_block_id))

    toc_entries, toc_diagnostics = _toc_entries(toc, blocks, anchors,
        verify_link_roles=parser_version in {"sec-source-blocks-v0.1.3-quarterly", "sec-source-blocks-v0.1.4-quarterly", "sec-source-blocks-v0.1.5"})
    return ParsedDocument(
        document_id=document_id,
        source_url=source_url,
        content_hash=content_hash,
        source_snapshot_id=source_snapshot_id,
        form_type=form_type,
        parser_version=parser_version,
        blocks=tuple(blocks),
        anchors=tuple(anchors),
        toc_entries=toc_entries,
        assets=tuple(assets),
        parser_diagnostics=toc_diagnostics,
    )


def _body_outline_entries(parsed: ParsedDocument) -> tuple[TocEntry, ...]:
    entries: list[TocEntry] = []
    current_part = ""
    for block in parsed.blocks:
        if block.type != "heading_candidate":
            continue
        part_match = _PART_RE.match(block.text)
        if part_match:
            current_part = part_match.group(1).upper()
            entries.append(TocEntry("part", current_part, f"PART {current_part}", block.source_anchor, block.reported_page, len(entries) + 1))
            continue
        item_match = _ITEM_RE.match(block.text)
        if item_match and current_part:
            entries.append(
                TocEntry(
                    "item",
                    item_match.group(1).upper(),
                    item_match.group(2).strip(" .") or f"Item {item_match.group(1).upper()}",
                    block.source_anchor,
                    block.reported_page,
                    len(entries) + 1,
                )
            )
    return tuple(entries)


def build_legal_outline(parsed_document: ParsedDocument, *, schema_version: str = SCHEMA_VERSION) -> DocumentIndex:
    """Build only the filing's legal Document → Part → Item hierarchy."""
    blocks = parsed_document.blocks
    if not blocks:
        raise ValueError("cannot build an outline for a document without blocks")
    by_id = {block.block_id: block for block in blocks}
    anchor_targets = {anchor.anchor: anchor.target_block_id for anchor in parsed_document.anchors}
    diagnostics = list(parsed_document.parser_diagnostics)
    entries = parsed_document.toc_entries
    if not any(entry.kind == "item" for entry in entries):
        entries = _body_outline_entries(parsed_document)
        diagnostics.append(IndexDiagnostic("outline_body_fallback", "warning", "The legal outline was built from deterministic body heading patterns."))

    resolved: list[tuple[TocEntry, SourceBlock]] = []
    current_part = ""
    search_after = 0
    for entry in entries:
        if entry.kind == "part":
            current_part = entry.number
            candidates = [
                block for block in blocks
                if block.ordinal >= search_after and _PART_RE.match(block.text) and _PART_RE.match(block.text).group(1).upper() == entry.number
            ]
            if candidates:
                resolved.append((entry, candidates[0]))
                search_after = candidates[0].ordinal
            else:
                diagnostics.append(IndexDiagnostic("part_heading_missing", "warning", f"PART {entry.number} was listed in the TOC but no body heading was found."))
            continue
        target_id = anchor_targets.get(entry.source_anchor or "")
        target = by_id.get(target_id or "")
        if target is None:
            candidates = [
                block for block in blocks
                if block.ordinal >= search_after
                and (match := _ITEM_RE.match(block.text))
                and match.group(1).upper() == entry.number
            ]
            target = candidates[0] if candidates else None
            if target:
                diagnostics.append(IndexDiagnostic("item_anchor_fallback", "warning", f"Item {entry.number} used its deterministic body heading fallback."))
        if target is None:
            diagnostics.append(IndexDiagnostic("item_unresolved", "error", f"Item {entry.number} could not be mapped to a source block."))
            continue
        heading_match = _ITEM_RE.match(target.text)
        if not heading_match or heading_match.group(1).upper() != entry.number:
            diagnostics.append(IndexDiagnostic("item_anchor_title_mismatch", "error", f"Item {entry.number} anchor resolves near {target.text[:80]!r}."))
        resolved.append((entry, target))
        search_after = target.ordinal

    index_seed = f"{parsed_document.content_hash}:{schema_version}:{parsed_document.parser_version}"
    index_id = f"didx-{hashlib.sha256(index_seed.encode()).hexdigest()[:16]}"
    root_id = f"{index_id}-document"
    starts: list[tuple[TocEntry, SourceBlock, str, str | None, str | None]] = []
    part_node_id: str | None = None
    current_part_number: str | None = None
    for entry, block in resolved:
        if entry.kind == "part":
            current_part_number = entry.number
            part_node_id = f"{index_id}-part-{entry.number.lower()}"
            starts.append((entry, block, part_node_id, root_id, current_part_number))
        elif part_node_id:
            starts.append((entry, block, f"{part_node_id}-item-{entry.number.lower()}", part_node_id, current_part_number))
        else:
            diagnostics.append(IndexDiagnostic("item_without_part", "error", f"Item {entry.number} has no resolved Part parent."))

    nodes: list[DocumentNode] = [
        DocumentNode(
            node_id=root_id,
            parent_id=None,
            kind="document",
            title=parsed_document.document_id,
            part_number=None,
            item_number=None,
            start_block_id=blocks[0].block_id,
            end_block_id=blocks[-1].block_id,
            source_anchor=blocks[0].source_anchor,
            reported_page=blocks[0].reported_page,
        )
    ]
    part_start_ordinals = [block.ordinal for entry, block, _, _, _ in starts if entry.kind == "part"]
    all_start_ordinals = [block.ordinal for _, block, _, _, _ in starts]
    for entry, start, node_id, parent_id, part_number in starts:
        boundaries = part_start_ordinals if entry.kind == "part" else all_start_ordinals
        following = [ordinal for ordinal in boundaries if ordinal > start.ordinal]
        end_ordinal = (min(following) - 1) if following else blocks[-1].ordinal
        if end_ordinal < start.ordinal:
            diagnostics.append(IndexDiagnostic("node_range_invalid", "error", f"Invalid source range for {node_id}.", node_id))
            end_ordinal = start.ordinal
        end = blocks[end_ordinal - 1]
        nodes.append(
            DocumentNode(
                node_id=node_id,
                parent_id=parent_id,
                kind=entry.kind,
                title=entry.title,
                part_number=part_number,
                item_number=entry.number if entry.kind == "item" else None,
                start_block_id=start.block_id,
                end_block_id=end.block_id,
                source_anchor=entry.source_anchor or start.source_anchor,
                reported_page=entry.reported_page if entry.reported_page is not None else start.reported_page,
            )
        )

    return DocumentIndex(
        index_id=index_id,
        schema_version=schema_version,
        parser_version=parsed_document.parser_version,
        source_snapshot_id=parsed_document.source_snapshot_id,
        form_type=parsed_document.form_type,
        nodes=tuple(nodes),
        diagnostics=tuple(diagnostics),
    )
