"""Reproducible vocabulary analysis. Raw lyrics stay in ignored local data directories."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import importlib.metadata

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.manifold import TSNE
from sklearn.metrics.pairwise import cosine_similarity

from hiphop.text import clean_lyrics, tokens, name_key
from hiphop.paths import StudyPaths

VARIANT = re.compile(r'\b(remix|remaster(?:ed)?|instrumental|karaoke|acapella|a cappella|sped up|slowed|translation|tracklist|credits|discography|liner notes|booklet|album review|acceptance speech|press release|tour dates|interview|documentary|a conversation|reddit ama|studio session|snippet|unreleased|demo)\b|\(live\b|\blive (?:at|from|in)\b', re.I)


def signature_word_indices(artist, terms, scores, limit=10):
    """Skip the artist's own name components, stylizations, and possessives."""
    name = artist.replace('’', "'").replace('‘', "'")
    excluded = set()
    for spelling in (name, name.replace('$', 's')):
        excluded.update(tokens(spelling))
        excluded.update(tokens(name_key(spelling)))
    def is_own_name(word):
        normalized = word.removesuffix("'s")
        return normalized in excluded or name_key(normalized) in excluded
    return [i for i in np.argsort(-scores)
            if scores[i] > 0 and not is_own_name(str(terms[i]))][:limit]


def read_corpus(config, allow_partial, paths):
    source = json.loads((paths.source / 'source-info.json').read_text())
    expected = json.loads((paths.source / 'source-files.json').read_text())
    files = sorted((paths.historical).glob('train-*.parquet'))
    if len(files) != len(expected) and not allow_partial:
        raise SystemExit('Historical download is incomplete. Run hiphop fetch historical or use --allow-partial for a labeled preview.')
    cohort = {name_key(a['artist']):a for a in config['artists']}
    # The upstream cleaning sometimes deletes accented letters instead of transliterating them.
    for a in config['artists']:
        cohort.setdefault(name_key(a['artist'].encode('ascii','ignore').decode()), a)
    for alias, artist in {'thedixiechicks':'Dixie Chicks','thechicks':'Dixie Chicks',
                          'lilkim':'Lil’ Kim','puffdaddy':'Diddy','yasiinbey':'Mos Def'}.items():
        target = next((a for a in config['artists'] if a['artist']==artist), None)
        if target:
            cohort[alias]=target
    source_aliases = {'Shelley FKA DRAM':'D.R.A.M.','Jermaine Dupri':'JD',
                      'Boosie Badazz':"Lil' Boosie",'Diddy':'P. Diddy','Pras':'Pras Michel',
                      'Soulja Boy':"Soulja Boy Tell'em",'2 Live Crew':'The 2 Live Crew'}
    for alias, canonical in source_aliases.items():
        target = next((a for a in config['artists'] if a['artist']==canonical), None)
        if target:
            cohort[name_key(alias)] = target
    audit = Counter()
    manual_exclusions={(r['artist'],name_key(r['title'])) for r in json.loads((paths.references / 'exclusions.json').read_text())}
    raw_years = Counter()
    candidates = []
    for file in files:
        print('Reading',file.name,flush=True)
        offset = 0
        for batch in pq.ParquetFile(file).iter_batches(batch_size=4096):
            for row in batch.to_pylist():
                source_row = offset
                offset += 1
                audit['source_rows_scanned'] += 1
                raw_years[str(row['year'])] += 1
                if not all(isinstance(row.get(k),str) and row[k].strip() for k in ['artist','title','lyrics']) or row.get('year') is None:
                    audit['source_rows_missing_required_fields'] += 1
                    continue
                entry = cohort.get(name_key(row['artist']))
                if not entry:
                    continue
                candidates.append({**row, 'id':f'hf:{file.stem}:{source_row}',
                    'artist':entry['artist'],'genre':entry['genre'],
                    'source':'hf_historical','source_url':f'https://huggingface.co/datasets/{source["id"]}',
                    'release_date':None,'language':'en','original_artist':row['artist']})
    recent_status = []
    for file in sorted((paths.recent(config['as_of'])).glob('*.json')):
        data = json.loads(file.read_text())
        recent_status.append({k:data.get(k) for k in ['artist','complete','catalog_entries','errors','collected_at']})
        candidates.extend(data['songs'])
    # Prefer the earliest listed release when duplicate editions have different years.
    candidates.sort(key=lambda r:(int(r['year']),r['artist'],r['title'],r['id']))
    seen_text, seen_song = set(), set()
    rows = []
    for row in candidates:
        audit['cohort_candidates'] += 1
        year = int(row['year'])
        if (row['artist'],name_key(row['title'])) in manual_exclusions:
            audit['excluded_reviewed_non_song'] += 1
            continue
        if not config['start_year'] <= year <= int(config['as_of'][:4]):
            audit['excluded_outside_window'] += 1
            continue
        if row['source']=='hf_historical' and year > 2022:
            audit['excluded_historical_unverified_future_date'] += 1
            continue
        if VARIANT.search(row['title']):
            audit['excluded_variant_or_non_song_title'] += 1
            continue
        lines = clean_lyrics(row['lyrics'])
        word_list = tokens(' '.join(lines))
        if len(word_list) < config['min_words_per_song']:
            audit['excluded_short'] += 1
            continue
        fingerprint = hashlib.sha256(' '.join(word_list).encode()).hexdigest()
        song_key = (row['artist'], name_key(row['title']))
        if fingerprint in seen_text or song_key in seen_song:
            audit['excluded_duplicate'] += 1
            continue
        seen_text.add(fingerprint)
        seen_song.add(song_key)
        row['counts'] = Counter(word_list)
        row['unique_line_counts'] = Counter(tokens(' '.join(dict.fromkeys(lines))))
        row['n_tokens'] = len(word_list)
        row['fingerprint'] = fingerprint
        rows.append(row)
    audit['retained_songs'] = len(rows)
    present_recent = {r['artist'] for r in recent_status if r['complete']}
    expected_recent = {a['artist'] for a in config['artists'] if a['collect_recent']}
    status = {'historical_shards_downloaded':len(files),'historical_shards_expected':len(expected),
              'historical_complete':len(files)==len(expected),
              'recent_artists_complete':len(present_recent),'recent_artists_expected':len(expected_recent),
              'recent_pending_or_failed':sorted(expected_recent-present_recent),
              'recent_status':recent_status,'audit':dict(audit), 'raw_year_counts':dict(raw_years),
              'source_revision':source['sha']}
    return rows, status


def word_comparison(rows):
    counts = {'rap':Counter(),'other':Counter()}
    line_counts = {'rap':Counter(),'other':Counter()}
    song_counts = {'rap':Counter(),'other':Counter()}
    artist_sets = defaultdict(set)
    totals = Counter()
    song_totals = Counter()
    by_year = defaultdict(lambda:{'rap':Counter(),'other':Counter()})
    for row in rows:
        group = 'rap' if row['genre']=='rap' else 'other'
        counts[group].update(row['counts'])
        line_counts[group].update(row['unique_line_counts'])
        song_counts[group].update(row['counts'].keys())
        totals[group] += row['n_tokens']
        song_totals[group] += 1
        by_year[row['year']][group].update(row['counts'])
        if group=='rap':
            for w in row['counts']:
                artist_sets[w].add(row['artist'])
    if not totals['rap'] or not totals['other']:
        return {'words':[],'totals':dict(totals),'songs':dict(song_totals),'matched_years':[]}
    years = [y for y,c in by_year.items() if c['rap'] and c['other']]
    year_totals = {y:{g:sum(c.values()) for g,c in by_year[y].items()} for y in years}
    matched_rap_total = sum(year_totals[y]['rap'] for y in years)
    rap_line_total, other_line_total = (sum(line_counts[g].values()) for g in ['rap','other'])
    records = []
    # A scaled support floor plus cross-song and cross-artist support prevents rare-word explosions.
    floor = max(30, round(totals['rap'] * 1000 / 26_000_000))
    for word, count in counts['rap'].items():
        if count < floor or song_counts['rap'][word] < 10 or len(artist_sets[word]) < 5:
            continue
        other = counts['other'][word]
        rap_rate = count/totals['rap']
        other_rate = other/totals['other']
        # Tiny additive smoothing is only used for ratios, never displayed as observed counts.
        ratio = ((count+.5)/(totals['rap']+1))/((other+.5)/(totals['other']+1))
        matched_rap = sum(by_year[y]['rap'][word] for y in years)/matched_rap_total if years else 0
        matched_other = sum(year_totals[y]['rap']/matched_rap_total *
            (by_year[y]['other'][word]+.5)/(year_totals[y]['other']+1) for y in years) if years else 0
        line_ratio = ((line_counts['rap'][word]+.5)/(rap_line_total+1))/((line_counts['other'][word]+.5)/(other_line_total+1))
        records.append({'word':word,'rap_count':count,'other_count':other,
            'rap_per_10k':round(rap_rate*10000,4),'other_per_10k':round(other_rate*10000,4),
            'ratio':round(ratio,4),'year_matched_ratio':round(matched_rap/matched_other,4) if matched_other else None,
            'unique_line_ratio':round(line_ratio,4),'rap_songs':song_counts['rap'][word],
            'rap_artists':len(artist_sets[word]),'rap_song_pct':round(100*song_counts['rap'][word]/song_totals['rap'],3)})
    records.sort(key=lambda r:(-r['ratio'],r['word']))
    return {'words':records,'totals':dict(totals),'songs':dict(song_totals),
            'minimum_rap_count':floor,'matched_years':sorted(years)}


def artist_map(rows, min_songs):
    counts = defaultdict(Counter)
    song_counts = Counter()
    years = defaultdict(list)
    for row in rows:
        if row['genre']=='rap':
            counts[row['artist']].update(row['counts'])
            song_counts[row['artist']] += 1
            years[row['artist']].append(row['year'])
    names = sorted(a for a in counts if song_counts[a]>=min_songs)
    if len(names)<4:
        return []
    vectorizer = DictVectorizer()
    matrix = vectorizer.fit_transform([counts[a] for a in names])
    terms = vectorizer.get_feature_names_out()
    keep = np.asarray((matrix>0).sum(axis=0)).ravel() >= math.ceil(.1*len(names))
    terms = terms[keep]
    tfidf = TfidfTransformer(sublinear_tf=True).fit_transform(matrix[:,keep])
    similarities = cosine_similarity(tfidf)
    np.fill_diagonal(similarities,-1)
    n_components = min(50,tfidf.shape[0]-1,tfidf.shape[1]-1)
    reduced = TruncatedSVD(n_components=n_components, random_state=42).fit_transform(tfidf)
    xy = TSNE(n_components=2,perplexity=min(40,(len(names)-1)/3), random_state=42,
              init='pca',learning_rate='auto',max_iter=1500).fit_transform(reduced)
    result=[]
    for i, name in enumerate(names):
        v=tfidf.getrow(i).toarray().ravel()
        top=signature_word_indices(name, terms, v)
        neighbors=np.argsort(-similarities[i])[:5]
        result.append({'artist':name,'songs':song_counts[name], 'tokens':sum(counts[name].values()),
            'first_year':min(years[name]),'last_year':max(years[name]),
            'median_year':float(np.median(years[name])), 'x':round(float(xy[i,0]),4),'y':round(float(xy[i,1]),4),
            'words':[{'word':str(terms[j]),'score':round(float(v[j]),5)} for j in top if v[j]>0],
            'neighbors':[{'artist':names[j],'similarity':round(float(similarities[i,j]),4)} for j in neighbors]})
    return result


def run(root, allow_partial=False):
    paths = StudyPaths(root, 'language-of-hip-hop')
    paths.exports.mkdir(parents=True, exist_ok=True)
    config=json.loads((paths.config).read_text())
    rows,status=read_corpus(config,allow_partial,paths)
    if not rows:
        raise SystemExit('No retained songs yet.')
    meta=[{k:r.get(k) for k in ['id','artist','title','year','release_date','genre','source',
                               'source_url','n_tokens','fingerprint']} for r in rows]
    frame=pd.DataFrame(meta)
    (paths.processed).mkdir(parents=True,exist_ok=True)
    frame.to_parquet(paths.processed / 'song_index.parquet',index=False)
    coverage=frame.groupby(['year','genre','source']).agg(songs=('id','size'),artists=('artist','nunique'),tokens=('n_tokens','sum')).reset_index()
    coverage.to_csv(paths.exports / 'coverage.csv',index=False)
    artists=frame.groupby(['artist','genre']).agg(songs=('id','size'),tokens=('n_tokens','sum'),
                   first_year=('year','min'),last_year=('year','max')).reset_index()
    artists.to_csv(paths.exports / 'artists.csv',index=False)
    periods={}
    for label,lo,hi in [('all',1990,2026),('1990s',1990,1999),('2000s',2000,2009),
                        ('2010s',2010,2019),('2020s',2020,2026),('recent',2023,2026)]:
        periods[label]=word_comparison([r for r in rows if lo<=r['year']<=hi])
        pd.DataFrame(periods[label]['words']).to_csv(paths.exports / f'words-{label}.csv',index=False)
    tracked={'love','money','police','compton','drip','flex','skrrt','opps','trap','heart','pain','lit','vibe','gang'}
    for period in periods.values():
        tracked.update(w['word'] for w in period['words'][:40])
    trends=[]
    for year in range(1990,2027):
        selected=[r for r in rows if r['year']==year and r['genre']=='rap']
        c=Counter(); presence=Counter()
        for row in selected:
            c.update(row['counts']);presence.update(row['counts'].keys())
        total=sum(c.values())
        for word in sorted(tracked):
            trends.append({'year':year,'word':word,'count':c[word], 'songs':len(selected),
                'song_pct':round(presence[word]/len(selected)*100,3) if selected else None,
                'per_10k':round(c[word]/total*10000,4) if total else None})
    pd.DataFrame(trends).to_csv(paths.exports / 'trends.csv',index=False)
    print('Computing artist similarity',flush=True)
    mapping=artist_map(rows,config['min_songs_per_artist'])
    status['missing_cohort_artists']=sorted(set(a['artist'] for a in config['artists'])-set(frame.artist))
    roster=pd.read_csv(paths.references / 'pudding-artist-song-counts.csv')
    observed={name_key(r['artist']):r for r in artists.to_dict('records')}
    roster_rows=[]
    for original_name in roster.artist:
        lookup=name_key(original_name)
        if lookup=='youngjeezy':
            lookup='jeezy'
        matched=observed.get(lookup,{})
        roster_rows.append({'original_artist':original_name,'matched_artist':matched.get('artist'),
            'songs':matched.get('songs',0),'map_eligible':matched.get('songs',0)>=config['min_songs_per_artist']})
    pd.DataFrame(roster_rows).to_csv(paths.exports / 'pudding-roster-coverage.csv',index=False)
    status['original_roster_artists']=len(roster_rows)
    status['original_roster_artists_observed']=sum(r['songs']>0 for r in roster_rows)
    status['original_roster_artists_map_eligible']=sum(r['map_eligible'] for r in roster_rows)
    status['config_sha256']=hashlib.sha256((paths.config).read_bytes()).hexdigest()
    status['software_versions']={name:importlib.metadata.version(name) for name in ['numpy','pandas','pyarrow','scikit-learn']}
    status['complete']=status['historical_complete'] and not status['recent_pending_or_failed']
    status['coverage']=coverage.to_dict('records')
    status['cohort_size']=len(config['artists'])
    status['artists_observed']=int(frame.artist.nunique())
    status['rap_songs']=int((frame.genre=='rap').sum())
    status['other_songs']=int((frame.genre!='rap').sum())
    status['total_tokens']=int(frame.n_tokens.sum())
    status['as_of']=config['as_of']
    status['built_at']=datetime.now(timezone.utc).isoformat()
    (paths.exports / 'audit.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n')
    payload={'status':status,'periods':periods,'artists':mapping,'trends':trends,
             'artist_coverage':artists.to_dict('records')}
    # A local script file keeps the explorer usable without a server or network calls.
    output='window.HIPHOP_DATA = '+json.dumps(payload,ensure_ascii=False,allow_nan=False)+';\n'
    temporary=paths.web / 'data.js.tmp'
    temporary.write_text(output)
    temporary.replace(paths.web / 'data.js')
    index=paths.web / 'index.html'
    revision=hashlib.sha256(output.encode()).hexdigest()[:12]
    index.write_text(re.sub(r'src="data\.js(?:\?v=[a-f0-9]+)?"',f'src="data.js?v={revision}"',index.read_text()))
    print(json.dumps({k:status[k] for k in ['complete','rap_songs','other_songs','artists_observed','total_tokens']},indent=2))
