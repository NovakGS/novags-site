"""Rebuild the Hamele Essentials report and the Due Diligence soils pages in the house report style."""
import sys
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth

LI = '/home/claude/novags-site/hamele/li-img/'
LOGO = '/home/claude/ess2/rep/logo.png'
OLIVE = HexColor('#687d53'); INK = HexColor('#1a1a1a'); BODY = HexColor('#333333'); NOTE = HexColor('#666666'); FOOT = HexColor('#777777')
ST = dict(
    kick=ParagraphStyle('kick', fontName='Helvetica-Bold', fontSize=8.5, leading=13.4, textColor=OLIVE),
    title=ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=INK),
    sub=ParagraphStyle('sub', fontName='Helvetica', fontSize=9.6, leading=13.4, textColor=BODY),
    h2=ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=13.5, leading=17, textColor=OLIVE, spaceBefore=10, spaceAfter=4),
    body=ParagraphStyle('body', fontName='Helvetica', fontSize=9.6, leading=13.4, textColor=BODY, spaceAfter=4),
    note=ParagraphStyle('note', fontName='Helvetica', fontSize=7.8, leading=10.4, textColor=NOTE, spaceBefore=3, spaceAfter=3),
    cell=ParagraphStyle('cell', fontName='Helvetica', fontSize=8.4, leading=10.6, textColor=BODY),
    cellb=ParagraphStyle('cellb', fontName='Helvetica-Bold', fontSize=8.4, leading=10.6, textColor=BODY),
)
W = 612 - 2 * 43.2

def deco(subtitle, page_offset=0):
    def draw(c, doc):
        c.saveState()
        c.setFillColor(INK); c.rect(0, 752.4, 612, 39.6, stroke=0, fill=1)
        c.drawImage(LOGO, 36, 758.5688, 90, 26.54237, mask='auto')
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 9); c.drawRightString(576, 774, 'LAND INTELLIGENCE')
        c.setFont('Helvetica', 8.5); c.drawRightString(576, 763.2, subtitle)
        c.setFillColor(FOOT); c.setFont('Helvetica', 7.4)
        c.drawString(36, 28.8, 'Mapping and analysis by Novak Geospatial Solutions™, a BUCK2NINETY LLC company')
        c.drawRightString(576, 28.8, 'Page %d' % (doc.page + page_offset))
        c.restoreState()
    return draw

def P(t, s='body'): return Paragraph(t, ST[s])

def kv(rows):
    t = Table([[P(k, 'cellb'), P(v, 'cell')] for k, v in rows], colWidths=[165.6, W - 165.6])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                           ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.3, HexColor('#dddddd'))]))
    return t

def grid(head, rows, widths, bold_last=False):
    data = [[P(h, 'cellb') for h in head]] + [[P(c, 'cellb' if (bold_last and i == len(rows) - 1) else 'cell') for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                           ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                           ('BACKGROUND', (0, 0), (-1, 0), HexColor('#eef0ea')),
                           ('LINEBELOW', (0, 0), (-1, -1), 0.3, HexColor('#dddddd'))]))
    return t

def img(name, h=374.4):
    return Image(LI + name, width=h * 1360 / 1155, height=h)

def build(path, title, subtitle, story, page_offset=0):
    doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=43.2, rightMargin=43.2, topMargin=57.6, bottomMargin=57.6,
                            title='33-Acre Hunting Property, Dane County, WI - ' + title, author='Novak Geospatial Solutions™')
    d = deco(subtitle, page_offset)
    doc.build(story, onFirstPage=d, onLaterPages=d)

SRC = {
 'parcels': ('Wisconsin Statewide Parcel Map (V1200)', 'https://www.sco.wisc.edu/parcels/data/'),
 'fema': ('FEMA National Flood Hazard Layer', 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28'),
 'wwi': ('Wisconsin Wetland Inventory (WI DNR)', 'https://dnrmaps.wi.gov/arcgis/rest/services/DW_Map_Dynamic/WT_Wisconsin_Wetland_Inventory_NWI_WTM_Ext_Dynamic_L16/MapServer/8'),
 'hydric': ('Wetland Indicators - hydric soils (WI DNR)', 'https://dnrmaps.wi.gov/arcgis/rest/services/WT_SWDV/WY_WETLAND_INDICATORS/MapServer/21'),
 'ssurgo': ('NRCS Soil Survey (SSURGO) via Soil Data Access', 'https://websoilsurvey.nrcs.usda.gov/'),
 'streams': ('24K Hydrography streams (WI DNR)', 'https://dnrmaps.wi.gov/arcgis/rest/services/WT_SWDV/WY_INLAND_WATER_RESOURCES/MapServer/2'),
 'osm': ('OpenStreetMap contributors (ODbL)', 'https://www.openstreetmap.org/copyright'),
 'lidar': ('Dane County 2024 (USGS 3DEP) LiDAR', 'https://www.usgs.gov/3d-elevation-program'),
}
def sources(keys, lead='Sources: '):
    return P(lead + '; '.join('%s (%s, retrieved 2026-11-25)' % SRC[k] for k in keys) + '.', 'note')

DISCLAIM = ('Maps are built from drone imagery, public LiDAR, and public records for planning and visualization. They are not a land survey and do not establish '
            'property boundaries, wetland boundaries, or legal access. Verify anything that affects a purchase with the agency or professional that owns it.')
WET_NOTE = 'Mapped wetlands are a screening layer. Only a field delineation or a WI DNR determination confirms wetland boundaries.'

def essentials(path):
    s = [P('33-Acre Hunting Property, Dane County, WI', 'kick'), P('Essentials Report', 'title'),
         P('What the land is, how it lies, and where the water goes.', 'sub'), Spacer(1, 8),
         P('The Property at a Glance', 'h2'),
         kv([('Mapped area', '33.33 acres (flight boundary)'),
             ('Boundary dimensions', 'About 1,340 x 1,085 ft, about 4,850 ft around (approximate, not a survey)'),
             ('County', 'Dane County, Wisconsin'), ('Municipality', 'Village of Cross Plains'),
             ('Elevation', '921 to 1,085 ft (164 ft of relief)'),
             ('Cover', 'Hardwood 30.8 ac, Open / Field 1.7 ac, Conifer 0.5 ac, Thicket / Regrowth 0.3 ac'),
             ('FEMA floodplain in boundary', '0 ac'), ('Mapped wetland in boundary', '1.6 ac'),
             ('Nearest public road', 'Shady Street (848 ft)'), ('Leaf-off aerial flown', 'November 24, 2026')]),
         Spacer(1, 6), img('map_overview.jpg', 352), Spacer(1, 6),
         P('County tax-parcel lines from the statewide parcel map. Approximate, not a survey. Owner names are not included.', 'note'),
         PageBreak(),
         P('The Lay of the Land', 'h2'),
         P('Elevation ranges from 921 to 1,085 ft, 164 ft of relief. Median slope is 15.8%. About 10.9 acres are under 12% slope, '
           'and 11.1 acres are steeper than 20%.'),
         Spacer(1, 4), img('map_slope.jpg'), Spacer(1, 6),
         P('Slope classes from the 2024 bare-earth LiDAR over the shaded relief. Greens are the flatter ground, oranges and reds the steeper.', 'note'),
         Spacer(1, 6),
         grid(['Slope', 'Ground', 'Acres', 'Share'],
              [['Under 6%', 'Flat to gentle', '2.9', '9%'], ['6 to 12%', 'Moderate', '8.0', '24%'], ['12 to 20%', 'Moderately steep', '11.3', '34%'],
               ['20 to 35%', 'Steep', '10.0', '30%'], ['35% and over', 'Very steep', '1.1', '3%'], ['Total', '', '33.3', '100%']],
              [131.4, 131.4, 131.4, 131.4], bold_last=True),
         P('Slope is measured from the 2024 bare-earth LiDAR on about a 4 ft grid. Classes are for planning; a site plan or engineer decides what can be built where.', 'note'),
         PageBreak(),
         P('Where the Water Goes', 'h2'),
         P('The whole property is FEMA Zone X, an area of minimal flood hazard, on FIRM panels 55025C0357H and 55025C0376H (both effective 2016-06-16). '
           'No floodplain, stream, or pond falls inside the boundary. The 1.6 acres of mapped wetland inside it are forested.'),
         Spacer(1, 4), img('map_water.jpg'), Spacer(1, 6),
         P('FEMA floodplain (dark blue), WI DNR mapped wetlands (green), and streams over the LiDAR shaded relief.', 'note'),
         Spacer(1, 6),
         grid(['Water', 'Inside the boundary', 'Nearest outside'],
              [['FEMA 1% annual chance floodplain', '0 ac', 'None mapped nearby'],
               ['Mapped wetland (WI DNR)', '1.6 ac, forested', 'Emergent / wet meadow wetland, about 16 ft away'],
               ['Ponds and open water', '0 ac', 'Unnamed pond, about 60 ft away'],
               ['Streams', '0 ft', 'Unnamed stream, about 755 ft away']],
              [175.2, 120, 230.4]),
         P('Wetland points (too small to outline): 0 inside the boundary, 1 within 1/4 mile. Watershed: Black Earth Creek.', 'note'),
         P(WET_NOTE, 'note'),
         PageBreak(),
         P('Boundary dimensions are measured on the map from the flight boundary and rounded to the nearest 5 ft: about 1,340 ft on the north and south lines '
           'and 1,085 ft on the east and west lines. They are approximate and are not a survey.', 'note'),
         sources(['parcels', 'fema', 'wwi', 'streams', 'osm', 'lidar']),
         P(DISCLAIM, 'note')]
    build(path, 'Essentials Report', 'Essentials Report', s)

def dd_soils(path, first_page):
    rows = [('7961D2', 'Kidder soils, 10 to 20 percent slopes, eroded', '11.39', 'Well drained', 'Not prime farmland', 'Very limited', 'Very limited'),
            ('7961E2', 'Kidder soils, 20 to 35 percent slopes, eroded', '10.27', 'Well drained', 'Not prime farmland', 'Very limited', 'Very limited'),
            ('7310D2', 'McHenry silt loam, 12 to 20 percent slopes, eroded', '7.35', 'Well drained', 'Not prime farmland', 'Very limited', 'Very limited'),
            ('609A', 'Otter silt loam', '2.91', 'Poorly drained', 'Prime farmland if drained and either protected from flooding or not frequently flooded during the growing season', 'Very limited', 'Very limited'),
            ('194C2', 'Newglarus silt loam, moderately deep, 6 to 12 percent slopes, moderately eroded', '1.23', 'Well drained', 'Farmland of statewide importance', 'Very limited', 'Very limited'),
            ('7748C2', 'Plano silt loam, gravelly substratum, 6 to 12 percent slopes, eroded', '0.18', 'Well drained', 'Farmland of statewide importance', 'Somewhat limited', 'Very limited')]
    s = [P('Soils and Drainage', 'h2'),
         P('Six NRCS soil map units cover the property, and about 30.4 acres are well drained. The 2.9 acres of Otter silt loam (609A) along the low drainage '
           'are poorly drained, with a water table that can reach the surface. That is the same ground the WI DNR maps as hydric-soil indicators (2.92 acres).'),
         Spacer(1, 4), img('map_soils.jpg'), Spacer(1, 6),
         P('NRCS soil map units, labeled by symbol. The purple 609A unit is the poorly drained ground along the low drainage.', 'note'),
         Spacer(1, 6),
         kv([('Soil map units', '6'), ('Largest unit', 'Kidder soils, 10 to 20 percent slopes, eroded, 11.4 ac'),
             ('Well-drained ground', '30.4 ac'), ('Poorly drained ground', '2.9 ac of Otter silt loam (609A)'),
             ('Hydric-soil indicators (WI DNR)', '2.92 ac inside the boundary'),
             ('Prime (some only if drained) or statewide-important farmland', '4.3 ac')]),
         PageBreak(),
         P('Soil Map Units', 'h2'),
         grid(['Map unit', 'Soil', 'Acres', 'Drainage', 'Farmland class', 'Homes w/o basements', 'Septic fields'], [list(r) for r in rows],
              [52, 136, 38, 62, 117.6, 60, 60]),
         P('Soil ratings are for the dominant component of each map unit and are for planning only. They do not replace an on-site soil test or a certified soil tester for septic.', 'note'),
         P('Poorly drained and hydric soils are where wetland is most likely. ' + WET_NOTE, 'note'),
         sources(['ssurgo', 'hydric'], 'Soil sources: ')]
    build(path, 'Buyer Due Diligence Report', 'Buyer Due Diligence Report', s, page_offset=first_page - 1)

if __name__ == '__main__':
    essentials('/home/claude/ess2/rep/ess_new.pdf')
    dd_soils('/home/claude/ess2/rep/dd_soils.pdf', 3)
    print('ok')
