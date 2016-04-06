import copy
import pygeoj
import utm
import overpass
from  shapely.geometry import Point,LineString,MultiPolygon
import charting

DATA_PATH = 'data/'
MAX_DISTANCE_TO_ROUTE = 50  # In meters

# This class represents an activity point with GeoJSON properties as attributes.
# Additionally, the original geometry, an UTM projected geometry and a buffered geometry is stored.
class ActivityPoint:
    
    def __init__(self, feature):
        self.id = feature.properties['id']
        self.timestamp = feature.properties['timestamp']
        self.created_at = feature.properties['created_at']
        self.previous_dominating_activity = feature.properties['previous_dominating_activity']
        self.previous_dominating_activity_confidence = feature.properties['previous_dominating_activity_confidence']
        self.current_dominating_activity = feature.properties['current_dominating_activity']
        self.current_dominating_activity_confidence = feature.properties['current_dominating_activity_confidence']
        self.bearing = feature.properties['bearing']
        self.altitude = feature.properties['altitude']
        self.speed = feature.properties['speed']
        self.accuracy = feature.properties['accuracy']
        self.feature = feature.properties['feature']
        self.geojson_geometry = feature.geometry
        # Project coordinates to UTM for more accurate calculations.
        utm_coordinates = utm.from_latlon(feature.geometry.coordinates[1], feature.geometry.coordinates[0])
        self.geometry = Point(utm_coordinates[0], utm_coordinates[1])
        self.buffered_geometry = self.geometry.buffer(MAX_DISTANCE_TO_ROUTE)

    def is_near(self, route):
        return self.buffered_geometry.intersects(route.geometry)


    def to_geojson_feature(self):
        properties = {
                        'id': self.id, 
                        'timestamp': self.timestamp, 
                        'created_at': self.created_at, 
                        'previous_dominating_activity': self.previous_dominating_activity,
                        'previous_dominating_activity_confidence': self.previous_dominating_activity_confidence,
                        'current_dominating_activity': self.current_dominating_activity,
                        'current_dominating_activity_confidence': self.current_dominating_activity_confidence,
                        'bearing': self.bearing,
                        'altitude': self.altitude,
                        'speed': self.speed,
                        'accuracy': self.accuracy,
                        'feature': self.feature
                     }
        geometry = {
                    'type': self.geojson_geometry.type, 
                    'coordinates': self.geojson_geometry.coordinates
                   }
        return pygeoj.Feature(obj=None, properties=properties, geometry=geometry)


# This class represents a route with route_id and an UTM projected LineString as attributes
class Route:
    
    def __init__(self, feature):
        self.route_id = feature.properties['route_id']
        utm_coordinates = []
        for c in feature.geometry.coordinates:
            utm_coordinates.append(utm.from_latlon(c[1],c[0])[:2])  # cut off UTM zone
        self.geometry = LineString(utm_coordinates)


class BusStop:
    def __init__(self, coordinates):
        utm_coordinates = utm.from_latlon(coordinates[1], coordinates[0])
        self.geometry = Point(utm_coordinates[0], utm_coordinates[1])
        self.nearby_activity_points = []
            

class GeoJSONError(Exception):
    pass


def load_geojson(filename):
    try:
        geojson = pygeoj.load(filepath=DATA_PATH+filename)
    except Exception as e:
        raise GeoJSONError('Could not load '+DATA_PATH+filename+'\nReason: '+repr(e)) 
    return geojson


def write_geojson(activity_points, filename):
    try:
        geojson = pygeoj.new()
        geojson.define_crs(type='name', name='urn:ogc:def:crs:OGC:1.3:CRS84')
        for point in activity_points.values():
            feature = point.to_geojson_feature()
            if feature.validate():
                geojson.add_feature(feature)   
        geojson.save(DATA_PATH+filename)
    except Exception as e:
        raise GeoJSONError('Could not write '+DATA_PATH+filename+'\nReason: '+repr(e))
        

def create_activity_points(features):
    activity_points = {}
    for feature in features:
        if feature.properties['id'] is None:
            raise GeoJSONError('Feature has no id property!')
        elif feature.properties['id'] in activity_points:
            raise GeoJSONError('Duplicate feature id detected!')
        else:
            activity_points[feature.properties['id']] = ActivityPoint(feature)
    return activity_points


def create_routes(features):
    routes = []
    for feature in features:
        routes.append(Route(feature))
    return routes
    

def filter_by_distance(activity_points, routes):
    filtered_activity_points = {}
    for point in activity_points.values():
        for route in routes:  
            if point.is_near(route):
                filtered_activity_points[point.id] = point
                break
    return filtered_activity_points

def filter_by_activity_combinations(activity_points, combinations):
    filtered_activity_points = {}
    for (id, point) in activity_points.items():
        for (previous_activity, current_activity) in combinations:
            if point.previous_dominating_activity == previous_activity and point.current_dominating_activity == current_activity:
                filtered_activity_points[id] = point
                break
    return filtered_activity_points

def check_activity_consistency(activity_points):
    for (id,point) in activity_points.items():
        if point.previous_dominating_activity is not None and id-1 in activity_points and activity_points[id-1].current_dominating_activity is not None:
            if point.previous_dominating_activity != activity_points[id-1].current_dominating_activity:
                return False
        if point.current_dominating_activity is not None and id+1 in activity_points and activity_points[id+1].previous_dominating_activity is not None:
            if point.current_dominating_activity != activity_points[id+1].previous_dominating_activity:
                return False
    return True


# Function to fill missing previous and current activities (where possible)   
def enhance_activity_points(activity_points):
    if check_activity_consistency(activity_points):
        print 'Trying to fill missing activity labels:'
        enhanced_previous_dominating_activities = 0
        enhanced_current_dominating_activities = 0
    
        for point in activity_points.values():
            if point.previous_dominating_activity is None:
                if (point.id-1 in activity_points and
                    activity_points[point.id-1].current_dominating_activity is not None):
                        point.previous_dominating_activity = activity_points[point.id-1].current_dominating_activity
                        point.previous_dominating_activity_confidence = activity_points[point.id-1].current_dominating_activity_confidence
                        enhanced_previous_dominating_activities += 1
            if point.current_dominating_activity is None:
                if (point.id+1 in activity_points and
                    activity_points[point.id+1].previous_dominating_activity is not None):
                        point.current_dominating_activity = activity_points[point.id+1].previous_dominating_activity
                        point.current_dominating_activity_confidence = activity_points[point.id+1].previous_dominating_activity_confidence
                        enhanced_current_dominating_activities += 1
        print 'Added '+str(enhanced_previous_dominating_activities)+' previous_dominating_activities.'
        print 'Added '+str(enhanced_current_dominating_activities)+' current_dominating_activities.'
    else:
        print 'Previous/current activities not consistent with ids. No enhancement possible :('
    return activity_points

      

def profile_activity_points(activity_points):
    original_points = copy.deepcopy(activity_points.values())
    enhanced_points = enhance_activity_points(activity_points).values()

    figure = charting.new_figure(title='Activity combinations', size=(20,10))
    charting.add_activity_combination_matrix(original_points, figure, rows=1, columns=2, position=1, title='Original data')
    charting.add_activity_combination_matrix(enhanced_points, figure, rows=1, columns=2, position=2, title='Enhanced data')
    
    figure2 = charting.new_figure(title='Properties profile\n(Original data)', size=(20,10))
    charting.add_barchart(original_points, figure2, 'previous_dominating_activity', rows=2, columns=3, position=1)   
    charting.add_barchart(original_points, figure2, 'current_dominating_activity', rows=2, columns=3, position=2)   
    charting.add_histogram(original_points, figure2, 'speed', num_bins=20, rows=2, columns=3, position=3)   
    charting.add_histogram(original_points, figure2, 'previous_dominating_activity_confidence', num_bins=20, rows=2, columns=3, position=4)   
    charting.add_histogram(original_points, figure2, 'current_dominating_activity_confidence', num_bins=20, rows=2, columns=3, position=5)   
    charting.add_histogram(original_points, figure2, 'accuracy', num_bins=20, rows=2, columns=3, position=6)   

    figure3 = charting.new_figure(title='Properties profile\n(Enhanced data)', size=(20,10))
    charting.add_barchart(enhanced_points, figure3, 'previous_dominating_activity', rows=2, columns=3, position=1)   
    charting.add_barchart(enhanced_points, figure3, 'current_dominating_activity', rows=2, columns=3, position=2)   
    charting.add_histogram(enhanced_points, figure3, 'speed', num_bins=20, rows=2, columns=3, position=3)   
    charting.add_histogram(enhanced_points, figure3, 'previous_dominating_activity_confidence', num_bins=20, rows=2, columns=3, position=4)   
    charting.add_histogram(enhanced_points, figure3, 'current_dominating_activity_confidence', num_bins=20, rows=2, columns=3, position=5)   
    charting.add_histogram(enhanced_points, figure3, 'accuracy', num_bins=20, rows=2, columns=3, position=6)   

    charting.show_charts()


def get_osm_bus_stops(routes):
    lines = []    
    for route in routes:
        lines.append(route.geometry.buffer(100))
    routes_bounds = MultiPolygon(lines).bounds
    south_west = utm.to_latlon(routes_bounds[0], routes_bounds[1], 37, 'M')
    north_east = utm.to_latlon(routes_bounds[2], routes_bounds[3], 37, 'M')
    bounding_box = (south_west[0],south_west[1],north_east[0],north_east[1])
    osm = overpass.API()
    # Get relevant OSM "nodes". For the sake of simplicity, "ways" are not considered here.
    # Manual inspection showed that all "ways" in the area also contained at least one "node".
    # Except Ubungo International Bus Terminal, however there is no activity point nearby.
    response = osm.Get('(node[amenity=bus_station]'+str(bounding_box)+';'+
                        'node[highway=bus_stop]'+str(bounding_box)+';);')
    with open(DATA_PATH+'osm_bus_stops.geojson', 'w') as out:   
        out.write(str(response))

    osm_bus_stops = []
    for feature in response['features']:
        osm_bus_stops.append(BusStop(feature['geometry']['coordinates']))
    return osm_bus_stops


def extract_activity_pattern_around_bus_stops(bus_stops, activity_points, radius=250):
    for bus_stop in bus_stops:
        buffered_bus_stop = bus_stop.geometry.buffer(radius)
        for point in activity_points.values():
            if buffered_bus_stop.intersects(point.geometry):
                bus_stop.nearby_activity_points.append(point)
                

def detect_bus_stops(activity_points, routes):
    enhance_activity_points(activity_points)

    interesting_activity_combinations = [
                                            ('in_vehicle','still'),
                                            ('in_vehicle','on_foot'),
                                            ('in_vehicle','on_bicycle'),
                                            ('still','in_vehicle'),
                                            ('on_foot','in_vehicle'),
                                            ('on_bicycle','in_vehicle')                                          
                                        ]
    filtered_points = filter_by_activity_combinations(activity_points, interesting_activity_combinations)
    filtered_points = filter_by_distance(filtered_points, routes)
    
    write_geojson(filtered_points,'filtered_activity_points.geojson')
    # TODO
  

activity_points_geojson = load_geojson('activity_points.geojson')
activity_points = create_activity_points(activity_points_geojson)

routes_geojson = load_geojson('routes.geojson')
routes = create_routes(routes_geojson)

osm_bus_stops = get_osm_bus_stops(routes)
extract_activity_pattern_around_bus_stops(osm_bus_stops, activity_points)

for stop in osm_bus_stops:
    if stop.nearby_activity_points:
        for nearby in stop.nearby_activity_points:
            print (nearby.previous_dominating_activity, nearby.current_dominating_activity, nearby.speed)
        print
#profile_activity_points(activity_points)
#detect_bus_stops(activity_points,routes)



