/* All source-derived text is inserted through textContent. Local lyric text is loaded separately from the aggregate exports. */
const data = window.RHYME_DATA;
const $ = id => document.getElementById(id);
const fmt = (value, digits = 1) => value == null ? '—' : Number(value).toLocaleString('en-US', {maximumFractionDigits: digits, minimumFractionDigits: digits});
function node(tag, text, className) { const el = document.createElement(tag); if (text != null) el.textContent = text; if (className) el.className = className; return el; }
function stat(container, value, label, digits = 1) { const el = node('div', null, 'stat'); el.append(node('b', fmt(value, digits)), node('span', label)); container.append(el); }
for (const album of data.albums) {
  const m = album.metrics, card = node('article', null, 'card ' + album.slug);
  card.append(node('div', album.artist, 'artist'), node('h3', album.album));
  const stats = node('div', null, 'stats');
  stat(stats, m.mean_rating, 'Mean rhyme rating'); stat(stats, m.median_rating, 'Median rating');
  stat(stats, m.mean_syllables, 'Mean credited syllables', 2); stat(stats, m.total_rhymed_syllables, 'Total credited syllables', 0);
  stat(stats, m.weighted_syllables_per_100_lines, 'Weighted syllables / 100 lines'); stat(stats, m.linked_line_percent, 'Lines with incoming link (%)');
  card.append(stats, node('p', `${m.rhyme_before_repeat_links} rhymes before repetition · ${m.repeat_only_links} repetition-only connections · ${m.tentative_slant_links} selected tentative slants`, 'note'), node('p', `${m.marked_adlib_lines} lines with marked ad-libs separated · ${m.adlib_adjusted_lines} unmarked endpoints moved · ${m.adlib_unresolved_lines} kept`, 'note'), node('p', `${album.scored_tracks} scored tracks · ${m.eligible_lines} verse lines · ${m.rhyme_links} links · ${fmt(100 * m.known_endings / m.eligible_lines)}% known endings`, 'note'));
  $('album-cards').append(card);
}
for (const album of data.albums) { const option = node('option', album.album); option.value = album.album; $('album-filter').append(option); }
function renderSongs() {
  $('song-table').replaceChildren();
  for (const album of data.albums.filter(a => $('album-filter').value === 'all' || a.album === $('album-filter').value)) {
    for (const song of album.songs) {
      const row = node('tr'), title = node('td', `${String(song.track).padStart(2, '0')}  ${song.title}`), m = song.metrics;
      title.append(node('small', `${album.artist} · ${album.album}`)); row.append(title);
      for (const [key, digits] of [['eligible_lines',0],['rhyme_links',0],['mean_rating',1],['median_rating',0],['mean_syllables',2],['median_syllables',0],['total_rhymed_syllables',0],['weighted_syllables_per_100_lines',1]]) row.append(node('td', fmt(m[key], digits)));
      $('song-table').append(row);
    }
  }
}
$('album-filter').addEventListener('change', renderSongs); renderSongs();
for (const album of data.albums) for (const song of album.songs) {
  const option = node('option', `${album.artist} — ${song.title}`); option.value = `${album.album}|${song.track}`; $('song-picker').append(option);
}
function schemeLetter(value) {
  if (value == null) return '—';
  let label = '', n = value;
  while (n > 0) { n--; label = String.fromCharCode(65 + n % 26) + label; n = Math.floor(n / 26); }
  return label;
}
function connectionText(syllables, rating, kind, repeated = 0) {
  if (kind === 'repetition') return `${repeated} repeated syllable${repeated === 1 ? '' : 's'} · no credit`;
  const prefix = kind === 'slant' ? 'Possible slant · ' : '';
  return `${prefix}${syllables} ${kind === 'slant' ? 'aligned' : 'credited'} syllable${syllables === 1 ? '' : 's'} · ${fmt(rating,0)}/100${repeated ? ` · ${repeated} repeated, no credit` : ''}${kind === 'slant' ? ' · excluded from main score' : ''}`;
}
function selectPair(current, partner, syllables, rating, kind, repeated) {
  for (const row of document.querySelectorAll('.pattern-line')) row.classList.remove('is-active', 'is-partner');
  const currentRow = $(`pattern-${current.index}`), partnerRow = $(`pattern-${partner.index}`);
  currentRow.classList.add('is-active'); partnerRow.classList.add('is-partner');
  $('selected-pair').hidden = false;
  $('selected-pair').textContent = `Line ${partner.source_line} ↔ line ${current.source_line} · ${connectionText(syllables,rating,kind,repeated)}`;
  partnerRow.scrollIntoView({behavior:'smooth', block:'nearest'}); partnerRow.focus({preventScroll:true});
}
function renderLines() {
  const [album, track] = $('song-picker').value.split('|');
  const lines = data.line_records.filter(l => l.album === album && l.track === Number(track));
  const song = data.albums.find(a => a.album === album)?.songs.find(s => s.track === Number(track));
  const m = song?.metrics;
  $('inspector-summary').textContent = m ? `${m.rhyme_links} scored links · ${m.repeat_only_links} repetition-only · ${m.tentative_slant_links} selected tentative slants. Ad-libs: ${m.marked_adlib_lines} marked lines separated, ${m.adlib_adjusted_lines} unmarked endpoints moved, ${m.adlib_unresolved_lines} unresolved candidates kept.` : '';
  const lyrics = (window.RHYME_LYRICS || []).find(s => s.album === album && s.track === Number(track));
  const textByIndex = new Map((lyrics?.lines || []).map(l => [l.index,l]));
  const includeSlants = $('show-slants').checked, original = $('show-original').checked;
  const scheme = l => includeSlants ? l.expanded_scheme : l.scheme;
  $('lyric-note').hidden = Boolean(lyrics); $('selected-pair').hidden = true;
  $('line-grid').replaceChildren(); let section = null, verse;
  const counts = new Map();
  for (const line of lines) if (scheme(line) != null && !counts.has(scheme(line))) counts.set(scheme(line), counts.size);
  for (const line of lines) {
    const local = textByIndex.get(line.index), familyId = scheme(line);
    if (line.section !== section) {
      section = line.section; verse = node('div', null, 'pattern-verse');
      const heading = node('div', null, 'verse-heading'); heading.append(node('h3', local?.heading || `Verse section ${section}`));
      const sequence = node('div', null, 'scheme-sequence'); sequence.setAttribute('aria-label', 'Rhyme pattern in line order');
      for (const member of lines.filter(l => l.section === section)) {
        const value = scheme(member), chip = node('span', schemeLetter(value), 'scheme-chip');
        if (value != null) chip.style.setProperty('--scheme-color', `var(--scheme-${counts.get(value) % 6})`);
        chip.title = `Line ${member.source_line}: ${value == null ? 'unlinked' : 'family ' + schemeLetter(value)}`; sequence.append(chip);
      }
      heading.append(sequence); verse.append(heading);
      const columns = node('div', null, 'pattern-columns');
      for (const label of ['Line', 'Family', 'Lyrics / line syllables', 'Credit / repeat', 'Rating', 'Best connection']) columns.append(node('span',label));
      verse.append(columns); $('line-grid').append(verse);
    }
    if (line.adjacent_kind && (includeSlants || line.adjacent_kind !== 'slant')) {
      const previous = lines[line.index - 1];
      const connection = node('button', `↳ Lines ${previous.source_line} + ${line.source_line} · ${connectionText(line.adjacent_syllables,line.adjacent_rating,line.adjacent_kind,line.adjacent_repeated)}`, 'adjacent-connection ' + line.adjacent_kind);
      connection.addEventListener('click', () => selectPair(line,previous,line.adjacent_syllables,line.adjacent_rating,line.adjacent_kind,line.adjacent_repeated)); verse.append(connection);
    }
    const row = node('div', null, 'pattern-line'); row.id = `pattern-${line.index}`; row.tabIndex = -1;
    if (familyId != null) row.style.setProperty('--scheme-color', `var(--scheme-${counts.get(familyId) % 6})`);
    row.append(node('span', String(line.source_line), 'source-line'));
    const family = node('span', schemeLetter(familyId), 'scheme-chip'); family.title = familyId == null ? 'No detected rhyme family' : `Rhyme family ${schemeLetter(familyId)}`; row.append(family);
    const lyric = node('div', null, 'lyric-cell'), text = node('p', null, 'lyric-text');
    if (local && original) text.textContent = local.raw;
    else if (local) {
      const content = local.analysis_text, split = Math.max(local.ending_start,local.repeat_start);
      text.append(document.createTextNode(content.slice(0,local.ending_start)));
      if (local.ending_start < split) text.append(node('mark',content.slice(local.ending_start,split)));
      if (split < content.length) text.append(node('span',content.slice(split),'repeated-ending'));
      if (local.ignored_adlib) text.append(node('span',local.ignored_adlib,'ignored-adlib'));
    } else text.textContent = 'Lyric text unavailable in this copy';
    lyric.append(text,node('span', `${line.line_syllables}${line.unknown_word_count ? '+' : ''} analyzed line syllables${line.unknown_word_count ? ' · incomplete dictionary coverage' : ''}`, 'line-syllable-note'));
    if (line.adlib_adjusted) lyric.append(node('span', `Endpoint before trailing ad-lib${local ? `: ${local.ignored_adlib.trim()} · supported by lines ${local.adlib_support.join(', ')}` : ''}`, 'decision-note'));
    else if (line.adlib_candidate) lyric.append(node('span','Possible trailing ad-lib kept: insufficient advantage from local evidence','decision-note unresolved'));
    if (line.marked_adlib_count) lyric.append(node('span', `Separated short marked ad-lib / echo${local ? ': ' + local.removed_parentheticals.join(' ') : ''}`, 'decision-note'));
    row.append(lyric);
    const anchor = line.predecessor == null && line.anchor_partner != null;
    const kind = anchor ? line.anchor_kind : line.connection_kind;
    const hiddenSlant = kind === 'slant' && !includeSlants;
    const syllables = hiddenSlant ? 0 : anchor ? line.anchor_syllables : line.syllables;
    const repeated = hiddenSlant ? 0 : anchor ? line.anchor_repeated : line.repeated_syllables;
    const rating = hiddenSlant ? null : anchor ? line.anchor_rating : line.rating;
    const depth = node('div', null, 'rhyme-depth');
    depth.append(node('b', kind === 'repetition' ? '0' : syllables || '—'));
    depth.append(node('small', hiddenSlant ? 'Slant hidden' : kind === 'slant' ? 'Possible slant' : kind === 'repetition' ? 'No credit' : syllables ? (anchor ? 'Anchor' : 'credited') : !line.ending_known ? 'Unknown' : 'Unlinked'));
    if (repeated) depth.append(node('small', `+${repeated} repeated`));
    row.append(depth,node('span', (kind === 'slant' && !hiddenSlant ? '~' : '') + fmt(rating,0),'line-rating'));
    const partner = line.predecessor == null ? null : lines[line.predecessor];
    if (partner && !hiddenSlant) {
      const button = node('button', `↖ Line ${partner.source_line}`, 'partner-link');
      button.title = connectionText(syllables,rating,kind,repeated); button.addEventListener('click', () => selectPair(line,partner,syllables,rating,kind,repeated)); row.append(button);
    } else if (anchor && !hiddenSlant) {
      const next = lines[line.anchor_partner], button = node('button', `↘ Line ${next.source_line}`, 'partner-link');
      button.title = 'Later connection using this endpoint'; button.addEventListener('click', () => selectPair(next,line,syllables,rating,kind,repeated)); row.append(button);
    } else row.append(node('span',hiddenSlant ? 'Tentative only' : 'No match','no-partner'));
    verse.append(row);
  }
}
$('show-slants').addEventListener('change',renderLines); $('show-original').addEventListener('change',renderLines);
$('song-picker').addEventListener('change', renderLines); renderLines();
// Keep full lyrics in an ignored local asset, outside committed/public exports.
if (location.protocol === 'file:' || ['localhost','127.0.0.1','[::1]'].includes(location.hostname)) {
  const script = document.createElement('script'); script.src = 'lyrics.local.js';
  script.onload = renderLines; script.onerror = () => { $('lyric-note').hidden = false; };
  document.head.append(script);
}
for (const example of data.examples) { const row = node('tr'); for (const text of [example.a, example.b, fmt(example.rating,0), example.syllables, example.repeated_syllables, example.kind]) row.append(node('td', text)); $('example-table').append(row); }
function renderSensitivity() {
  $('sensitivity').replaceChildren();
  for (const s of data.sensitivity.filter(s => s.scenario === $('scenario').value)) {
    const card = node('article', null, 'card'); card.append(node('h3', s.album)); const stats = node('div', null, 'stats');
    stat(stats, s.rhyme_links, 'Scored links', 0); stat(stats, s.total_rhymed_syllables, 'Credited syllables', 0); stat(stats, s.mean_syllables, 'Mean syllables', 2); stat(stats, s.weighted_syllables_per_100_lines, 'Weighted / 100 lines');
    card.append(stats); $('sensitivity').append(card);
  }
}
$('scenario').addEventListener('change', renderSensitivity); renderSensitivity();
$('interpretation').textContent = 'The primary totals count novel end-rhyme syllables. Repetition connects the pattern without raising the score; tentative phrase slants can be inspected and included in a separate sensitivity scenario. Culture tests the ad-lib decisions, but higher coverage is not evidence that every decision is correct. Internal rhymes and performed pronunciation remain outside this measurement.';
