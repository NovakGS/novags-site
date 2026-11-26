"""Rebuild the Hamele Buyer Due Diligence and Stewardship Baseline reports so they follow the round-3 page order.

Due Diligence: build sites, ground and water, zoning, ponds (one row per pond), soils, parcels, what is around it,
historical maps. Stewardship: deer herd baseline first, then cover and canopy, erosion watch, photo points, land use.
Uses the same map images as the web pages (hamele/li-img) and the house report style from essentials-move/li_reports.py.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'essentials-move'))
from li_reports import ST, P, kv, grid, build, DISCLAIM, WET_NOTE, W, LI, OLIVE, BODY
from reportlab.platypus import Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor

ST['h3'] = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=OLIVE, spaceBefore=8, spaceAfter=3)
SIZES = {}

def pic(name, w=None, h=None):
    from PIL import Image as PI
    iw, ih = SIZES.setdefault(name, PI.open(LI + name).size)
    if w is None: w = h * iw / ih
    if h is None: h = w * ih / iw
    return Image(LI + name, width=w, height=h)

def fig(name, caption, w=None, h=None):
    return KeepTogether([pic(name, w, h), Spacer(1, 4), P(caption, 'note')])

def styled(t, extra):
    t.setStyle(TableStyle(extra)); return t

DD_SRC = [
 ('Contaminated Lands - open (WI DNR BRRTS)', 'https://dnrmaps.wi.gov/arcgis/rest/services/RR_Sites_Map/RR_PUBLIC_MAPSERVICES_CORE_EXT/MapServer/101'),
 ('Depth to bedrock from well records (WGNHS / USGS)', 'https://data.wgnhs.wisc.edu/arcgis/rest/services/usgs_ndc/depth_to_bedrock/MapServer/1'),
 ('Historical well construction reports (WGNHS)', 'https://data.wgnhs.wisc.edu/arcgis/rest/services/geologic_data/well_construction_reports/MapServer/0'),
 ('Bedrock geology of Wisconsin, 1:1,000,000 (WGNHS)', 'https://data.wgnhs.wisc.edu/arcgis/rest/services/bedrock_maps/1000k_wisconsin_bedrock/MapServer/3'),
 ('Quaternary geology of Wisconsin, 1:500,000 (WGNHS)', 'https://data.wgnhs.wisc.edu/arcgis/rest/services/surficial_maps/500k_wisconsin_quaternary/MapServer/3'),
 ('DNR Managed Lands (WI DNR)', 'https://dnrmaps.wi.gov/arcgis/rest/services/LF_DML/LF_DNR_Managed_Lands_Dissolved_WTM_Ext/MapServer/0'),
 ('PAD-US Public Access (USGS)', 'https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/PADUS_Public_Access/FeatureServer/0'),
 ('Dane County rural zoning', 'https://dcimapapps.countyofdane.com/arcgissrv/rest/services/Zoning/MapServer/3'),
 ('Shoreland district (primary, 300 ft)', 'https://dcimapapps.countyofdane.com/arcgissrv/rest/services/Shoreland_Zone/MapServer/1'),
 ('Wetland district (75 ft buffer)', 'https://dcimapapps.countyofdane.com/arcgissrv/rest/services/Shoreland_Zone/MapServer/4'),
 ('Resource protection corridors', 'https://dcimapapps.countyofdane.com/arcgissrv/rest/services/Planning/MapServer/1'),
 ('Dane County zoning permits', 'https://dcimapapps.countyofdane.com/arcgissrv/rest/services/Zoning/MapServer/4'),
 ('NRCS Soil Survey (SSURGO) via Soil Data Access', 'https://websoilsurvey.nrcs.usda.gov/'),
 ('Wetland Indicators - hydric soils (WI DNR)', 'https://dnrmaps.wi.gov/arcgis/rest/services/WT_SWDV/WY_WETLAND_INDICATORS/MapServer/21'),
 ('USGS Historical Topographic Maps (The National Map)', 'https://ngmdb.usgs.gov/topoview/'),
 ('OpenStreetMap contributors (ODbL)', 'https://www.openstreetmap.org/copyright'),
]

def pond_table():
    hd = lambda t: P(t, 'cellb')
    c = lambda t: P(t, 'cell')
    data = [[hd('Pond'), hd('Land draining to it'), hd('With an 8 ft dam'), '', '', hd('With a 12 ft dam'), '', '', hd('Soil rating (pond area)')],
            ['', '', hd('Pond size'), hd('Water held'), hd('Dam length'), hd('Pond size'), hd('Water held'), hd('Dam length'), ''],
            [c('Pond 1'), c('4.3 ac'), c('0.58 ac'), c('2.8 ac-ft'), c('376 ft'), c('0.82 ac'), c('5.6 ac-ft'), c('424 ft'), c('Very limited')],
            [c('Pond 2'), c('12.9 ac'), c('0.17 ac'), c('0.5 ac-ft'), c('80 ft'), c('0.46 ac'), c('1.7 ac-ft'), c('208 ft'), c('Somewhat limited')],
            [c('Pond 3'), c('8.1 ac'), c('0.33 ac'), c('1.2 ac-ft'), c('236 ft'), c('0.46 ac'), c('2.8 ac-ft'), c('676 ft'), c('Very limited')]]
    t = Table(data, colWidths=[46, 64, 56, 56, 56, 56, 56, 56, 79.6])
    rule = HexColor('#c8c8c8')
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BACKGROUND', (0, 0), (-1, 1), HexColor('#eef0ea')),
        ('SPAN', (2, 0), (4, 0)), ('SPAN', (5, 0), (7, 0)), ('SPAN', (0, 0), (0, 1)), ('SPAN', (1, 0), (1, 1)), ('SPAN', (8, 0), (8, 1)),
        ('VALIGN', (0, 0), (1, 1), 'BOTTOM'), ('VALIGN', (8, 0), (8, 1), 'BOTTOM'),
        ('LINEBELOW', (2, 0), (7, 0), 0.3, rule),
        ('LINEBEFORE', (2, 0), (2, -1), 0.6, rule), ('LINEBEFORE', (5, 0), (5, -1), 0.6, rule), ('LINEBEFORE', (8, 0), (8, -1), 0.6, rule),
        ('LINEBELOW', (0, 1), (-1, -1), 0.3, HexColor('#dddddd'))]))
    return t

RATINGS = [
    ('Soil ratings:', '<i>Homes w/o basements</i> and <i>Septic fields</i> are USDA NRCS ratings of how well the soil suits a house without a basement and a septic drain field.'),
    ('Not limited:', 'the soil suits the use; expect good performance and very low upkeep.'),
    ('Somewhat limited:', 'the soil has drawbacks that special planning, design, or installation can overcome; expect fair performance and moderate upkeep.'),
    ('Very limited:', 'at least one soil feature, such as steep slope, wetness, or shallow bedrock, works against the use and generally takes major soil work, '
                      'special design, or costly installation to overcome; expect poor performance and high upkeep.'),
    ('Not rated:', 'NRCS has no rating for that soil and use.'),
]

def due_diligence(path):
    build_rows = [['Site A', '6.46', '9.5%', '7961E2', 'Very limited', 'Very limited', '848 ft', '10.7%'],
                  ['Site B', '1.29', '9.8%', '7961D2', 'Very limited', 'Very limited', '1,231 ft', '10.7%'],
                  ['Site C', '0.29', '6.4%', '7961D2', 'Very limited', 'Very limited', '1,511 ft', '13.4%'],
                  ['Site D', '0.26', '11.5%', '7310D2', 'Very limited', 'Very limited', '1,462 ft', '11.0%']]
    soil_rows = [['7961D2', 'Kidder soils, 10 to 20 percent slopes, eroded', '11.39', 'Well drained', 'Not prime farmland', 'Very limited', 'Very limited'],
                 ['7961E2', 'Kidder soils, 20 to 35 percent slopes, eroded', '10.27', 'Well drained', 'Not prime farmland', 'Very limited', 'Very limited'],
                 ['7310D2', 'McHenry silt loam, 12 to 20 percent slopes, eroded', '7.35', 'Well drained', 'Not prime farmland', 'Very limited', 'Very limited'],
                 ['609A', 'Otter silt loam', '2.91', 'Poorly drained', 'Prime farmland if drained and either protected from flooding or not frequently flooded during the growing season', 'Very limited', 'Very limited'],
                 ['194C2', 'Newglarus silt loam, moderately deep, 6 to 12 percent slopes, moderately eroded', '1.23', 'Well drained', 'Farmland of statewide importance', 'Very limited', 'Very limited'],
                 ['7748C2', 'Plano silt loam, gravelly substratum, 6 to 12 percent slopes, eroded', '0.18', 'Well drained', 'Farmland of statewide importance', 'Somewhat limited', 'Very limited']]
    records = [['BUECHNER PROPERTY', 'Closed', '2504 Military Rd, Cross Plains', '2016 to 2016', '0.41 mi'],
               ['DE PETROLEUM', 'Closed', '2575 Main St, Cross Plains', '1989 to 1999', '0.70 mi'],
               ['HI WAY SERVICE GARAGE', 'Closed', '2508 Main St, Cross Plains', '2012 to 2022', '0.85 mi'],
               ['CROSS CORNER CAFE', 'Closed', '2523 Main St, Cross Plains', '1991 to 1992', '0.87 mi'],
               ['FEDELE (JOSEPH) TRUCKING', 'Closed', '8355 Stage Coach Rd, Cross Plains', '1993 to 2009', '0.89 mi'],
               ['KWIK TRIP 833', 'Closed', '2508 Main St, Cross Plains', '1990 to 2000', '0.90 mi']]
    public = [['Baer Park', 'City Land', 'Open access', '15', '0.43 mi'],
              ['Westview Park', 'City Land', 'Open access', '105', '0.47 mi'],
              ['Melody Acres Park', 'City Land', 'Open access', '1', '0.48 mi'],
              ['State Ice Age Trail Area (SIATA)', 'WI DNR', 'DNR managed land', '1,378', '0.54 mi'],
              ['Ice Age Trail - Sd', 'State Department of Natural Resources', 'Open access', '843', '0.56 mi'],
              ['Black Earth Creek Fishery Area', 'WI DNR', 'DNR managed land', '407', '0.66 mi'],
              ['Brewery Creekside Park', 'City Land', 'Open access', 'under 1', '0.82 mi'],
              ['Raspberry Park', 'City Land', 'Open access', '6', '0.83 mi'],
              ['Municipal Park', 'City Land', 'Open access', '573', '0.91 mi'],
              ['Gausewitz Park', 'City Land', 'Open access', 'under 1', '1.17 mi'],
              ['Hickory Hill Conservation Easement', 'Non-Governmental Organization', 'Open access', '54', '1.22 mi'],
              ['Glacial Valley Park', 'City Land', 'Open access', '3', '1.24 mi']]
    s = [P('33-Acre Hunting Property, Dane County, WI', 'kick'), P('Buyer Due Diligence Report', 'title'),
         P('Build sites, the ground and water beneath, zoning, ponds, soils, and the records around the property.', 'sub'), Spacer(1, 6),
         # 1. Build sites
         P('Where a House, Shop, or Driveway Could Go', 'h2'),
         fig('map_build.jpg', 'Candidate build areas (yellow) and the gentlest driveway route on the property (red), starting at the property line nearest the public road.', h=236),
         Spacer(1, 6),
         grid(['Site', 'Acres', 'Avg slope', 'Soil', 'Homes w/o basements', 'Septic fields', 'Driveway', 'Steepest 50 ft'], build_rows,
              [50, 48, 56, 60, 84, 76, 72, 79.6]),
         Spacer(1, 2),
         P('<b>Confirm with the Village:</b> The property is in the Village of Cross Plains, which sets its own zoning. This screen used county, state, and federal layers only, so check any site with the Village before relying on it.', 'note')]
    s += [P('<b>%s</b> %s' % r, 'note') for r in RATINGS]
    s += [P('A Very limited rating doesn&rsquo;t rule a site out, but it means planning on engineering and added cost.', 'note'),
         P('Ground at or under 10% slope on the 2024 LiDAR bare earth (up to 15% counted as workable), at least 50 ft inside the boundary, outside the FEMA 1% floodplain, at least 75 ft from WI DNR mapped wetlands, outside Dane County shoreland, wetland, and floodplain districts where mapped, and at least 40 ft from modeled drainage paths. Driveway lengths and grades are the gentlest route over the 2024 LiDAR bare earth, measured on the property only, from the stretch of property line closest to the nearest public road.', 'note'),
         P('Screening only. Setbacks, driveway permits, septic suitability, and building approvals are set by the Village and county. The property has no road frontage on public road maps: the nearest mapped public road, Shady Street, is about 850 ft past the boundary in a straight line, so access to the property line is a title and easement question.', 'note'),
         PageBreak(),
         # 2. Ground and water
         P('Ground and Water Beneath', 'h2'),
         kv([('Bedrock (state map)', 'Cambrian, undivided. Sandstone with some dolomite and shale, undivided; includes Trempealeau, Tunnel City, and Elk Mound Groups'),
             ('Surface deposits (state map)', 'Low relief hummocky glacial sediment of the Holy Hill Formation. Brown to yellowish-brown sandy till and similar sediment '
              'deposited by the Green Bay and Lake Michigan Lobes late in the Wisconsin Glaciation. Similar to Hm but not in moraines and meltwater-stream sediment '
              'is common (su and sc).'),
             ('Depth to bedrock, nearby wells', '51 wells within 1 mile: 6 to 190 ft, median 50 ft'),
             ('Well depth, same wells', '117 to 360 ft, median 202 ft'),
             ('Historical well reports within 1 mile', '75')]),
         P('Nearby wells describe the area, not this property. Depth to water and yield on the property come only from a new well.', 'note'),
         P('Cross-Sections', 'h3'),
         fig('cross_sections.jpg', 'Cross-sections through the middle of the property: 2024 LiDAR bare earth (brown) and top of surface (green).', w=W),
         P('The drone surface was checked against the Dane County 2024 (USGS 3DEP) LiDAR on open, flat ground: median difference +0.09 ft, spread (NMAD) 3.60 ft. '
           'No independent survey checkpoints were set on this property, so elevations are stated relative to the public LiDAR, not as a certified accuracy.', 'note'),
         PageBreak(),
         # 3. Zoning
         P('Zoning and Land-Use Records', 'h2'),
         fig('map_zoning.jpg', 'Dane County zoning and planning layers.', h=235),
         Spacer(1, 6),
         kv([('County rural zoning in boundary', 'None. The property is in the Village of Cross Plains, which zones its own land. Village zoning is not in this report; confirm it with the Village.'),
             ('Shoreland, wetland, floodplain districts', 'Shoreland district (primary, 300 ft): 1.66 ac, Wetland district (75 ft buffer): 3.71 ac'),
             ('Resource protection corridor', '3.74 ac'), ('Farmland preservation plan', 'Not Farmland Preservation'),
             ('Zoning permits on these parcels', 'None on record'), ('Conditional use permits', 'None mapped'),
             ('Zoning deed restrictions', 'None mapped'), ('Zoning office', 'Village of Cross Plains for zoning on Village land; Dane County Department of Planning &amp; Development, Zoning Division, for the county layers in this report')]),
         Spacer(1, 4),
         P('<b>Shoreland ring:</b> The shoreland ring on this map comes from the most recent public data available. '
           'Follow-up with the zoning office is needed if it has to be confirmed.', 'note'),
         Spacer(1, 6),
         fig('landuse_history.jpg', 'How Dane County has classified the ground inside the boundary over time (acres).', w=W * 0.85),
         PageBreak(),
         # 4. Ponds
         P('What a Pond Here Would Involve', 'h2'),
         P('Every low spot inside the boundary with 2 to 60 acres draining to it was tested twice over the 2024 LiDAR bare earth, once with an 8 ft dam and once '
           'with a 12 ft dam. The three best sites are below, ranked by how much water each foot of dam holds back, and kept at least 300 ft apart.'),
         fig('map_ponds.jpg', 'Dam sites (white circles), the land draining to each (dashed), and the pond an 8 ft dam would hold (blue).', h=300),
         Spacer(1, 6), pond_table(), Spacer(1, 2),
         P('<b>How to read this table:</b> Each site was tested with two dam heights, so each pond has two sets of numbers. <b>Land draining to it</b> is the '
           'ground that sheds rain and snowmelt toward the dam site. It is the pond&rsquo;s water supply, not its size. <b>Pond size</b> is the water surface '
           'when full. <b>Water held</b> is in acre-feet; 1 acre-foot is about 326,000 gallons, or 1 acre of water 1 ft deep. <b>Dam length</b> is how far '
           'the earthen dam would run across the low ground. Pond 2 has the most land draining to it but holds the least water because its draw is steep: '
           'the ground rises about 8 ft in the first 100 ft behind the dam, so the water backs up only a short way. Pond 1 sits in a flatter draw, so an 8 ft '
           'dam backs water up nearly 300 ft. The soil rating uses the classes defined under the build-site table, rated for holding water in a pond.', 'note'),
         P('Pond screening is approximate. A pond needs a site survey, soil borings, an engineered design, and permits (county, and WI DNR where water or '
           'wetlands are involved).', 'note'),
         PageBreak(),
         # 5. Soils
         P('Soils and Drainage', 'h2'),
         P('Six NRCS soil map units cover the property, and about 30.4 acres are well drained. The 2.9 acres of Otter silt loam (609A) along the low drainage '
           'are poorly drained, with a water table that can reach the surface. That is the same ground the WI DNR maps as hydric-soil indicators (2.92 acres).'),
         fig('map_soils.jpg', 'NRCS soil map units, labeled by symbol. The purple 609A unit is the poorly drained ground along the low drainage.', h=320),
         Spacer(1, 6),
         kv([('Soil map units', '6'), ('Largest unit', 'Kidder soils, 10 to 20 percent slopes, eroded, 11.4 ac'),
             ('Well-drained ground', '30.4 ac'), ('Poorly drained ground', '2.9 ac of Otter silt loam (609A), where the water table can reach the surface'),
             ('Hydric-soil indicators (WI DNR)', '2.92 ac inside the boundary, the same ground as the Otter silt loam'),
             ('Prime (some only if drained) or statewide-important farmland', '4.3 ac')]),
         PageBreak(),
         P('Soil Map Units', 'h3'),
         grid(['Map unit', 'Soil', 'Acres', 'Drainage', 'Farmland class', 'Homes w/o basements', 'Septic fields'], soil_rows,
              [52, 136, 38, 62, 117.6, 60, 60]),
         P('Not limited, Somewhat limited, and Very limited are defined under the build-site table. Soil ratings are for the dominant component of each map unit '
           'and are for planning only. They do not replace an on-site soil test or a certified soil tester for septic.', 'note'),
         P('Poorly drained and hydric soils are where wetland is most likely. ' + WET_NOTE, 'note'),
         # 6. Parcels
         P('Parcels and Assessment', 'h2'),
         grid(['Parcel', 'Acres in boundary', 'Parcel acres (GIS)'],
              [['070702195011', '5.44', '41.00'], ['070702480011', '15.08', '39.91'], ['070702485011', '9.37', '39.62'], ['070702190011', '3.45', '41.14']],
              [175.2, 175.2, 175.2]),
         P('County tax-parcel lines from the statewide parcel map. Approximate, not a survey. Owner names are not included. The statewide parcel file carries no '
           'assessment or tax values for these parcels; the current assessment and tax bill are on record with Village of Cross Plains.', 'note'),
         PageBreak(),
         # 7. Around it
         P('What Is Around It', 'h2'),
         P('Within 1 mile of the property: 0 open records and 6 closed records in the WI DNR contaminated-lands database, none on the property itself. '
           'The 12 nearest public properties are all within about 1.25 miles.'),
         fig('map_context.jpg', 'Public land (green) and WI DNR contaminated-land records (red) within about two miles.', h=330),
         Spacer(1, 6),
         grid(['Record', 'Status', 'Address', 'Years', 'Distance'], records, [150, 55, 170, 80, 70.6]),
         P('Nearest Public Land', 'h3'),
         grid(['Name', 'Managed by', 'Access', 'Acres', 'Distance'], public, [165, 130, 105, 55, 70.6]),
         PageBreak(),
         # 8. Historical maps
         P('Historical Maps', 'h2'),
         P('USGS topographic maps covering this ground exist for 1907, 1909, 1957, 1960, 1962, and 1991. The two below are the oldest and newest '
           '1:62,500-scale editions, the most detailed scale that covers the property, with the boundary in orange. The 1957, 1960, and 1991 maps '
           'are regional editions at 1:250,000 and 1:100,000, with far less detail.'),
         fig('historic_topo_1907.jpg', 'USGS 1:62500-scale Quadrangle for Cross Plains, WI 1907', h=270),
         Spacer(1, 4),
         fig('historic_topo_1962.jpg', 'USGS 1:62500-scale Quadrangle for Cross Plains, WI 1962', h=270),
         PageBreak(),
         P('Sources: ' + '; '.join('%s (%s, retrieved 2026-11-25)' % x for x in DD_SRC) + '.', 'note'),
         P(DISCLAIM, 'note')]
    build(path, 'Buyer Due Diligence Report', 'Buyer Due Diligence Report', s)

def stewardship(path):
    s = [P('33-Acre Hunting Property, Dane County, WI', 'kick'), P('Stewardship Baseline Report', 'title'),
         P('Where to watch, what to manage, and what to measure on the next flight.', 'sub'), Spacer(1, 6),
         P('The Baseline', 'h2'),
         P('This flight is the baseline. Change maps (trails and food plots, canopy, erosion, and restoration) are measured against it on each repeat flight.'),
         P('Deer Herd Baseline', 'h2'),
         P('Night thermal survey on November 24, 2026, 7:19 to 8:40 PM: 7 likely sightings, which may include the same deer seen twice (5 to 7 deer), and 9 possible. Each ongoing deer herd survey flies the property again '
           'after dark, in the same season and on the same flight plan, so herd use can be compared from one year to the next.'),
         P('Each survey is a snapshot of one night. Deer under heavy cover or off the property that night are not counted, so treat each number as a minimum.', 'note'),
         KeepTogether([P('Cover and Canopy', 'h2'),
                       grid(['Cover', 'Acres', 'Median canopy height (2024 LiDAR)'],
                            [['Conifer', '0.54', '54 ft'], ['Thicket / Regrowth', '0.29', '12 ft'], ['Open / Field', '1.71', '0 ft'], ['Hardwood', '30.78', '57 ft']],
                            [175.2, 175.2, 175.2]),
                       P('Canopy heights come from 2024 public LiDAR.', 'note')]),
         KeepTogether([P('Erosion Watch', 'h2'),
                       fig('map_steward.jpg', 'Erosion watch (red) and repeat photo points (yellow).', h=330),
                       Spacer(1, 6),
                       grid(['ID', 'Avg slope', 'Drains', 'Length'], [['E1', '18.2%', '2.8 ac', '113 ft']], [131.4, 131.4, 131.4, 131.4]),
                       P('Erosion watch: modeled drainage paths that average 15% slope or steeper and collect at least 1 acre of runoff.', 'note')]),
         P('Repeat Photo Points', 'h2'),
         P('18 points are saved in the GPX file in the Downloads. Each repeat flight retakes the same views so change can be compared side by side.'),
         KeepTogether([P('Land-Use History', 'h2'),
                       fig('landuse_history.jpg', 'County land-use classes inside the boundary, by year (acres).', w=W)]),
         Spacer(1, 8),
         P(DISCLAIM, 'note')]
    build(path, 'Stewardship Baseline Report', 'Stewardship Baseline Report', s)

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp'
    due_diligence(os.path.join(out, '26-239-buyer-due-diligence-report.pdf'))
    stewardship(os.path.join(out, '26-239-stewardship-baseline-report.pdf'))
    print('ok')
