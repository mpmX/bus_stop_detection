import numpy as np

from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

def dbscan(point_array=None, epsilon=250, min_points=2, visualize=True, vis_title='DBSCAN'):
    ############################################################################
    # Standardize points
    scaler = StandardScaler()
    X = scaler.fit_transform(point_array)
    #print X
    # Little 'dirty hack' to allow epsilon definition in native units. 
    eps_pt = np.array([[0.0,0.0],[0.0,float(epsilon)]])
    scaled_eps_pt = scaler.transform(eps_pt)
    epsi = scaled_eps_pt[1][1]-scaled_eps_pt[0][1]

    ############################################################################
    # Compute DBSCAN
    db = DBSCAN(eps=epsi, min_samples=min_points).fit(X)
    core_samples_mask = np.zeros_like(db.labels_, dtype=bool)
    core_samples_mask[db.core_sample_indices_] = True
    labels = db.labels_
    
    # Number of clusters in labels, ignoring noise if present.
    n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
    
    ############################################################################
    # Plot result
    if visualize:
        import matplotlib.pyplot as plt
        figure = plt.figure(figsize=(20,10))
        figure.suptitle(vis_title, fontsize=20)
        axes = figure.add_subplot(1, 1, 1)
        # Black removed and is used for noise instead.
        unique_labels = set(labels)
        colors = plt.cm.Spectral(np.linspace(0, 1, len(unique_labels)))
        for k, col in zip(unique_labels, colors):
            if k == -1:
                # Black used for noise.
                col = 'k'
        
            class_member_mask = (labels == k)
        
            xy = X[class_member_mask & core_samples_mask]
            axes.plot(xy[:, 0], xy[:, 1], 'o', markerfacecolor=col,
                    markeredgecolor='k', markersize=14)
        
            xy = X[class_member_mask & ~core_samples_mask]
            axes.plot(xy[:, 0], xy[:, 1], 'o', markerfacecolor=col,
                    markeredgecolor='k', markersize=6)
        
        axes.set_title('Estimated number of clusters: '+str(n_clusters_)+
                        '\nepsilon='+str(epsilon)+', min. points='+str(min_points))
        plt.show()

    ############################################################################
    # Return clusters with member ids
    result = {}
    for k in np.unique(labels):
        members = np.where(labels == k)[0]
        if k > -1:
            result[k] = members
    return result
