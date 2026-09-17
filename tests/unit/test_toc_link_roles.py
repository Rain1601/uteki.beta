import unittest
from types import SimpleNamespace as N
from lxml import html
from uteki.infrastructure.document_sources.sec_index import _toc_entries


class LinkRolesTests(unittest.TestCase):
    def check_roles(self, page=4, heading='ITEM 1. FINANCIAL STATEMENTS', part='PART I', page_target='part'):
        table=html.fromstring(f'''<table><tr><td>PART I</td></tr>
        <tr><td>Item 1</td><td><a href="#item">Financial Statements</a></td>
        <td><a href="#{page_target}">4</a></td></tr></table>''')
        blocks=[N(block_id='p',text=part,reported_page=page,ordinal=10),
                N(block_id='i',text=heading,reported_page=4,ordinal=11)]
        anchors=[N(anchor='part',target_block_id='p'),N(anchor='item',target_block_id='i')]
        return _toc_entries(table,blocks,anchors,True)

    def test_verified_same_page_is_not_conflict(self):
        entries, diagnostics=self.check_roles()
        self.assertEqual(entries[-1].source_anchor,'item')
        self.assertEqual(diagnostics,())

    def test_true_conflicts_are_preserved(self):
        for changes in ({'page':5},{'heading':'ITEM 1. WRONG TITLE'},{'part':'PART II'},{'page_target':'missing'}):
            with self.subTest(changes=changes):
                _,diagnostics=self.check_roles(**changes)
                self.assertIn('toc_row_anchor_conflict',[d.code for d in diagnostics])
