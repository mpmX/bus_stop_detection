# Ally GIS Challenge: Bus stop detection (Solution)
[Task URL](https://github.com/allyapp/gis-code-challenge)

### Required packages
You need to have the following Python packages installed: <br/>
`numpy`<br/>
`scipy`<br/>
`scikit-learn`<br/>
`matplotlib`<br/>
`shapely`<br/>
`utm`<br/>
`pygeoj`<br/>
`overpass`<br/>

### Instructions
1. Run `detect_bus_stops.py` and wait until it terminates.
2. Run `start_webserver.py`.
3. Open a webbrowser (preferably not IE) and go to <http://localhost:8000/>.
4. Explore the results.

### Algorithm description
I implemented two different algorithms to detect bus stops and will explain both approaches in the following paragraphs.
#### Cluster-based approach
Input: Activity points, bus routes, bus stops from OSM
<ol>
<li>Extract bus stop related previous/current activity patterns by examining the surrounding of known bus stops.</li>
<li>Perform spatial clustering on the activity points.</li>
<li>Extract the previous/current activity pattern for each cluster.</li>
<li>Compare the patterns with the bus stop related patterns.</li>
<li>If pattern similarity is above a certain threshold, chances are good that there is a bus stop nearby.</li>
<li>Calculate the centroids for each cluster.</li>
<li>If the distance between the centroid and the closest bus route is below a certain threshold, project the centroid to the closest bus route.</li>
</ol>
Possible improvement:<br/>
For each cluster, take the bearing and speed of the contained activity points into account and shift the centroid accordingly. Then project it to the closest route.

#### Route-traversing approach
Input: Activity points, bus routes, bus stops from OSM
<ol>
<li>Extract bus stop related previous/current activity patterns by examining the surrounding of known bus stops.</li>
<li>Assign a score to each combination.</li>
<li>Define common sense previous/current bus stop related activity combinations and also give them a score.</li>
<li>Traverse each bus route with a certain step length and check for surrounding activity points at each step.</li>
<li>For each step, sum the score of each activity point and optionally penalize by distance.</li>
<li>Detect local maxima on the series of scores for each route</li>
<li>Spatially aggregate the found maxima because bus routes can have route segments in common.</li>
<li>Calculate an average score for the aggregated local maxima and optionally exclude those that are below a certain threshold.</li>
</ol>

#### Comparison
##### Cluster-based approach
\+ Fast.<br/>
\+ Scales well with larger amounts of data.<br/>
\- Does not work so well with small data sets.<br/>
\- Results depend on many parameters.<br/>
##### Route-traversing approach
\+ Flexible due to the ability to define scores for each activity combination.<br/>
\- Rather slow.<br/>
\- Does not scale very well with larger amounts of data.<br/>
\- Results depend on many parameters.<br/>
#### Misc
The two proposed algorithms heavily depend on several parameters and the parameter setting is not always trivial. 
For that reason, I wrote a small function which tests various parameter settings and calculates the average distance between the detected bus stops and the closest known bus stop.
However, it is always a tradoff between the number of detected bus stops and the average distance to the ground truth.
Unfortunately, I had not enough time to evaluate the best parameter settings in depth, however I chose two different settings for each algorithm and provided the option to view the different results in the map visualization.

Furthermore, I've created some charts which helped me to understand the data. They will show up after the bus stop detection is finished.

#### Screenshots
![activity matrix](/screenshots/activity_matrix.png?raw=true)
![activity matrix](/screenshots/data_profiling.png?raw=true)
![activity matrix](/screenshots/results1.PNG?raw=true)
![activity matrix](/screenshots/results2.PNG?raw=true)







