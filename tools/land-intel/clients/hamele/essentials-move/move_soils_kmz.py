import re, sys
E, D = '/home/claude/ess2/kmz/e/doc.kml', '/home/claude/ess2/kmz/d/doc.kml'
e = open(E).read(); d = open(D).read()
i = e.find('<name>Soils (NRCS)</name>'); a = e.rfind('<Folder>', 0, i); b = e.find('</Folder>', i) + 9
soils = e[a:b]; e = e[:a] + e[b:]
sid = set(re.findall(r'<styleUrl>#([^<]+)</styleUrl>', soils)); assert sid == {'s25155'}
st = re.search(r'<Style id="s25155">.*?</Style>', e).group(0)
if '#s25155' not in e: e = e.replace(st, '')
assert 'id="s25155"' not in d
d = d.replace('<Folder><name>Imagery</name>', st + '<Folder><name>Imagery</name>', 1)
j = d.find('<name>Zoning districts</name>'); k = d.rfind('<Folder>', 0, j)
d = d[:k] + soils + d[k:]
# Essentials boundary: side lengths in the description and as labels on each side
W_, E_, N_, S_ = -89.6273906, -89.6223816, 43.1120397, 43.1090618
desc = ('About 1,340 ft on the north and south lines and 1,085 ft on the east and west lines, about 4,850 ft around (33.33 acres). '
        'Approximate, measured on the map from the flight boundary, not a survey.')
old = '<Placemark><name>Flight boundary (approximate)</name><description><![CDATA[]]></description>'
assert e.count(old) == 1
e = e.replace(old, '<Placemark><name>Flight boundary (approximate)</name><description><![CDATA[%s]]></description>' % desc)
lab_style = '<Style id="sidelabel"><IconStyle><scale>0</scale></IconStyle><LabelStyle><color>ffffffff</color><scale>0.9</scale></LabelStyle></Style>'
e = e.replace('<Folder><name>Imagery</name>', lab_style + '<Folder><name>Imagery</name>', 1)
mx, my = (W_ + E_) / 2, (N_ + S_) / 2
labels = [('North line, about 1,340 ft', mx, N_), ('South line, about 1,340 ft', mx, S_),
          ('East line, about 1,085 ft', E_, my), ('West line, about 1,085 ft', W_, my)]
pms = ''.join('<Placemark><name>%s</name><description><![CDATA[Approximate, measured on the map, not a survey.]]></description><styleUrl>#sidelabel</styleUrl><Point><coordinates>%.7f,%.7f,0</coordinates></Point></Placemark>' % l for l in labels)
bi = e.find('<name>Boundary</name>'); be = e.find('</Folder>', bi)
e = e[:be] + pms + e[be:]
open(E, 'w').write(e); open(D, 'w').write(d)
print('moved', soils.count('<Placemark>'), 'soil placemarks')
