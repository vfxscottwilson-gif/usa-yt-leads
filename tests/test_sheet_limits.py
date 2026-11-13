import json
import unittest
from src.sheets import Sheets, SheetsError, sanitize_cell_value, sanitize_payload, CELL_LIMIT

class CellLimitTests(unittest.TestCase):
    def test_ascii_and_unicode_limit_includes_marker(self):
        for value in ['x'*60000, '\U0001f600'*30000]:
            safe=sanitize_cell_value(value)
            self.assertLessEqual(len(safe.encode('utf-16-le'))//2,CELL_LIMIT)
            self.assertTrue(safe.endswith('... [TRUNCATED]'))
        self.assertEqual(sanitize_cell_value(123),123)
        self.assertEqual(sanitize_cell_value('x'*49500),'x'*49500)

    def test_batch_and_grid_cells_are_guarded(self):
        result=sanitize_payload({'data':[{'range':'A1','values':[['x'*60000]]}],
            'requests':[{'updateCells':{'rows':[{'values':[{'userEnteredValue':{'stringValue':'y'*60000}}]}]}}]})
        self.assertLessEqual(len(result['data'][0]['values'][0][0]),CELL_LIMIT)
        self.assertLessEqual(len(result['requests'][0]['updateCells']['rows'][0]['values'][0]['userEnteredValue']['stringValue']),CELL_LIMIT)

    def test_memory_roundtrip_large_json_and_old_format(self):
        sheet=object.__new__(Sheets)
        sheet.headers={'Channel Memory':['Value','Key']}
        sheet.rows={'Channel Memory':[]}
        sheet.grow=lambda *args:None
        writes=[]
        sheet.write=lambda title,cell,values: writes.extend(values)
        original={'UCbig':{'text':'quotes " and unicode \U0001f600 '*10000},'UCsmall':{'n':1}}
        sheet.save_memory('Channel Memory',original)
        self.assertTrue(all(len(str(cell))<=CELL_LIMIT for row in writes for cell in row))
        self.assertEqual(sheet.memory('Channel Memory'),original)
        sheet.rows['Channel Memory'].pop(0)
        with self.assertRaises(SheetsError):sheet.memory('Channel Memory')

    def test_write_sanitizes_even_with_intercepted_call(self):
        sheet=object.__new__(Sheets)
        sent=[]
        sheet.call=lambda *args,**kwargs:sent.append(kwargs['body'])
        sheet.write('All Leads','A1',[['z'*70000]])
        self.assertLessEqual(len(sent[0]['data'][0]['values'][0][0]),CELL_LIMIT)

class FinalBoundaryTests(unittest.TestCase):
    def test_direct_call_sanitizes_values_before_http(self):
        from unittest.mock import Mock
        sheet=object.__new__(Sheets)
        sheet.base='https://sheets.googleapis.com/v4/spreadsheets/test'
        sheet.session=Mock()
        sheet.session.request.return_value.ok=True
        sheet.session.request.return_value.json.return_value={}
        sheet.call('POST','/values:batchUpdate',body={'data':[{'range':'A1','values':[['x'*60000]]}]})
        payload=sheet.session.request.call_args.kwargs['json']
        self.assertLessEqual(len(payload['data'][0]['values'][0][0]),CELL_LIMIT)
