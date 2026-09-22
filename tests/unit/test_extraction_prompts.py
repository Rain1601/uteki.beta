import unittest
from pydantic import ValidationError
from agents import AgentOutputSchema
from uteki.infrastructure.research_data.extraction_prompts import Extraction, validate_extraction, PROMPTS, COMMON


class ExtractionPromptTests(unittest.TestCase):
    def setUp(self):
        self.packet = {'entity_catalog': [{'entity_id': 'alphabet'}], 'blocks': [
            {'block_id': 'b', 'text': 'Revenue may grow if supply improves.', 'speaker': 'CFO', 'speaker_role': 'management'},
            {'block_id': 'q', 'text': 'Will it grow?', 'speaker': 'Analyst', 'speaker_role': 'analyst'}]}
        self.record = dict(kind='guidance', entity='alphabet', metric='growth', period=None,
                           value=None, upper=None, unit=None, summary='Conditional growth', speaker='CFO',
                           evidence=[{'block_id': 'b', 'quote': 'Revenue may grow'}],
                           qualifiers=[{'block_id': 'b', 'quote': 'if supply improves'}], question_refs=['q'])

    def test_schema_and_shared_contract(self):
        data = Extraction.model_validate({'records': [self.record], 'gaps': []}).model_dump()
        self.assertEqual(validate_extraction(data, self.packet), [])
        self.assertFalse(AgentOutputSchema(Extraction).json_schema()['additionalProperties'])
        self.assertTrue(all(prompt.startswith(COMMON) for prompt in PROMPTS.values()))
        with self.assertRaises(ValidationError):
            Extraction.model_validate({'records': [self.record], 'gaps': [], 'unsupported': 1})

    def test_qualifier_and_speaker_validation(self):
        self.record['qualifiers'][0]['quote'] = 'fabricated'
        self.record['speaker'] = 'CEO'
        reasons = {e['reason'] for e in validate_extraction({'records': [self.record]}, self.packet)}
        self.assertEqual(reasons, {'nonexact_or_missing_quote', 'speaker_mismatch'})

    def test_analyst_text_cannot_become_management_fact(self):
        self.record['evidence'] = [{'block_id': 'q', 'quote': 'Will it grow?'}]
        self.record['question_refs'] = ['b']
        reasons = {e['reason'] for e in validate_extraction({'records': [self.record]}, self.packet)}
        self.assertIn('analyst_question_as_record', reasons)
        self.assertIn('invalid_question_ref', reasons)

    def test_entity_catalog_controls_attribution_without_default(self):
        self.packet['entity_catalog'] = [{'entity_id': 'sample-company'}]
        errors = validate_extraction({'records': [self.record]}, self.packet)
        self.assertIn('entity_outside_packet_scope', {e['reason'] for e in errors})
        self.record['entity'] = 'sample-company'
        self.assertEqual(validate_extraction({'records': [self.record]}, self.packet), [])
        del self.packet['entity_catalog']
        self.assertIn('missing_entity_catalog', {e['reason'] for e in validate_extraction({'records': []}, self.packet)})
