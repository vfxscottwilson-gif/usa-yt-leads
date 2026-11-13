import json
import os
import uuid
from collections import Counter
from datetime import timedelta
from .config import ROOT, load
from .contacts import Research
from .discovery import discover
from .names import infer_person, guess_email
from .scoring import assess
from .models import contact_id, iso, next_delay, parse, utcnow
from .qualification import precheck, evaluate
from .reporting import report, dashboard, local_time
from .sheets import Sheets
from .youtube import YouTube, BudgetStop, YouTubeError

def build_rows(channel, evaluation, research, cfg, run_id, now):
    cid = channel['id']
    person = cfg['people'].get(cid, {})
    if not person and research.get('people'):
        person = research['people'][0]
    # Manually researched people must include a source, never infer identity from email usernames.
    full_name = person.get('full_name', '') if person.get('source') else ''
    first_name = (person.get('first_name') or full_name.split(' ')[0]) if full_name else ''
    person_source = person.get('source', '')
    if not full_name:  # fall back to a real first name found in the channel title ("Travel with Dave" -> Dave)
        first_name, full_name = infer_person(channel['snippet']['title'])
        person_source = 'Inferred from channel title' if full_name else ''
    guess = guess_email(first_name, research.get('guess_domain', ''))
    base = {'Channel Name':channel['snippet']['title'], 'Full Name':full_name or 'Team',
        'First Name':first_name or 'Team', 'Guessed Email':guess,
        'Designation':person.get('designation', '') if full_name else '',
        'YouTube Link':'https://www.youtube.com/channel/' + cid,
        'Niche':evaluation['niche'], 'Subscribers':int(channel.get('statistics',{}).get('subscriberCount',0)) or '',
        'Videos Checked':evaluation['videos_checked'], 'Videos Meeting View Threshold':evaluation['videos_above'],
        'Average Views':evaluation['average_views'], 'Long Uploads In Activity Window':len(evaluation['active']),
        'Last Upload':evaluation['last_upload'],
        'Suggested Editing Quote':cfg['quote_base_usd'] or '',
        'Last Checked':local_time(now,cfg), 'Email Added At':local_time(now,cfg),
        'Qualification Checked At':local_time(now,cfg),
        'Channel ID':cid, 'Run ID':run_id,
        'Phone Number':chr(10).join(research['phones']),
        'Business Address':person.get('business_address','') if person.get('source') else '',
        'Notes':evaluation.get('location_note','') + f"{len(evaluation['active'])} observed long uploads in {cfg['activity_days']} days; "
            f"{evaluation['videos_above']} of {evaluation['videos_checked']} sampled long videos have "
            f"at least {cfg['min_video_views']:,} views. "
            + ('Preferred upload activity. ' if len(evaluation['active']) >= cfg['preferred_long_uploads'] else 'Minimum upload activity. ')
            + 'Long format uses duration as a proxy. Niche is keyword classified. '
            + research.get('research_notes','') + ' ' + ('Team page for research: ' + research['team_pages'][0] if research['team_pages'] else ''),
        **research['links']}
    extra = assess(channel, evaluation, research)
    if cfg['quote_base_usd']:  # a fixed quote set in settings wins over the estimate
        extra.pop('Suggested Editing Quote', None)
    base.update(extra)
    contacts = list(research['contacts'].values()) or [dict(email='',source='',supported=True,
            evidence='No public email located within research budget')]
    result = []
    for contact in contacts:
        row = dict(base)
        row.update({'Email':contact['email'], 'Contact Source':contact['source'],
            'Evidence Note':contact['evidence'] +
                ('; Person source: ' + person_source + '; named person is not proven inbox owner' if full_name else '') +
                ('; Guessed Email is an unverified first-name pattern' if guess else ''),
            'Contact ID':contact_id(cid,contact['email']),
            'Email Status':'Published Contact' if contact['email'] and contact['supported'] else
                ('Needs Verification' if contact['email'] else 'Not Found')})
        # Qualification depends on the CHANNEL (subscribers, views, uploads, country). An email we could not tie to the
        # creator is shown in Email Status ("Needs Verification"); it no longer pushes a qualified channel into Needs Review.
        reason = evaluation['reason']
        row['Review Reason'] = reason
        row['Current Qualification'] = 'Qualified' if not reason else 'Needs Review'
        result.append(row)
    return result

def run(check_only=False):
    cfg, niches = load()
    if check_only:
        print('Configuration valid. No APIs called and no spreadsheet changed.')
        return 0
    for secret in ('YOUTUBE_API_KEY','GOOGLE_SERVICE_ACCOUNT_JSON','GOOGLE_SHEET_ID'):
        if not os.environ.get(secret):
            raise ValueError(f'Missing {secret}; follow START_HERE.md')
    try:
        credentials = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
    except ValueError:
        raise ValueError('GOOGLE_SERVICE_ACCOUNT_JSON must contain the complete JSON object') from None
    run_id = utcnow().strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    start = utcnow()
    deadline = start + timedelta(minutes=cfg['max_runtime_minutes'])
    output = ROOT / 'output' / run_id
    output.mkdir(parents=True, exist_ok=True)
    metrics = Counter()
    metrics['rejections'], metrics['niche_new'] = Counter(), Counter()
    sheet = Sheets(os.environ['GOOGLE_SHEET_ID'],credentials,cfg,niches)
    sheet.setup()
    # Recover a crash between RAW data commit and formula installation without rewriting all formulas.
    for title in ['All Leads','Needs Review'] + [n['name'] for n in niches]:
        seen_ids = set()
        for row_number,row in enumerate(sheet.records(title),2):
            cid = row.get('Channel ID')
            if cid and cid not in seen_ids and row.get('ID','') == '':
                sheet.repair_ids(title,row_number,end=row_number)
            seen_ids.add(cid)
    if cfg.get('remove_review_duplicates', True):   # one lead, one place
        removed = sheet.remove_review_duplicates()
        if removed:
            print(f'Removed {removed} Needs Review rows whose channel is already in All Leads', flush=True)
    memory = sheet.memory('Channel Memory')
    searches = sheet.memory('Search Memory')
    existing = {title:{r.get('Contact ID') for r in sheet.records(title)}
                for title in ['All Leads','Needs Review'] + [n['name'] for n in niches]}
    qualified_ids = {r.get('Channel ID') for r in sheet.records('All Leads') if r.get('Channel ID')}
    # Your decision sticks: a channel that is in one tab is never added to the other. Move a row between tabs by hand
    # and the automation will not bring the channel back; it only appends new contacts of channels already in All Leads.
    # Review approval confirms format only. It never bypasses numeric or country filters.
    approved = {r.get('Channel ID') for r in sheet.records('Needs Review')
                if str(r.get('Review Decision','')).strip().lower() == 'approve'}
    denied = {r.get('Channel ID') for r in sheet.records('Needs Review')
              if str(r.get('Review Decision','')).strip().lower() == 'reject'}
    confirmed = set(cfg['confirmed_talking_head_channel_ids']) | approved
    api, research = YouTube(os.environ['YOUTUBE_API_KEY'],cfg,metrics), Research(cfg,metrics)
    ranges, staged = [], []
    status, error = 'Complete', ''

    def checkpoint():
        nonlocal staged
        # Contacts first, memory second. On restart deduplicate against actual sheet rows.
        # Live read at every checkpoint: a lead you moved by hand a minute ago counts, however old the lead or the run is.
        in_all = sheet.channel_ids('All Leads')
        review_only = sheet.channel_ids('Needs Review') - in_all
        for title in ['All Leads','Needs Review'] + [n['name'] for n in niches]:
            rows = []
            for row in staged:
                qualified = row['Current Qualification'] == 'Qualified'
                belongs = (title == 'All Leads' and qualified) or (title == 'Needs Review' and not qualified) or (
                    qualified and title == row['Niche'])
                if title == 'Needs Review' and row['Channel ID'] in in_all:
                    belongs = False   # already in All Leads
                elif title != 'Needs Review' and row['Channel ID'] in review_only:
                    belongs = False   # waiting in Needs Review for your decision
                if belongs and row['Contact ID'] not in existing[title]:
                    rows.append(row)
                    existing[title].add(row['Contact ID'])
            block = sheet.append(title,rows)
            if block:
                ranges.append((title,*block))
                if title == 'All Leads':
                    metrics['contact_rows_added'] += len(rows)
                    metrics['new_emails'] += sum(bool(r['Email']) for r in rows)
                elif title == 'Needs Review':
                    metrics['review_rows_added'] += len(rows)
        sheet.save_memory('Channel Memory',memory)
        sheet.save_memory('Search Memory',searches)
        (output/'channel_memory.json').write_text(json.dumps(memory,indent=2),encoding='utf-8')
        staged = []

    try:
        candidates = discover(api,cfg,niches,searches,memory,metrics,deadline)
        for cid in candidates:
            memory.setdefault(cid,dict(status='pending',attempts=0))
        checkpoint()
        new, due = [], []
        for cid, item in memory.items():
            if cid in denied:
                continue
            if item.get('status') == 'pending':
                new.append(cid)
            elif item.get('rule_version') != cfg['rule_version']:
                due.append(cid)
            elif cid in approved and item.get('status') != 'qualified':
                due.append(cid)
            elif item.get('next_review') and parse(item['next_review']) <= utcnow():
                due.append(cid)
            elif cid in candidates:
                metrics['duplicates_skipped'] += 1
        due.sort(key=lambda cid: memory[cid].get('next_review',''))
        old_cap = int(cfg['max_channels_per_run']*cfg['recheck_fraction'])
        selected_old = due[:old_cap]
        metrics['rechecks_deferred'] = max(0,len(due)-len(selected_old))
        # Interleave a small old queue. It never consumes the entire evaluation budget.
        fresh_queue = new[:cfg['max_channels_per_run']-len(selected_old)]
        old_queue = list(selected_old)
        selected = []
        stride = max(1,int((1-cfg['recheck_fraction'])/cfg['recheck_fraction'])) if cfg['recheck_fraction'] else len(fresh_queue)+1
        while fresh_queue or old_queue:
            selected.extend(fresh_queue[:stride])
            del fresh_queue[:stride]
            if old_queue:
                selected.append(old_queue.pop(0))
        for offset in range(0,len(selected),50):
            if utcnow() >= deadline:
                status = 'Partial Runtime Limit'
                break
            batch = selected[offset:offset+50]
            channels = api.channels(batch)
            for cid in batch:
                if utcnow() >= deadline:
                    status = 'Partial Runtime Limit'
                    break
                item = memory[cid]
                old = cid in selected_old
                metrics['old_channels_checked' if old else 'new_channels_checked'] += 1
                channel = channels.get(cid)
                if not channel:
                    outcome, reason = 'review','Channel unavailable; existing rows retained'
                    if cid in qualified_ids:
                        sheet.patch_channel_status(cid,'Unavailable',reason,local_time(utcnow(),cfg))
                    item.update(status=outcome,reason=reason,next_review=iso(utcnow()+timedelta(days=20)),checked=iso(),rule_version=cfg['rule_version'])
                    continue
                outcome, reason = precheck(channel,cfg)
                if outcome == 'rejected':
                    metrics['rejections'][reason] += 1
                    if cid in qualified_ids:
                        sheet.patch_channel_status(cid,'No Longer Meets Filters',reason,local_time(utcnow(),cfg))
                    attempts = item.get('attempts',0)
                    item.update(status=outcome,checked=iso(),reason=reason,attempts=attempts+1,rule_version=cfg['rule_version'],
                        next_review=iso(utcnow()+timedelta(days=next_delay(attempts,cfg))))
                    continue
                try:
                    videos, complete = api.videos(channel['contentDetails']['relatedPlaylists']['uploads'])
                    evaluation = evaluate(channel,videos,complete,cfg,niches,cid in confirmed)
                except YouTubeError:
                    metrics['rejections']['Transient API inspection failure; queued'] += 1
                    continue
                if outcome == 'review' and evaluation['status'] != 'rejected':
                    evaluation['status'] = 'review'
                    evaluation['reason'] = '; '.join(filter(None,[reason,evaluation['reason']]))
                if cid in qualified_ids:
                    sheet.patch_channel_status(cid,{'qualified':'Qualified','review':'Needs Review',
                        'rejected':'No Longer Meets Filters'}[evaluation['status']],evaluation['reason'],local_time(utcnow(),cfg))
                if evaluation['status']=='rejected':
                    metrics['rejections'][evaluation['reason']] += 1
                else:
                    result = research.collect(channel,videos)
                    for rel in result.get('related', []):  # same person's other channels; judged by the normal filters next run
                        rid = rel.split('/')[-1] if rel.startswith('channel/') else api.resolve_handle(rel)
                        if rid and rid not in memory:
                            memory[rid] = dict(status='pending', attempts=0, related_to=cid)
                    rows = build_rows(channel,evaluation,result,cfg,run_id,utcnow())
                    staged.extend(rows)
                    if evaluation['status']=='qualified' and cid not in qualified_ids:
                        metrics['new_qualified_leads'] += 1
                        metrics['niche_new'][evaluation['niche']] += 1
                        if old:
                            metrics['old_newly_qualified'] += 1
                        qualified_ids.add(cid)
                        for fid in api.featured(cid):  # snowball: judged by the normal filters on a later run
                            if fid not in memory:
                                memory[fid] = dict(status='pending', attempts=0, featured_by=cid)
                    if result['failure']:
                        item['enrichment_retry'] = iso(utcnow()+timedelta(days=cfg['website_retry_days']))
                    else:
                        item.pop('enrichment_retry',None)
                attempts = item.get('attempts',0)
                delay = cfg['accepted_contact_refresh_days'] if evaluation['status']=='qualified' else next_delay(attempts,cfg)
                if item.get('enrichment_retry') and evaluation['status']!='rejected':
                    delay = min(delay,cfg['website_retry_days'])
                item.update(status=evaluation['status'],reason=evaluation['reason'],checked=iso(),rule_version=cfg['rule_version'],
                    attempts=attempts+1,next_review=iso(utcnow()+timedelta(days=delay)))
                if (metrics['new_channels_checked']+metrics['old_channels_checked']) % cfg['checkpoint_channels']==0:
                    checkpoint()
        checkpoint()
    except BudgetStop:
        status = 'Partial API Budget'
        checkpoint()
    except Exception as exc:
        # Never emit request URLs, credentials, or HTTP response bodies.
        status, error = 'Failed', type(exc).__name__ + ': processing stopped; inspect setup and private artifacts'
        raise
    finally:
        end = utcnow()
        try:
            report(sheet,metrics,run_id,start,end,status,error,ranges,cfg)
            dashboard(sheet,end,cfg)
            sheet.export_local(output)
        except Exception:
            status, error = 'Failed Reporting', 'Report or dashboard update failed; saved lead rows are retained'
            raise
        finally:
            safe = {k:dict(v) if isinstance(v,Counter) else v for k,v in metrics.items()}
            (output/'run_summary.json').write_text(json.dumps(dict(run_id=run_id,status=status,
                error=error,metrics=safe,row_ranges=ranges,start=iso(start),end=iso(end)),indent=2),encoding='utf-8')
    print(f"Run {run_id}: {status}. New qualified channels: {metrics['new_qualified_leads']}; "
          f"new published email rows: {metrics['new_emails']}; review rows: {metrics['review_rows_added']}.")
    return 0
