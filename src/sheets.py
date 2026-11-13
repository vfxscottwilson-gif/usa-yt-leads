import json
import time
from .models import HEADERS, REPORT_HEADERS, utcnow

CELL_LIMIT = 49500
TRUNCATED = '... [TRUNCATED]'


def sanitize_cell_value(value):
    if not isinstance(value, str):
        return value
    encoded = value.encode('utf-16-le', errors='replace')
    if len(encoded) // 2 <= CELL_LIMIT:
        return value
    return encoded[:(CELL_LIMIT-len(TRUNCATED))*2].decode('utf-16-le', errors='ignore') + TRUNCATED


def sanitize_payload(value):
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == 'values' and isinstance(item, list) and all(isinstance(row, list) for row in item):
                result[key] = [[sanitize_cell_value(cell) for cell in row] for row in item]
            elif key in ('stringValue', 'formulaValue'):
                result[key] = sanitize_cell_value(item)
            else:
                result[key] = sanitize_payload(item)
        return result
    return value


class SheetsError(Exception):
    pass


def reorder(header, rows, expected):
    """Re-map rows to the master column order BY HEADER NAME. Unknown columns are kept after the master columns.
    Returns (new_header, new_rows) or None when nothing needs to move."""
    if len(header) != len(set(header)):
        return None
    known = [h for h in header if h in expected]
    if known == [h for h in expected if h in header]:
        return None
    new_header = list(expected) + [h for h in header if h not in expected]
    index = {h: i for i, h in enumerate(header)}
    return new_header, [[row[index[h]] if h in index and index[h] < len(row) else '' for h in new_header] for row in rows]


class RateLimited(SheetsError):
    pass

def col(number):
    result = ''
    while number:
        number, rem = divmod(number - 1, 26)
        result = chr(65 + rem) + result
    return result

def quote(title):
    return "'" + title.replace("'", "''") + "'"

class Sheets:
    def __init__(self, sheet_id, credentials, cfg, niches):
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import AuthorizedSession
        self.session = AuthorizedSession(Credentials.from_service_account_info(credentials,
            scopes=['https://www.googleapis.com/auth/spreadsheets']))
        self.base = 'https://sheets.googleapis.com/v4/spreadsheets/' + sheet_id
        self.cfg, self.niches = cfg, niches
        self.headers, self.rows, self.tabs = {}, {}, {}

    def call(self, *args, **kwargs):
        # HTTP 429 means Google rejected the request without applying it, so waiting out the
        # per-minute write quota (60/min) and resending is safe even for appends.
        for wait in (0, 30, 60, 60, 60):
            time.sleep(wait)
            try:
                return self._call(*args, **kwargs)
            except RateLimited:
                continue
        raise RateLimited('Sheets HTTP 429: Google write quota (60 per minute) still exhausted after waiting; rerun later')

    def _call(self, method, path='', body=None, params=None, retry=True):
        # Ambiguous appends are never retried blindly; next startup reconciles by Contact ID.
        import requests
        body = sanitize_payload(body)
        for attempt in range(4 if retry else 1):
            if method != 'GET':  # stay under 60 write requests per minute
                time.sleep(max(0, 1.2 - (time.monotonic() - getattr(self, '_last_write', 0))))
                self._last_write = time.monotonic()
            try:
                response = self.session.request(method, self.base + path, json=body, params=params, timeout=60)
            except requests.RequestException:
                if not retry or attempt == 3:
                    raise SheetsError('Sheets network failure; restart safely to reconcile written contacts') from None
            else:
                if response.ok:
                    return response.json()
                if response.status_code == 429:
                    raise RateLimited('Sheets HTTP 429: write quota per minute reached')
                if response.status_code not in (500, 502, 503, 504) or not retry or attempt == 3:
                    hints = {400:'Invalid Sheets request. Inspect safe stack location for failing setup operation.',
                        401:'Service account authentication failed. Check JSON key and whether it was revoked.',
                        403:'Enable Google Sheets API in the service account project and share the sheet with its client_email as Editor.',
                        404:'Spreadsheet not found or not shared. Check GOOGLE_SHEET_ID and service account sharing.',
                        429:'Google Sheets rate limit reached. Wait and rerun.'}
                    try:  # Google's own reason (e.g. SERVICE_DISABLED, PERMISSION_DENIED) names the exact cause
                        err = response.json().get('error', {})
                        reason = f" Google says: {err.get('status', '')} - {err.get('message', '')}"
                    except ValueError:
                        reason = ''
                    raise SheetsError(f'Sheets HTTP {response.status_code} during {method} {path.split(chr(47))[1] if chr(47) in path else "spreadsheet metadata"}: ' + hints.get(response.status_code,'Google Sheets unavailable; retry later.') + reason)
            time.sleep(2 ** attempt)

    def read(self, title):
        data = self.call('GET', '/values/' + quote(title), params={'valueRenderOption': 'UNFORMATTED_VALUE'})
        return data.get('values', [])

    def write(self, title, cell, values, formula=False):
        self.call('POST', '/values:batchUpdate', body={'valueInputOption': 'USER_ENTERED' if formula else 'RAW',
            'data': [{'range': quote(title) + '!' + cell, 'values': [[sanitize_cell_value(v) for v in row] for row in values]}]})

    def setup(self):
        data = self.call('GET', params={'fields': 'sheets.properties,properties.title'})
        self.tabs = {s['properties']['title']: s['properties'] for s in data.get('sheets', [])}
        layouts = {'Dashboard': ['Metric', 'Value'], 'Daily Report': REPORT_HEADERS,
                   'All Leads': HEADERS, 'Needs Review': HEADERS}
        layouts.update({n['name']: HEADERS for n in self.niches})
        layouts.update({'Settings': ['Setting', 'Value'], 'Channel Memory': ['Key', 'Value'],
                        'Search Memory': ['Key', 'Value']})
        missing = [t for t in layouts if t not in self.tabs]
        if missing:
            self.call('POST', ':batchUpdate', body={'requests': [
                {'addSheet': {'properties': {'title': title, 'hidden': title.endswith('Memory')}}}
                for title in missing]})
            data = self.call('GET', params={'fields': 'sheets.properties'})
            self.tabs = {s['properties']['title']: s['properties'] for s in data['sheets']}
        formatting = [{'updateSpreadsheetProperties': {'properties': {'title': self.cfg['spreadsheet_title'],
                        'timeZone': self.cfg['timezone']}, 'fields': 'title,timeZone'}}]
        # New Sheets usually start with 26 columns. Expand BEFORE writing the 33-column header.
        expansion = []
        for title, expected in layouts.items():
            props = self.tabs[title]
            if props['gridProperties']['columnCount'] < len(expected):
                props['gridProperties']['columnCount'] = len(expected)
                expansion.append({'updateSheetProperties': {'properties': {'sheetId':props['sheetId'],
                    'gridProperties':{'columnCount':len(expected)}},'fields':'gridProperties.columnCount'}})
        if expansion:
            self.call('POST',':batchUpdate',body={'requests':expansion})
        for index, (title, expected) in enumerate(layouts.items()):
            values = self.read(title)
            if not values:
                self.write(title, 'A1', [expected])
                values = [expected]
            header = [str(h) for h in values[0]]
            aligned = False
            if self.cfg.get('align_headers') and expected is HEADERS and len(values) > 0:
                moved = reorder(header, values[1:], expected)
                if moved:
                    header, body = moved
                    width = max(len(header), self.tabs[title]['gridProperties']['columnCount'])
                    self.call('POST', ':batchUpdate', body={'requests': [{'updateSheetProperties': {'properties': {
                        'sheetId': self.tabs[title]['sheetId'], 'gridProperties': {'columnCount': width}},
                        'fields': 'gridProperties.columnCount'}}]})
                    self.tabs[title]['gridProperties']['columnCount'] = width
                    self.call('POST', '/values:batchClear', body={'ranges': [
                        f'{quote(title)}!A1:{col(max(len(values[0]), len(header)))}{len(values) + 5}']})
                    self.write(title, 'A1', [header])
                    self.grow(title, len(body) + 2)
                    for start in range(0, len(body), 300):
                        self.write(title, f'A{start + 2}', body[start:start + 300])
                    values, aligned = [header] + body, True
                    print(f'Aligned {title} to the master header ({len(body)} rows)', flush=True)
            new_fields = {'Score','Tier','Pitch Angle','Guessed Email','Personal LinkedIn','Company LinkedIn','Twitter And X','All Discovered Links','Link Sources','Scrapling Pages','Scrapling Failures','Browser Pages','Browser Failures','YouTube Panel Checks','YouTube Panel Blocks','YouTube Panel Timeouts'}
            missing = [h for h in expected if h not in header]
            if missing and set(missing).issubset(new_fields) and len(header)==len(set(header)):
                header += missing
                self.call('POST', ':batchUpdate', body={'requests':[{'updateSheetProperties':{
                    'properties':{'sheetId':self.tabs[title]['sheetId'],'gridProperties':{
                    'columnCount':max(len(header),self.tabs[title]['gridProperties']['columnCount'])}},
                    'fields':'gridProperties.columnCount'}}]})
                self.tabs[title]['gridProperties']['columnCount']=max(len(header),self.tabs[title]['gridProperties']['columnCount'])
                self.write(title,'A1',[header])
            if len(header) != len(set(header)) or any(h not in header for h in expected):
                raise SheetsError(f'{title}: required header missing or duplicated; restore header names')
            self.headers[title], self.rows[title] = header, values[1:]
            if aligned and 'ID' in header and 'Channel ID' in header:
                self.repair_ids(title, 2)   # ID formulas point at the Channel ID column, which moved
            sid = self.tabs[title]['sheetId']
            # Never shrink existing grids or erase unknown columns or user notes.
            width = max(self.tabs[title]['gridProperties']['columnCount'], len(header))
            formatting.extend([
                {'updateSheetProperties': {'properties': {'sheetId': sid, 'index': index,
                  'gridProperties': {'frozenRowCount': 1, 'columnCount': width}},
                  'fields': 'index,gridProperties.frozenRowCount,gridProperties.columnCount'}},
                {'repeatCell': {'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1},
                  'cell': {'userEnteredFormat': {'textFormat': {'bold': True},
                           'backgroundColor': {'red': .82, 'green': .9, 'blue': .97}}},
                  'fields': 'userEnteredFormat'}}])
        # Formatting is bounded by tab count, not row count.
        self.call('POST', ':batchUpdate', body={'requests': formatting})
        self.write('Settings', 'A2', [[key, json.dumps(value)] for key, value in self.cfg.items()])

    def records(self, title):
        return [dict(zip(self.headers[title], row)) for row in self.rows[title]]

    def memory(self, title):
        import hashlib
        result, chunks = {}, {}
        try:
            for row in self.records(title):
                key = row.get('Key')
                if not key:
                    continue
                value = json.loads(row['Value'])
                if isinstance(value, dict) and set(value) == {'__yt_memory_chunk_v1'}:
                    chunks.setdefault(key, []).append(value['__yt_memory_chunk_v1'])
                else:
                    if key in result:
                        raise ValueError('Duplicate memory')
                    result[key] = value
            for key, parts in chunks.items():
                parts.sort(key=lambda part: part['index'])
                total, digest = parts[0]['total'], parts[0]['sha256']
                if key in result or len(parts) != total or [x['index'] for x in parts] != list(range(total)):
                    raise ValueError('Incomplete chunks')
                if any(x['total'] != total or x['sha256'] != digest for x in parts):
                    raise ValueError('Inconsistent chunks')
                payload = ''.join(x['data'] for x in parts)
                if hashlib.sha256(payload.encode()).hexdigest() != digest:
                    raise ValueError('Memory checksum mismatch')
                result[key] = json.loads(payload)
        except (ValueError, KeyError, TypeError):
            raise SheetsError(f'{title}: corrupt or incomplete memory; restore from backup before continuing') from None
        return result

    def save_memory(self, title, records):
        import hashlib
        ordered = []
        for key, value in records.items():
            payload = json.dumps(value, separators=(',', ':'))
            if len(payload) <= CELL_LIMIT:
                ordered.append([key, payload])
            else:
                parts = [payload[i:i+18000] for i in range(0, len(payload), 18000)]
                digest = hashlib.sha256(payload.encode()).hexdigest()
                for index, part in enumerate(parts):
                    encoded = json.dumps({'__yt_memory_chunk_v1': dict(index=index, total=len(parts), sha256=digest, data=part)})
                    if len(encoded) > CELL_LIMIT:
                        raise SheetsError('Memory chunk exceeds cell limit')
                    ordered.append([key, encoded])
        header = self.headers[title]
        values = [[dict(Key=k, Value=v).get(h, '') for h in header] for k, v in ordered]
        self.grow(title, len(values) + 1)
        for start in range(0, len(values), 300):
            self.write(title, f'A{start+2}', values[start:start+300])
        if len(self.rows[title]) > len(values):
            self.call('POST', '/values:batchClear', body={'ranges': [
                f'{quote(title)}!A{len(values)+2}:{col(len(header))}{len(self.rows[title])+1}']})
        self.rows[title] = values

    def grow(self, title, rows):
        props = self.tabs[title]
        current = props['gridProperties']['rowCount']
        if rows > current:
            self.call('POST', ':batchUpdate', body={'requests': [{'appendDimension': {
                'sheetId': props['sheetId'], 'dimension': 'ROWS', 'length': rows - current + 100}}]})
            props['gridProperties']['rowCount'] = rows + 100

    def append(self, title, records):
        if not records:
            return None
        header = self.headers[title]
        # Fail closed if a human or another process inserted/appended/reordered data after startup.
        # This is detection, not a distributed lock; only one writer is supported.
        live = self.read(title)
        if not live or [str(h) for h in live[0]] != header:
            raise SheetsError(f'{title}: headers changed during run; retry after edits finish')
        live_ids = [dict(zip(header,r)).get('Contact ID') for r in live[1:]] if 'Contact ID' in header else None
        cached_ids = [dict(zip(header,r)).get('Contact ID') for r in self.rows[title]] if live_ids is not None else None
        if len(live)-1 != len(self.rows[title]) or live_ids != cached_ids:
            # Someone edited the tab during the run (rows added, deleted or sorted). Appending at the real bottom
            # never touches existing rows, so adopt the live rows and skip leads already present instead of crashing.
            self.rows[title] = live[1:]
            known = set(live_ids or [])
            records = [r for r in records if not r.get('Contact ID') or r.get('Contact ID') not in known]
            if not records:
                return None
        values = [[sanitize_cell_value(row.get(h, '')) for h in header] for row in records]
        start = len(self.rows[title]) + 2
        self.grow(title, start + len(values))
        # Fixed ranges + exclusive workflow are idempotent on retries. Do not run multiple writers.
        self.write(title, f'A{start}', values)
        self.rows[title].extend(values)
        if 'Channel ID' in header:
            self.repair_ids(title, start)
        return start, start + len(values) - 1

    def repair_ids(self, title, start=2, end=None):
        header = self.headers[title]
        ids, channel = col(header.index('ID')+1), col(header.index('Channel ID')+1)
        stop = end if end is not None else len(self.rows[title]) + 1
        if stop > self.cfg['max_formula_rows']:
            raise SheetsError('Formula row safety cap reached; increase max_formula_rows')
        formulas = []
        for r in range(start, stop+1):
            # First appearance only. Later discoveries remain at the bottom with blank display ID.
            formulas.append([f'=IF({channel}{r}="","",IF(COUNTIF({channel}$2:{channel}{r},{channel}{r})=1,'
                f'COUNTUNIQUE(FILTER({channel}$2:{channel}{r},{channel}$2:{channel}{r}<>"")),""))'])
        for offset in range(0, len(formulas), 300):
            self.write(title, f'{ids}{start+offset}', formulas[offset:offset+300], formula=True)

    def channel_ids(self, title):
        """Channel IDs that are in the tab RIGHT NOW (live read, so rows you moved by hand are respected)."""
        i = self.headers[title].index('Channel ID')
        return {str(r[i]) for r in self.read(title)[1:] if len(r) > i and r[i]}

    def remove_review_duplicates(self):
        """One lead, one place: delete Needs Review rows whose channel is already in All Leads. Never touches All Leads."""
        in_all = self.channel_ids('All Leads')
        header, live = self.headers['Needs Review'], self.read('Needs Review')
        if not live or [str(h) for h in live[0]] != header:
            raise SheetsError('Needs Review: headers changed during run; retry after edits finish')
        i = header.index('Channel ID')
        doomed = sorted((n for n, r in enumerate(live[1:], 2) if len(r) > i and str(r[i]) in in_all), reverse=True)
        if not doomed:
            return 0
        sid = self.tabs['Needs Review']['sheetId']
        for start in range(0, len(doomed), 100):   # bottom rows first, so the remaining row numbers stay valid
            self.call('POST', ':batchUpdate', body={'requests': [{'deleteDimension': {'range': {
                'sheetId': sid, 'dimension': 'ROWS', 'startIndex': n - 1, 'endIndex': n}}} for n in doomed[start:start + 100]]})
        gone = set(doomed)
        self.rows['Needs Review'] = [r for n, r in enumerate(live[1:], 2) if n not in gone]
        if self.rows['Needs Review'] and 'ID' in header:
            self.repair_ids('Needs Review', 2)
        return len(doomed)

    def validate_identity(self, title):
        header = self.headers[title]
        live = self.read(title)
        if not live or live[0] != header:
            raise SheetsError('Headers changed during run; retry after edits finish')
        actual = [dict(zip(header, row)).get('Contact ID') for row in live[1:]]
        expected = [dict(zip(header, row)).get('Contact ID') for row in self.rows[title]]
        if actual != expected:
            # Rows moved since startup: re-read positions from the live tab so a status update can never hit the wrong row.
            self.rows[title] = live[1:]

    def patch_contact(self, title, contact, changes):
        self.validate_identity(title)
        header = self.headers[title]
        for number, row in enumerate(self.rows[title], 2):
            record = dict(zip(header, row))
            if record.get('Contact ID') == contact:
                for key, value in changes.items():
                    self.write(title, f'{col(header.index(key)+1)}{number}', [[value]])
                    while len(row) < len(header):
                        row.append('')
                    row[header.index(key)] = value

    def patch_channel_status(self, cid, status, reason, checked):
        data = []
        for title in ['All Leads']+[n['name'] for n in self.niches]:
            header = self.headers[title]
            if any(dict(zip(header,row)).get('Channel ID') == cid for row in self.rows[title]):
                self.validate_identity(title)
            for number,row in enumerate(self.rows[title],2):
                if dict(zip(header,row)).get('Channel ID') != cid:
                    continue
                for key,value in {'Current Qualification':status,'Qualification Checked At':checked,
                                  'Review Reason':reason}.items():
                    data.append({'range':f'{quote(title)}!{col(header.index(key)+1)}{number}','values':[[value]]})
                    while len(row)<len(header):
                        row.append('')
                    row[header.index(key)] = value
        for start in range(0,len(data),300):
            self.call('POST','/values:batchUpdate',body={'valueInputOption':'RAW','data':data[start:start+300]})

    def export_local(self, directory):
        import csv
        directory.mkdir(parents=True, exist_ok=True)
        for title in ('All Leads', 'Needs Review', 'Daily Report'):
            # Read evaluated formula results for exported snapshots, not the RAW-write cache.
            live = self.read(title)
            header, values = (live[0], live[1:]) if live else (self.headers[title], [])
            with (directory / (title.replace(' ', '_') + '.csv')).open('w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                for row in values:
                    # CSV spreadsheet injection defense; RAW Sheets writes already avoid interpretation.
                    writer.writerow(["'" + x if isinstance(x, str) and x.startswith(('=', '+', '-', '@')) else x for x in row])
