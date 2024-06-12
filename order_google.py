from ortools.linear_solver import pywraplp
import requests
import json
import folium
import polyline
import json
import time
def filter_driver(driver_df,order_df):
    """
    logic to filter driver to create and distribute order list 
    """
    pass
def route(driver,pickup,drop):
    params = {
    'overview': 'false',
    'alternatives': 'true',
    'steps': 'true',
    }
    response = requests.get(
        f'https://routing.openstreetmap.de/routed-bike/route/v1/driving/{driver[1]},{driver[0]};{pickup[1]},{pickup[0]};{drop[1]},{drop[0]}',
        params=params,
        
    )
    response=response.text
    #response= response.replace('true', 'True')
    #response= response.replace('fasle', 'False')
    return json.loads(response)


def show_route(route_data):
    # Decode polylines to get the coordinates
    coordinates = []
    for leg in route_data['routes'][0]['legs']:
        for step in leg['steps']:
            coords = polyline.decode(step['geometry'])
            coordinates.extend(coords)
    # Create a folium map centered around the starting point
    start_location = route_data['waypoints'][0]['location'][::-1]
    m = folium.Map(location=start_location, zoom_start=15)
    # Add the route to the map
    folium.PolyLine(locations=coordinates, color='blue', weight=5).add_to(m)
    # Add waypoints to the map
    for waypoint in route_data['waypoints']:
        folium.Marker(location=waypoint['location'][::-1]).add_to(m)
    # Save map to HTML file
    m.save(f"/Users/rag9704/Quantum/order_assignment/route_map_{int(time.time())}.html")
    # To display the map in a Jupyter notebook (optional)
    return m
    
def calculate_distance(driver,pickup,drop):
    params = {
    'overview': 'false',
    }
    response = requests.get(
    f'http://router.project-osrm.org/route/v1/driving/{driver[1]},{driver[0]};{pickup[1]},{pickup[0]};{drop[1]},{drop[0]}',
    params=params,
    )
    return (json.loads(response.text)['routes'][0]['legs'][0]['distance']/1000) + (json.loads(response.text)['routes'][0]['legs'][1]['distance']/1000)

def create_cost_matrix(driver_locations, pickup_locations, drop_locations, speeds):
    num_workers = len(driver_locations)
    num_tasks = len(pickup_locations)
    
    distances = []
    for i in range(num_workers):
        driver_distances = []
        for j in range(num_tasks):
            distance = calculate_distance(driver_locations[i], pickup_locations[j], drop_locations[j])
            driver_distances.append(distance)
        distances.append(driver_distances)
    costs = [[distances[i][j] / speeds[i] for j in range(num_tasks)] for i in range(num_workers)]
    return costs



def cost_matrix(costs,speeds):
    num_workers = len(costs)
    num_tasks = len(costs[0])
    costs = [[costs[i][j] / speeds[i] for j in range(num_tasks)] for i in range(num_workers)]
    return costs


def order_assignment(costs):
    # Data
    num_workers = len(costs)
    num_tasks = len(costs[0])
    # Solver
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        return
    # Variables
    x = {}
    for i in range(num_workers):
        for j in range(num_tasks):
            x[i, j] = solver.IntVar(0, 1, '')
    # Constraints
    # Each worker is assigned to at most 1 task.
    for i in range(num_workers):
        solver.Add(solver.Sum([x[i, j] for j in range(num_tasks)]) <= 1)
    # Each task is assigned to exactly one worker.
    for j in range(num_tasks):
        solver.Add(solver.Sum([x[i, j] for i in range(num_workers)]) == 1)
    #Even distribution of tasks constraint
    # y is an auxiliary variable representing the number of tasks assigned to a worker
    y = [solver.IntVar(0, num_tasks, '') for i in range(num_workers)]
    for i in range(num_workers):
        solver.Add(y[i] == solver.Sum([x[i, j] for j in range(num_tasks)]))
    for i in range(num_workers):
        for j in range(num_workers):
            solver.Add(y[i] - y[j] <= 1)
    # Objective
    objective_terms = []
    for i in range(num_workers):
        for j in range(num_tasks):
            objective_terms.append(costs[i][j] * x[i, j])
    solver.Minimize(solver.Sum(objective_terms))
    # Solve
    print(f"Solving with {solver.SolverVersion()}")
    status = solver.Solve()
    # Print solution.
    '''
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        print(f"Total cost = {solver.Objective().Value()}\n")
        for i in range(num_workers):
            for j in range(num_tasks):
                if x[i, j].solution_value() > 0.5:
                    print(f"Worker {i+1} assigned to task {j+1}. Cost: {costs[i][j]}")
    else:
        print("No solution found.")
    '''
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        solution = []
        for i in range(num_workers):
            for j in range(num_tasks):
                if x[i, j].solution_value() > 0.5:
                    solution.append((i, j))
        return solution
    else:
        print("No solution found.")
        return None

def create_folium_map(driver_locations, pickup_locations, drop_locations, solution):
    folium_map = folium.Map(location=list(driver_locations[0]), zoom_start=13)

    # List of colors for different drivers
    colors = ['blue', 'green', 'red', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen',
              'cadetblue', 'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray']

    # Plot all driver locations
    for idx, driver in enumerate(driver_locations):
        folium.Marker(location=driver, popup=f'Driver {idx}', icon=folium.Icon(color='blue')).add_to(folium_map)

    # Process the solution and plot routes, pickups, and drop-offs
    for i, j in solution:
        driver = driver_locations[i]
        pickup = pickup_locations[j]
        drop = drop_locations[j]
        route_driver = route(driver, pickup, drop)

        coordinates = []
        for leg in route_driver['routes'][0]['legs']:
            for step in leg['steps']:
                coords = polyline.decode(step['geometry'])
                coordinates.extend(coords)

        # Select a color based on the driver index
        color = colors[i % len(colors)]

        # Add the route to the map with the selected color
        folium.PolyLine(locations=coordinates, color=color, weight=5).add_to(folium_map)

        # Plot pickup location
        folium.Marker(location=pickup, popup=f'Pickup {j}', icon=folium.Icon(color='green')).add_to(folium_map)
        # Plot drop location
        folium.Marker(location=drop, popup=f'Drop {j}', icon=folium.Icon(color='red')).add_to(folium_map)

    return folium_map

'''
def create_folium_map(driver_locations, pickup_locations, drop_locations, solution):
    folium_map = folium.Map(location=list(driver_locations[0]), zoom_start=13)

    # Plot all driver locations
    for idx, driver in enumerate(driver_locations):
        folium.Marker(location=driver, popup=f'Driver {idx}', icon=folium.Icon(color='blue')).add_to(folium_map)

    # Process the solution and plot routes, pickups, and drop-offs
    for i, j in solution:
        driver = driver_locations[i]
        pickup = pickup_locations[j]
        drop = drop_locations[j]
        route_driver = route(driver, pickup, drop)

        coordinates = []
        for leg in route_driver['routes'][0]['legs']:
            for step in leg['steps']:
                coords = polyline.decode(step['geometry'])
                coordinates.extend(coords)

        # Add the route to the map
        folium.PolyLine(locations=coordinates, color='blue', weight=5).add_to(folium_map)

        # Plot pickup location
        folium.Marker(location=pickup, popup=f'Pickup {j}', icon=folium.Icon(color='green')).add_to(folium_map)
        # Plot drop location
        folium.Marker(location=drop, popup=f'Drop {j}', icon=folium.Icon(color='red')).add_to(folium_map)

    return folium_map
'''
if __name__ == '__main__':
    speeds = [18, 25, 15]
    driver_location = [(12.914368,77.666922),(12.921383, 77.666319),(12.922742,77.675514)]
    pickup_location = [(12.912831, 77.681145),(12.925258,77.671648)]
    drop_location = [(12.922923, 77.673605),(12.915595, 77.677188)]
    #speeds = [10, 20, 15, 25, 12]
    costs = create_cost_matrix(driver_location, pickup_location, drop_location, speeds)
    #order_assignment(costs)

    
    solution = order_assignment(costs)
    if solution:
        folium_map = create_folium_map(driver_location, pickup_location, drop_location, solution)
        folium_map = create_folium_map(driver_location, pickup_location, drop_location, solution)
        folium_map.save(f"/Users/rag9704/Quantum/order_assignment/route_map_{int(time.time())}.html")
        print("Map saved")

