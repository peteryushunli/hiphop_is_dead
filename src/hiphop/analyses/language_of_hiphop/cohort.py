"""Define the editorial pilot cohort. This is a sample, not a census or chart ranking."""
import csv
import json

from hiphop.text import name_key as key
from hiphop.paths import StudyPaths
GROUPS = {
    'rap': ['2Pac', 'The Notorious B.I.G.', 'Nas', 'JAY-Z', 'Wu-Tang Clan', 'OutKast',
            'A Tribe Called Quest', 'De La Soul', 'Public Enemy', 'N.W.A', 'Ice Cube',
            'Dr. Dre', 'Snoop Dogg', 'Scarface', 'Geto Boys', 'Gang Starr', 'Mobb Deep',
            'Mos Def', 'Talib Kweli', 'Common', 'The Roots', 'Lauryn Hill', 'Missy Elliott',
            'Lil’ Kim', 'Queen Latifah', 'Foxy Brown', 'DMX', 'Busta Rhymes', 'Eminem',
            'MF DOOM', '50 Cent', 'Ludacris', 'T.I.', 'Jeezy', 'Gucci Mane', 'Lil Wayne',
            'Kanye West', 'Nicki Minaj', 'Drake', 'Kendrick Lamar', 'J. Cole', 'Big Sean',
            'Wale', 'Kid Cudi', 'Tyler, The Creator', 'Earl Sweatshirt', 'Mac Miller',
            'A$AP Rocky', 'ScHoolboy Q', 'Danny Brown', 'Freddie Gibbs', 'Pusha T',
            'Run The Jewels', 'Vince Staples', 'Denzel Curry', 'Joey Bada$$', 'JID',
            'Little Simz', 'Stormzy', 'Skepta', 'Dave', 'Central Cee', 'Future',
            'Young Thug', 'Travis Scott', 'Migos', '21 Savage', 'Lil Uzi Vert',
            'Playboi Carti', 'Lil Baby', 'Gunna', 'Kodak Black', 'Lil Yachty',
            'Juice WRLD', 'Pop Smoke', 'Lil Durk', 'Cardi B', 'Megan Thee Stallion',
            'Doja Cat', 'Latto', 'GloRilla', 'Ice Spice', 'Doechii', 'Sexyy Red',
            'Rapsody', 'Noname', 'billy woods', 'JPEGMAFIA'],
    'pop': ['Madonna', 'Michael Jackson', 'Mariah Carey', 'Whitney Houston',
            'Britney Spears', 'Christina Aguilera', 'P!nk', 'Katy Perry', 'Lady Gaga',
            'Taylor Swift', 'Ariana Grande', 'Justin Bieber', 'Ed Sheeran', 'Adele',
            'Dua Lipa', 'Billie Eilish', 'Olivia Rodrigo', 'Sabrina Carpenter',
            'Chappell Roan', 'Tate McRae', 'Charli xcx', 'Harry Styles', 'Miley Cyrus'],
    'rb': ['Mary J. Blige', 'TLC', 'Aaliyah', 'Usher', 'D’Angelo', 'Erykah Badu',
           'Alicia Keys', 'Beyoncé', 'Rihanna', 'Ne-Yo', 'Frank Ocean', 'Miguel',
           'The Weeknd', 'SZA', 'Summer Walker', 'Kehlani', 'Victoria Monét',
           'Brent Faiyaz', 'Giveon', 'Daniel Caesar', 'PARTYNEXTDOOR'],
    'rock': ['Nirvana', 'Pearl Jam', 'Soundgarden', 'Radiohead', 'Oasis', 'Blur',
             'Green Day', 'Foo Fighters', 'Red Hot Chili Peppers', 'Coldplay',
             'The Strokes', 'The Killers', 'Paramore', 'Arctic Monkeys', 'Muse',
             'Florence + the Machine', 'Hozier', 'Mitski', 'Phoebe Bridgers',
             'boygenius', 'Fontaines D.C.', 'Wet Leg', 'Turnstile'],
    'country': ['Garth Brooks', 'Shania Twain', 'Faith Hill', 'Tim McGraw',
                'Alan Jackson', 'George Strait', 'Dixie Chicks', 'Kenny Chesney',
                'Carrie Underwood', 'Miranda Lambert', 'Eric Church', 'Luke Bryan',
                'Kacey Musgraves', 'Chris Stapleton', 'Maren Morris', 'Luke Combs',
                'Morgan Wallen', 'Zach Bryan', 'Tyler Childers', 'Lainey Wilson',
                'Jelly Roll', 'Shaboozey', 'Megan Moroney']
}
RECENT = set(['Drake','Kendrick Lamar','J. Cole','Tyler, The Creator','A$AP Rocky',
              'Travis Scott','Future','21 Savage','Playboi Carti','Lil Uzi Vert',
              'Lil Baby','Gunna','Lil Yachty','Nicki Minaj','Cardi B','Megan Thee Stallion',
              'Doja Cat','Latto','GloRilla','Ice Spice','Doechii','Sexyy Red','JID',
              'Denzel Curry','Little Simz','Central Cee','Dave','JPEGMAFIA',
              'Taylor Swift','Ariana Grande','Dua Lipa','Billie Eilish','Olivia Rodrigo',
              'Sabrina Carpenter','Chappell Roan','Tate McRae','Charli xcx','Miley Cyrus',
              'Beyoncé','The Weeknd','SZA','Summer Walker','Victoria Monét',
              'Brent Faiyaz','Giveon','Daniel Caesar','PARTYNEXTDOOR','Kehlani',
              'Foo Fighters','Green Day','Paramore','Hozier','Mitski','boygenius',
              'Fontaines D.C.','Wet Leg','Turnstile','Coldplay',
              'Kacey Musgraves','Chris Stapleton','Luke Combs','Morgan Wallen',
              'Zach Bryan','Tyler Childers','Lainey Wilson','Jelly Roll','Shaboozey','Megan Moroney'])
def build_config(root):
    paths = StudyPaths(root, 'language-of-hip-hop')
    # Preserve the published original roster, adding the contemporary/editorial names above.
    roster_path = paths.references / 'pudding-artist-song-counts.csv'
    original = list(csv.DictReader(roster_path.read_text().splitlines()))
    known = {key(a) for artists in GROUPS.values() for a in artists}
    aliases = {'notoriousbig':'The Notorious B.I.G.','yasiinbey':'Mos Def',
               'youngjeezy':'Jeezy','lilkim':'Lil’ Kim','puffdaddy':'Diddy',
               'puffdaddyandthefamily':'Diddy'}
    for row in original:
        name=aliases.get(key(row['artist']),row['artist'])
        if key(name) not in known:
            GROUPS['rap'].append(name)
            known.add(key(name))
    config = {'start_year': 1990, 'as_of': '2026-09-30', 'recent_start_year': 2023,
              'recent_catalog_pages': 2, 'recent_max_songs_per_artist': 40,
              'min_words_per_song': 50, 'min_songs_per_artist': 20,
              'cohort_type': 'published Pudding roster plus editorial additions; not representative of all music',
              'original_roster_source': 'https://pudding.cool/2017/09/hip-hop-words/data/artist_song_counts_full.csv',
              'artists': [{'artist': a, 'genre': g, 'collect_recent': a in RECENT}
                          for g, artists in GROUPS.items() for a in artists]}
    (paths.config).write_text(json.dumps(config, indent=2, ensure_ascii=False)+'\n')
