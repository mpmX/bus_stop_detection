import matplotlib.pyplot as plt
import numpy as np


class InvalidInputError(Exception):
    pass


def new_figure(title=None, size=None):
    plt.style.use('ggplot')
    figure = plt.figure(figsize=size)
    figure.suptitle(title, fontsize=20)
    return figure


def add_activity_combination_matrix(activity_points, figure, rows=1, columns=1, position=1,
                                        title='Activity combinations'):
    matrix = [[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]
    mapping = {'still':1,'on_foot':2,'on_bicycle':3,'in_vehicle':4}
    for point in activity_points:
        row = mapping.get(point.previous_dominating_activity, 0)
        column = mapping.get(point.current_dominating_activity, 0)
        matrix[row][column] += 1
    
    matrix = np.matrix(matrix)
    axes = figure.add_subplot(rows, columns, position)    
    axes.grid(b=False)
    labels = ['Unknown','still','on_foot','on_bicycle','in_vehicle']
    axes.set_xticklabels([''] + labels)
    axes.set_yticklabels([''] + labels)

    image = axes.matshow(matrix, cmap=plt.cm.Greens)
    figure.colorbar(image)
    for (i, j), z in np.ndenumerate(matrix):
        axes.text(j, i, z, ha='center', va='center')

    axes.set_title(title)
    axes.set_xlabel('current_dominating_activity')
    axes.set_ylabel('previous_dominating_activity')


def add_barchart(activity_points, figure, feature_property, rows=1, columns=1, position=1):
    value_counts = {}
    for point in activity_points:
        feature_properties = {
                                'current_dominating_activity': point.current_dominating_activity,
                                'previous_dominating_activity': point.previous_dominating_activity
                             }
        if feature_property not in feature_properties:
            raise InvalidInputError(str(feature_property)+' is not a valid feature property here!')
        
        value = feature_properties[feature_property]
        if value is None:
            value = 'Unknown'
        if value in value_counts:
            value_counts[value] += 1
        else:
            value_counts[value] = 1
        
    keys = []
    values = []
    for (key, value) in sorted(value_counts.items()):
        keys.append(key)
        values.append(value)

    axes = figure.add_subplot(rows, columns, position) 
    y_positions = np.arange(len(keys))
    axes.barh(y_positions, values, align='center', alpha=0.8)
    axes.set_yticks(y_positions)
    axes.set_yticklabels(keys)
    axes.set_xlabel('Count')
    axes.set_title(feature_property)  


def add_histogram(activity_points, figure, feature_property, num_bins=20, rows=1, columns=1, position=1):
    values = []
    for point in activity_points:
        feature_properties = {
                                'current_dominating_activity_confidence': point.current_dominating_activity_confidence,
                                'previous_dominating_activity_confidence': point.previous_dominating_activity_confidence,
                                'speed': point.speed,
                                'accuracy': point.accuracy
                             }
        if feature_property not in feature_properties:
            raise InvalidInputError(str(feature_property)+' is not a valid feature property here!')
             
        values.append(feature_properties[feature_property])
    
    numpy_values = np.array(values)
    axes = figure.add_subplot(rows, columns, position)
    axes.hist(numpy_values, num_bins, normed=True, cumulative=True, facecolor='green', alpha=0.5)
    axes.set_xlabel(feature_property)
    axes.set_ylabel('Cumulative probability')
    axes.set_title(feature_property)
          

def show_charts():
    plt.show()   
