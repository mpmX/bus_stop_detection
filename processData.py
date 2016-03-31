import json
import utm
import os
from  shapely.geometry import shape

data_path = os.path.dirname(os.path.realpath(__file__))+'\\data\\'

def loadGeoJSON(filename):
    with open(data_path+filename) as f:
        data = json.load(f)
    return data

def writeGeoJSON(filename,data):
    with open(filename,'w') as out:
        out.write(json.dumps(data))

def isCleanEnough(feature):
    if len(feature['geometry']['coordinates']) is not 2:
        return False
    if feature['properties']['current_dominating_activity'] is None:
        return False
    if feature['properties']['speed'] is None:
        return False
    return True    

def isStopCandidate(feature):
    if int(feature['properties']['speed']) > 0:
        return False
    if str(feature['properties']['current_dominating_activity']) != 'in_vehicle':
        return False
    return True

def isNearRoute(feature):
    return True
    

actPts = loadGeoJSON('activity_points.geojson')
routes = loadGeoJSON('routes.geojson')

outGeoJSON = {'type': 'FeatureCollection','crs':{'type':'name','properties':{'name':'urn:ogc:def:crs:OGC:1.3:CRS84'}},'features':[]}


for feature in actPts['features']:
    coords = feature['geometry']['coordinates']
    utmCoords = utm.from_latlon(coords[1],coords[0])
    feature['geometry']['utmCoordinates'] = utmCoords
    

    outGeoJSON['features'].append(feature)


print len(actPts['features'])

writeGeoJSON('stops.geojson',outGeoJSON)
