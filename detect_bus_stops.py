# -*- coding: utf-8 -*-
################################################################################
# Script to extract bus stops based on activity points and routes.
################################################################################

import copy
from collections import OrderedDict
from sets import Set
import pygeoj
import utm
import overpass
from  shapely.geometry import Point,LineString,MultiPolygon,MultiLineString,MultiPoint
from numpy import interp
from scipy import signal
import numpy as np
import charting
import clustering

################################################################################
# Relative path where the data is located.
DATA_PATH = 'data/'

################################################################################
# This class represents an activity point with GeoJSON properties as attributes.
# Additionally, the original geometry and an UTM projected geometry is stored.
class ActivityPoint:
    
    def __init__(self, feature):
        self.id = feature.properties['id']
        self.timestamp = feature.properties['timestamp']
        self.created_at = feature.properties['created_at']
        self.previous_dominating_activity = feature.properties[
                                                'previous_dominating_activity']                                                
        self.previous_dominating_activity_confidence = feature.properties[
                                        'previous_dominating_activity_confidence']
        self.current_dominating_activity = feature.properties[
                                        'current_dominating_activity']
        self.current_dominating_activity_confidence = feature.properties[
                                        'current_dominating_activity_confidence']
        self.activity_combination = (self.previous_dominating_activity,
                                     self.current_dominating_activity)
        self.bearing = feature.properties['bearing']
        self.altitude = feature.properties['altitude']
        self.speed = feature.properties['speed']
        self.accuracy = feature.properties['accuracy']
        self.feature = feature.properties['feature']
        self.geojson_geometry = feature.geometry
        # Project coordinates to UTM for more accurate calculations.
        utm_coordinates = utm.from_latlon(feature.geometry.coordinates[1], 
                                          feature.geometry.coordinates[0])
        self.geometry = Point(utm_coordinates[0], utm_coordinates[1])

    def to_geojson_feature(self):
        properties = {
                        'id': self.id, 
                        'timestamp': self.timestamp, 
                        'created_at': self.created_at, 
                        'previous_dominating_activity': 
                                self.previous_dominating_activity,
                        'previous_dominating_activity_confidence': 
                                self.previous_dominating_activity_confidence,
                        'current_dominating_activity': 
                                self.current_dominating_activity,
                        'current_dominating_activity_confidence': 
                                self.current_dominating_activity_confidence,
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

################################################################################
# This class represents a route with route_id and an UTM projected LineString 
# as attributes.
class Route:
    
    def __init__(self, feature):
        self.route_id = feature.properties['route_id']
        utm_coordinates = []
        for c in feature.geometry.coordinates:
            utm_coordinates.append(utm.from_latlon(c[1],c[0])[:2])  # cut off UTM zone
        self.geometry = LineString(utm_coordinates)

    def __eq__(self, other): 
        return self.geometry.equals(other.geometry)

    def __hash__(self):
        return hash(self.geometry.wkt)

################################################################################
# This class represents a bus stop and stores an UTM projected point geometry.
class BusStop:
    def __init__(self, coordinates):
        utm_coordinates = utm.from_latlon(coordinates[1], coordinates[0])
        self.geometry = Point(utm_coordinates[0], utm_coordinates[1])

################################################################################
# This class represents an activity pattern. It inherits from dict and has 
# default values (0) for every previous/current activity combination.    
class ActivityPattern(dict):
    activities = [None, 'still', 'on_foot', 'on_bicycle', 'in_vehicle']

    def __init__(self):
        dict.__init__(self)
        for prev_act in self.activities:
            for curr_act in self.activities:
                self[(prev_act,curr_act)] = 0

    def normalize(self):
        value_sum = 0.0
        for prev_act in self.activities:
            for curr_act in self.activities:
                value_sum += self[(prev_act,curr_act)]        
        for prev_act in self.activities:
            for curr_act in self.activities:
               self[(prev_act,curr_act)] = self[(prev_act,curr_act)] / value_sum

    def has_N_combinations_set(self, n):
        combination_count = 0
        for prev_act in self.activities:
            for curr_act in self.activities:
                if self[(prev_act,curr_act)] > 0:
                    combination_count += 1
        return combination_count >= n

    def get_similarity(self, other):
        distance = 0
        divisor = 0
        for prev_act in self.activities:
            for curr_act in self.activities:
                if self[(prev_act,curr_act)] != other[(prev_act,curr_act)]:
                    divisor += 1
                    distance += abs(self[(prev_act,curr_act)]-other[(prev_act,curr_act)])
        if divisor > 0:
            distance /= divisor
        else: 
            distance = 0
        return 1-distance 

    def get_overall_similarity(self, other):
        distance = 0
        for prev_act in self.activities:
            for curr_act in self.activities:
                distance += abs(self[(prev_act,curr_act)]-other[(prev_act,curr_act)])
        distance /= len(self.activities)**2
        return 1-distance        

################################################################################
# Simple custom GeoJSON related exception.                                          
class GeoJSONError(Exception):
    pass

################################################################################
# Loads a GeoJSON file.
def load_geojson(filename):
    geojson = pygeoj.load(filepath=DATA_PATH+filename)
    return geojson
      
        
################################################################################
# Returns a dictionary from GeoJSON features with ids as keys and ActivityPoint
# objects as values.
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

################################################################################
# Returns a list of Route objects.
def create_routes(features):
    routes = []
    for feature in features:
        routes.append(Route(feature))
    return routes
    
################################################################################
# Checks whether previous and current activities are consistent with the ids.
def check_activity_consistency(activity_points):
    for (id,point) in activity_points.items():
        if (point.previous_dominating_activity is not None and
                id-1 in activity_points and 
                activity_points[id-1].current_dominating_activity is not None):
            if (point.previous_dominating_activity != 
                            activity_points[id-1].current_dominating_activity):
                return False
        if (point.current_dominating_activity is not None and 
                id+1 in activity_points and 
                activity_points[id+1].previous_dominating_activity is not None):
            if (point.current_dominating_activity != 
                            activity_points[id+1].previous_dominating_activity):
                return False
    return True

################################################################################
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

################################################################################
# Creates charts to visually analyze various properties of the given activity
# points.
def profile_activity_points(activity_points):
    if check_activity_consistency(activity_points):
        original_points = copy.deepcopy(activity_points.values())
        enhanced_points = enhance_activity_points(activity_points).values()
    
        figure1 = charting.new_figure(title='Activity combinations', size=(20,10))
        charting.add_activity_combination_matrix(original_points, figure1, rows=1, columns=2, position=1, title='Original data')
        charting.add_activity_combination_matrix(enhanced_points, figure1, rows=1, columns=2, position=2, title='Enhanced data')
        
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
    else:
        figure1 = charting.new_figure(title='Activity combinations', size=(20,10))
        charting.add_activity_combination_matrix(activity_points.values(), figure1, rows=1, columns=1, position=1, title='Original data')

        figure2 = charting.new_figure(title='Properties profile\n(Original data)', size=(20,10))
        charting.add_barchart(activity_points.values(), figure2, 'previous_dominating_activity', rows=2, columns=3, position=1)   
        charting.add_barchart(activity_points.values(), figure2, 'current_dominating_activity', rows=2, columns=3, position=2)   
        charting.add_histogram(activity_points.values(), figure2, 'speed', num_bins=20, rows=2, columns=3, position=3)   
        charting.add_histogram(activity_points.values(), figure2, 'previous_dominating_activity_confidence', num_bins=20, rows=2, columns=3, position=4)   
        charting.add_histogram(activity_points.values(), figure2, 'current_dominating_activity_confidence', num_bins=20, rows=2, columns=3, position=5)   
        charting.add_histogram(activity_points.values(), figure2, 'accuracy', num_bins=20, rows=2, columns=3, position=6)  

    charting.show_charts()

################################################################################
# Retrieves bus stops from OSM via the Overpass API
def get_osm_bus_stops(routes):
    ############################################################################
    # Calculate the bounding box around all routes
    lines = []    
    for route in routes:
        lines.append(route.geometry.buffer(100))
    routes_bounds = MultiPolygon(lines).bounds
    south_west = utm.to_latlon(routes_bounds[0], routes_bounds[1], 37, 'M')
    north_east = utm.to_latlon(routes_bounds[2], routes_bounds[3], 37, 'M')
    bounding_box = (south_west[0],south_west[1],north_east[0],north_east[1])
    ############################################################################
    # Get relevant OSM "nodes". For the sake of simplicity, "ways" are not 
    # considered here. Manual inspection showed that all "ways" in the area also
    # contained at least one "node". Except Ubungo International Bus Terminal,
    # however there is no activity point nearby.
    osm = overpass.API(endpoint='http://overpass.osm.rambler.ru/cgi/interpreter',
                       timeout=60)
    response = osm.Get('(node[amenity=bus_station]'+str(bounding_box)+';'+
                        'node[highway=bus_stop]'+str(bounding_box)+';);')
    ############################################################################
    # Write bus stops to file.
    with open(DATA_PATH+'osm_bus_stops.geojson', 'w') as out:   
        out.write(str(response))
    ############################################################################
    # Return list of BusStop objects.
    osm_bus_stops = []
    for feature in response['features']:
        osm_bus_stops.append(BusStop(feature['geometry']['coordinates']))
    return osm_bus_stops

################################################################################
# Extracts previous/current activity combinations around bus stops.
def extract_activity_combinations_around_bus_stops(bus_stops, activity_points, 
                                                                    radius=150):
    activity_combination_counts = {}
    for bus_stop in bus_stops:
        buffered_bus_stop = bus_stop.geometry.buffer(radius)
        for point in activity_points.values():
            if buffered_bus_stop.intersects(point.geometry):
                activity_tuple = (point.previous_dominating_activity, 
                                  point.current_dominating_activity)
                if activity_tuple in activity_combination_counts:
                    activity_combination_counts[activity_tuple] += 1
                else:
                    activity_combination_counts[activity_tuple] = 1
    return OrderedDict(sorted(activity_combination_counts.items(),
                                key=lambda t: t[1], reverse=True))

################################################################################
# Extracts previous/current activity patterns around bus stops.
def extract_activity_pattern_around_bus_stops(bus_stops, activity_points, 
                                                radius=150, min_combinations=1):
    patterns = []
    for bus_stop in bus_stops:
        pattern = ActivityPattern()
        buffered_bus_stop = bus_stop.geometry.buffer(radius)
        for point in activity_points.values():
            if buffered_bus_stop.intersects(point.geometry):
                pattern[(point.previous_dominating_activity, 
                            point.current_dominating_activity)] += 1
        if pattern.has_N_combinations_set(min_combinations):
            pattern.normalize()
            patterns.append(pattern)
    return patterns
                    

################################################################################
# Bus stop detection algorithm based on route traversing, data-driven activity
# combinations, common sense activity combinations and local maxima detection.                
def detect_bus_stops_traversing_approach(activity_points, routes, activity_radius=200, 
                                            step_length=50, dbscan_eps=400, out_file=None):
    ############################################################################
    # Get bus stop locations from OSM
    osm_bus_stops = get_osm_bus_stops(routes)
    ############################################################################
    # Extract activity combinations around bus stops
    data_driven_activity_combinations = extract_activity_combinations_around_bus_stops(osm_bus_stops, 
                                                                                       activity_points, 
                                                                                       radius=activity_radius)
    ############################################################################
    # Give each combination a score
    data_driven_activity_combinations_scores = {}
    for (combination,count) in data_driven_activity_combinations.items():
        score = 1.0
        if not all(combination):
            score = 0.5
        data_driven_activity_combinations_scores[combination] = score
    interesting_activity_combinations_scores = {
                                                ('in_vehicle','still'): 1,
                                                ('in_vehicle','on_foot'): 1,
                                                ('in_vehicle','on_bicycle'): 1,
                                                ('still','in_vehicle'): 1,
                                                ('on_foot','in_vehicle'): 1,
                                                ('on_bicycle','in_vehicle'): 1                                          
                                               }
    ############################################################################
    # Generate step points for each unique route and calculated a score for each step
    unique_routes = Set([])
    for route in routes:
        unique_routes.add(route)

    filtered_peak_points = []
    filtered_scores = []
    for route in unique_routes:
        score_sequence = []
        step_sequence = []
        steps = int(route.geometry.length/step_length)
        for i in xrange(0,steps):
            step = route.geometry.interpolate(i*step_length)
            buffered_step = step.buffer(activity_radius)
            score = 0
            for activity_point in activity_points.values():
                if buffered_step.intersects(activity_point.geometry):
                    distance = step.distance(activity_point.geometry)
                    if activity_point.activity_combination in interesting_activity_combinations_scores:
                        score += interesting_activity_combinations_scores[activity_point.activity_combination]*interp(distance, [0,activity_radius], [1.2,0.8])
                    elif activity_point.activity_combination in data_driven_activity_combinations_scores:
                        score += data_driven_activity_combinations_scores[activity_point.activity_combination]*interp(distance, [0,activity_radius], [1.2,0.8])
            score_sequence.append(score)
            step_sequence.append(step)
        ############################################################################
        # Find local score peaks in the sequence of steps.
        score_array = np.array(score_sequence)
        peaks = signal.find_peaks_cwt(score_array, np.arange(1,20))
        ############################################################################
        # Prepare stop candidates for clustering
        for i in peaks:
            point = step_sequence[i]
            score = score_sequence[i]
            if score > 0.0:
                filtered_peak_points.append([point.x, point.y])
                filtered_scores.append(score)

    point_array = np.array(filtered_peak_points)
    clusters = clustering.dbscan(point_array, epsilon=dbscan_eps, min_points=1,
                                    visualize=True, vis_title='DBSCAN for traversing-based algorithm')
    clusters_info = {}
    for cluster_id,members in clusters.items():
        cluster_multipoint_coords = []
        avg_score = 0
        for id in np.nditer(members):
            point = filtered_peak_points[int(id)]
            cluster_multipoint_coords.append((point[0],point[1]))
            avg_score += filtered_scores[int(id)]
        clusters_info[int(cluster_id)] = {
                                            'centroid': MultiPoint(cluster_multipoint_coords).centroid,
                                            'score': avg_score/len(cluster_multipoint_coords)
                                         }

    geojson = pygeoj.new()
    geojson.define_crs(type='name', name='urn:ogc:def:crs:OGC:1.3:CRS84')
    for (cluster_id,info) in clusters_info.items():
        
        latlon = utm.to_latlon(info['centroid'].x, info['centroid'].y, 37, 'M')
        feature = pygeoj.Feature(obj=None, properties={'score': info['score']}, 
                                geometry={'type': info['centroid'].type, 'coordinates':
                                                         (latlon[1],latlon[0])})
        if feature.validate():
            geojson.add_feature(feature)
        else:
            raise GeoJSONError('Feature not valid!')  
    geojson.save(DATA_PATH+out_file)  
         
            
################################################################################
# Bus stop detection algorithm based on data-driven activity patterns and 
# spatial clustering.  
def detect_bus_stops_clustering_approach(activity_points, routes, pattern_radius=150,
                                          dbscan_eps = 300, dbscan_min_points=2, out_file=None):
    ############################################################################
    # Try to enhance activity points.
    #enhance_activity_points(activity_points)
    ############################################################################
    # Get bus stop locations from OSM.
    osm_bus_stops = get_osm_bus_stops(routes)
    ############################################################################
    # Extract activity patterns around OSM bus stops.
    bus_stop_patterns = extract_activity_pattern_around_bus_stops(osm_bus_stops,
                                                                  activity_points,
                                                                  pattern_radius, 
                                                                  min_combinations=1)
    ############################################################################
    # Prepare activity points for clustering and perform DBSCAN.
    point_list = []
    clustered_points = {}
    for i in xrange(0,len(activity_points.values())-1):
        point = activity_points.values()[i]
        point.clustering_id = i
        point_list.append([point.geometry.x, point.geometry.y])
        clustered_points[i] = point        
    point_array = np.array(point_list)  
    clusters = clustering.dbscan(point_array, epsilon=dbscan_eps, min_points=dbscan_min_points, 
                                visualize=True, vis_title='DBSCAN for clustering-based algorithm')
    ############################################################################
    # Calculate the activity combination pattern and the centroid for each cluster.    
    clusters_info = {}
    for cluster_id,members in clusters.items():
        cluster_activity_pattern = ActivityPattern()
        cluster_multipoint_coords = []
        original_activity_point_ids = []
        for id in np.nditer(members):
            point_id = int(id)
            activity_point = clustered_points[point_id]
            point_activity_combination = (activity_point.previous_dominating_activity,
                                          activity_point.current_dominating_activity)
            cluster_activity_pattern[point_activity_combination] += 1
            cluster_multipoint_coords.append((activity_point.geometry.coords[0]))
            original_activity_point_ids.append(activity_point.id)
        cluster_activity_pattern.normalize()
        clusters_info[int(cluster_id)] = {
                                            'pattern': cluster_activity_pattern,
                                            'centroid': MultiPoint(cluster_multipoint_coords).centroid,
                                            'activity_points': original_activity_point_ids
                                         }
    ############################################################################
    # Compare cluster patterns with known bus stop patterns. 
    # Project cluster centroid to the closest route.  
    max_projection_distance = 500  
    route_geometries = []
    for route in routes:
        route_geometries.append(route.geometry)
    multi_route = MultiLineString(route_geometries)
   
    potential_bus_stops = []
    similarity_threshold = 0.75
    for cluster_id, info in clusters_info.items():
        #print cluster_id
        similarities = []
        for pattern in bus_stop_patterns:
            similarity = info['pattern'].get_similarity(pattern)
            similarities.append(similarity)
       # print str(min(similarities))+' '+str(np.mean(similarities))+' '+str(max(similarities))
        if max(similarities) > similarity_threshold:
            point_on_route = multi_route.interpolate(multi_route.project(info['centroid']))
            if point_on_route.distance(info['centroid']) <= max_projection_distance:
                potential_bus_stops.append((point_on_route,info['activity_points']))
    ############################################################################
    # Write result to geojson file.
    geojson = pygeoj.new()
    geojson.define_crs(type='name', name='urn:ogc:def:crs:OGC:1.3:CRS84')
    for stop in potential_bus_stops:
        latlon = utm.to_latlon(stop[0].x, stop[0].y, 37, 'M')
        feature = pygeoj.Feature(obj=None, properties={'activity_points': stop[1]}, 
                                 geometry={'type': stop[0].type,
                                           'coordinates': (latlon[1],latlon[0])})
        geojson.add_feature(feature)
   # filename = 'detected_bus_stops_pattern_radius_'+str(pattern_radius)+'.geojson'
    geojson.save(DATA_PATH+out_file)
    
    return potential_bus_stops

################################################################################
# Function to calculate the average distance between detected bus stops and 
# bus stops from OSM.
def avg_distance_to_ground_truth(detected_stops, osm_stops):
    cumulative_distance = 0
    for stop in detected_stops:
        min_dist = 9999999999
        for osm_stop in osm_stops:
            distance = stop.distance(osm_stop)
            if distance < min_dist:
                min_dist = distance
        cumulative_distance += min_dist
    return cumulative_distance/len(detected_stops)
################################################################################
# Function to evaluate different parameter settings.
# The prints have to following structure:
# (pattern_radius, dbscan_eps, dbscan_min_points, #bus_stops, average distance)    
def evaluate_parameter_settings(activity_points, routes, osm_stops):
    results = []
    for pattern_radius in xrange(100,500,50):
        for epsilon in xrange(100,500,50):
            for min_pts in xrange(1,5):
                detected_stops = detect_bus_stops_clustering_approach(activity_points,
                                                                      routes,
                                                                      pattern_radius=pattern_radius,
                                                                      dbscan_eps = epsilon,
                                                                      dbscan_min_points=min_pts)
                stop_list = []
                for stop in detected_stops:
                    stop_list.append(stop[0])
                osm_stop_list = []
                for osm_stop in osm_stops:
                    osm_stop_list.append(osm_stop.geometry)
                results.append((pattern_radius,epsilon,min_pts,len(stop_list),
                                avg_distance_to_ground_truth(stop_list, osm_stop_list)))
    for run in sorted(results, key=lambda x: x[4]):
        print run
                
################################################################################

      
    
activity_points = create_activity_points(load_geojson('activity_points.geojson'))
routes = create_routes(load_geojson('routes.geojson'))

profile_activity_points(activity_points)

enhance_activity_points(activity_points)

detect_bus_stops_clustering_approach(activity_points, routes, pattern_radius=100,
                                        dbscan_eps = 200, dbscan_min_points=2, 
                                        out_file='detected_bus_stops_clustering_approach_params1.geojson')
detect_bus_stops_clustering_approach(activity_points, routes, pattern_radius=150,
                                        dbscan_eps = 300, dbscan_min_points=2,
                                        out_file='detected_bus_stops_clustering_approach_params2.geojson')
detect_bus_stops_traversing_approach(activity_points, routes, activity_radius=200,
                                        step_length=50, dbscan_eps=400, 
                                        out_file='detected_bus_stops_traversing_approach_params1.geojson')
detect_bus_stops_traversing_approach(activity_points, routes, activity_radius=300,
                                        step_length=50, dbscan_eps=400, 
                                        out_file='detected_bus_stops_traversing_approach_params2.geojson')

#osm_bus_stops = get_osm_bus_stops(routes)
#evaluate_parameter_settings(activity_points, routes, osm_bus_stops)


