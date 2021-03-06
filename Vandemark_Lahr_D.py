#!/usr/bin/env python3

import abc
import cv2
import numpy as np
from math import sqrt

# Board dimensions, in millimeters as well as pixels
BOARD_H = 300
BOARD_W = 400

# Board Obstacles
quads = [[36.53, 124.38, 48, 108, 170.87, 194.04, 159.40, 210.42],
         [200,280,200,230,210,230,210,280],
         [210,280,210,270,230,270,230,280],
         [210,240,210,230,230,230,230,240]]
elips = [[90, 70, 35, 35],
         [246, 145, 60, 30]]


def quad_check(x0, y0, quad):
    # extract coords out of quad list
    x1 = quad[0]
    y1 = quad[1]
    x2 = quad[2]
    y2 = quad[3]
    x3 = quad[4]
    y3 = quad[5]
    x4 = quad[6]
    y4 = quad[7]

    # check if the point is within the restricted half-plane side of each line
    chk1 = line_check(x0, y0, x1, y1, x2, y2, False, False)
    chk2 = line_check(x0, y0, x2, y2, x3, y3, False, True)
    chk3 = line_check(x0, y0, x3, y3, x4, y4, True, True)
    chk4 = line_check(x0, y0, x4, y4, x1, y1, True, False)

    # check if point is within resitected half place side of all lines --> in object
    if chk1 and chk2 and chk3 and chk4:
        return False  # point is in obstacle space
    else:
        return True  # point is not in obstacle space


def line_check(x0, y0, x1, y1, x2, y2, UD, LR):
    # UD = True  if object is bottom side of line
    # UD = False if object is top    side of line
    # LR = True  if object is left   side of line
    # LR = False if object is right  side of line
    if x2 != x1:  # not vertical line
        m = (y2 - y1) / (x2 - x1)  # get the slope
        b = y1 - m * x1  # get the intercept
        # check if point is within the restriced half-plane
        if (y0 >= m * x0 + b and not UD) or (y0 <= m * x0 + b and UD):
            return True  # True means point is within the restriced half-plane
        else:
            return False  # False means point is not within the restriced half-plane

    else:  # x2 == x1 --> vertical line
        if (x0 >= x1 and not LR) or (x0 <= x1 and LR):
            return True  # True means point is within the restriced half-plane
        else:
            return False  # False means point is not within the restriced half-plane


def elip_check(x0, y0, elip):
    # extract dimensions out of elip list
    xc = elip[0]
    yc = elip[1]
    a2 = elip[2]**2  # horizontal dimension
    b2 = elip[3]**2  # vertical dimension

    if (x0 - xc)**2 / a2 + (y0 - yc)**2 / b2 <= 1:  # check if point is within ellipse
        return False  # point is in obstacle space
    else:
        return True  # point is not in obstacle space
    

def setup_graph(robot_radius, clearance, point_robot = True):
    obst = np.ones((BOARD_H,BOARD_W))
    for x in range(BOARD_W):
        for y in range(BOARD_H):
            for quad in quads:  # check quads
                if not quad_check(x, y, quad):  # see if point is near the quad
                    obst[BOARD_H-y, x] = 0
                    break
    
            for elip in elips:  # check elips
                if not elip_check(x, y, elip):  # see if point is near the elip
                    obst[BOARD_H-y, x] = 0
                    break
                
    if not point_robot:  # used to override the expansion for the vizualization step
        return obst
                       
    newObst = np.ones((BOARD_H,BOARD_W))  # create new obstacle array that will have r
    r = robot_radius + clearance  # point robot radius
    for x in range(BOARD_W):
        for y in range(BOARD_H):
            for i in range(x-r, x+r):  # window each pixel and check for an obstacle in radius
                for j in range(y-r, y+r):
                    if i >= 0 and j >= 0 and i < BOARD_W and j < BOARD_H:  # makes sure point is within bounds
                        if obst[j, i] == 0 and sqrt((x-i)**2+(y-j)**2) < r:  # if window point is in obstacle
                            newObst[y, x] = 0
                            break
                else:
                    continue
                break
            
    return newObst            


# A representation of the traversable portions of the maze
class DiscreteGraph(object):

    # The square root of 2, to reuse in NEIGHBOR_DISPLACEMENTS
    R2 = sqrt(2)

    # An 8-tuple of 2-tuples, describing the (y,x) displacements and total distance to each neighbor
    NEIGHBOR_DISPLACEMENTS = (
        (-1, -1, R2), (-1, +0, +1), (-1, +1, R2),
        (+0, -1, +1),               (+0, +1, +1),
        (+1, -1, R2), (+1, +0, +1), (+1, +1, R2)
    )

    # A dict, where the key is a vertex, and the value is a list of 2-tuples:
    # - A vertex is itself a 2-tuple (y,x), where the y and x is the pixel
    #   position / millimeter displacement from the top left corner of the board
    # - For the 2-tuple elements:
    #   - The first element is another vertex that the vertex key can connect to
    #   - The second element is the distance between these two vertices, it's
    #     calculated here once and only once to save time
    edges = None

    # Build the graph with the given obstacles
    def __init__(self, robot_radius, clearance):
        self.build(robot_radius, clearance)

    # Build the graph with the given obstacles
    def build(self, robot_radius, clearance):
        # Clear the set of edges
        self.edges = dict()

        # Loop through all the pixels / each millimeter to create the edges by
        # visiting each pixel's (at most) eight neighbors
        # A neighbor is valid if it's within the bounds of the maze and is not
        # inside of any of the given obstacles
        rh = range(BOARD_H); rw = range(BOARD_W)
        obst = setup_graph(robot_radius, clearance)  # creates the obstacle space. 0 for obstacle, 1 for open space
        for j in rh:
            for i in rw:
                if obst[j, i] == 0:
                    continue
                v = (j,i)
                self.edges[v] = list()
                for dj, di, dd in DiscreteGraph.NEIGHBOR_DISPLACEMENTS:
                    jj = j + dj; ii = i + di
                    if (jj in rh) and (ii in rw) and not obst[jj, ii] == 0:
                        self.edges[v].append(((jj,ii), dd))

# A single state of the maze's search
class MazeVertexNode(object):

    # The parent MazeVertexNode to this instance
    parent = None

    # A 2-tuple, (y,x) coordinate pair
    position = None

    # The current tentative distance from the start to this node
    distG = None

    # The current tentative distance from this node to the goal, given some heuristic
    distF = None

    # Constructor, given all values
    def __init__(self, parent, position, distG, distF):
        self.parent = parent
        self.position = position
        self.distG = distG
        self.distF = distF

# A maze object that uses a DiscreteGraph instance with some other utilities
class Maze(abc.ABC):

    # The DiscreteGraph representation of the maze
    graph = None

    # Build the graph with the list of semi-algebraic models
    def __init__(self, robot_radius, clearance):
        self.graph = DiscreteGraph(robot_radius, clearance)

    # Determine if a coordinate pair is in a traversable portion of the maze
    def is_in_board(self, position):
        return position in self.graph.edges

    # Run a path planning algorithm between a start and goal point
    def find(self, start, goal):
        # Mark every traversable pixel except for the start as initially without a parent and infinitely far
        vertices = [MazeVertexNode(None, pos, 999999999, 999999999) for pos in self.graph.edges.keys() if pos != start]
        vertices.append(MazeVertexNode(None, start, 0, self.h(start, goal)))
        vertex_indices = {v.position:v for v in vertices}

        # Track the pixels that were visited in the order they were, to visualize later
        pixels_explored = []

        # Start the main part of the algorithm, tracking the node that can be used to recover the path
        final_node = None
        while (final_node is None) and (len(vertices) != 0):
            # Essentially, mark this node as "visited" and capture its position
            vertex_node = vertices.pop(-1)
            vnp = vertex_node.position
            pixels_explored.append(vnp)

            # Check if this is the goal position
            if vnp == goal:
                final_node = vertex_node
                continue

            # Get each of the neighbors of this node by using the graph
            for neighbor, dist_to_neighbor in self.graph.edges[vnp]:
                neighbor_node = vertex_indices.get(neighbor, None)
                if neighbor_node is None:
                    # This node was already removed, continue to the next neighbor
                    continue
                # Calculate the adjusted distance
                vertex_node_distG = vertex_node.distG + dist_to_neighbor
                if vertex_node_distG < neighbor_node.distG:
                    # Set this node as this neighbor's shortest path
                    vertices.remove(neighbor_node)
                    neighbor_node.distG = vertex_node_distG
                    neighbor_node.distF = vertex_node_distG + self.h(neighbor_node.position, goal)
                    neighbor_node.parent = vertex_node
                    # Do a less costly sort by simply moving the neighbor node in the list
                    i = len(vertices) - 1
                    while True:
                        if vertices[i].distF >= neighbor_node.distF:
                            vertices.insert(i + 1, neighbor_node)
                            break
                        i = i - 1

        # If there's no path, the final_node will be null, but pixels_explored could still have content
        return final_node, pixels_explored

    # Calculate the tentative remaining distance from n to goal, given some heuristic
    @abc.abstractmethod
    def h(self, n, goal):
        return None

# A Maze that uses Dijkstra
class MazeDijkstra(Maze):

    # Build the graph with the list of semi-algebraic models
    def __init__(self, robot_radius, clearance):
        super().__init__(robot_radius, clearance)

    # Overriden
    def h(self, n, goal):
        return 0

def main():
    # Capture required user input
    s = None
    try:
        s_str = input("Enter the start position: ")
        s_comma = s_str.index(",")
        s = (int(s_str[:s_comma]), int(s_str[s_comma+1:]))
    except:
        print("Please enter the start position in \"y,x\" format, where y and x are integers.")
        return

    g = None
    try:
        g_str = input("Enter the goal position: ")
        g_comma = g_str.index(",")
        g = (int(g_str[:g_comma]), int(g_str[g_comma+1:]))
    except:
        print("Please enter the goal position in \"y,x\" format, where y and x are integers.")
        return

    robot_radius = None
    try:
        r_str = input("Enter the robot radius: ")
        robot_radius = int(r_str)
    except:
        print("Please enter the robot radius as an integer.")
        return
    if robot_radius <= 0:
        print("Please enter the robot radius as a positive integer.")
        return

    clearance = None
    try:
        c_str = input("Enter the clearance: ")
        clearance = int(c_str)
    except:
        print("Please enter the clearance as an integer.")
        return
    if clearance < 0:
        print("Please enter the robot radius as a non-negative integer.")
        return

    vid_name = input("Enter the name of the output file (no file extension, ex. 'output1'): ")

    # Build the maze and underlying graph object
    print("Starting maze generation...")
    maze = MazeDijkstra(robot_radius, clearance)
    # Check if they're traversable positions in the maze, continue if so
    if maze.is_in_board(s) and maze.is_in_board(g):
        # Do Dijkstra
        print("Done. Planning path...")
        path_node, positions_searched = maze.find(s,g)
        print("Done. Starting render...")
        # Build video writer to render the frames at 120 FPS
        vid_write = cv2.VideoWriter(
            "{0}.mp4".format(vid_name),
            cv2.VideoWriter_fourcc(*'mp4v'),
            120.0,
            (BOARD_W, BOARD_H)
        )
        # Build image to be white and draw the obstacles
        temp = np.uint8(setup_graph(robot_radius, clearance, point_robot = False))
        temp *= 255
        img = np.empty((BOARD_H,BOARD_W,3), dtype=np.uint8)
        img[:, :, 0] = temp
        img[:, :, 1] = temp
        img[:, :, 2] = temp
        img[s] = (0,255,0)
        img[g[0]-2:g[0]+2,g[1]-2:g[1]+2] = (0,0,255)

        # Go through the pixels visited
        for px in positions_searched:
            img[px] = (255,0,0)
            vid_write.write(img)
        # Draw the final path
        while path_node is not None:
            img[path_node.position] = (0,255,0)
            vid_write.write(img)
            path_node = path_node.parent
        vid_write.release()
        print("Finished.")
    else:
        print("Either the start {0} or the goal {1} was not valid.".format(s, g))

if __name__ == "__main__":
    main()
