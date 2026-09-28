import heapq
from collections import deque
from database import get_connection

class PaymentNetworkGraph:
    def __init__(self):
        self.graph = {}

    def add_edge(self, u, v, cost, latency, reliability):
        if u not in self.graph:
            self.graph[u] = []
        if v not in self.graph:
            self.graph[v] = []
        self.graph[u].append((v, cost, latency, reliability))

    # --- Algorithm 1: Dijkstra Shortest Path (Optimal Cost/Latency) ---
    def dijkstra_route(self, start_node, end_node, criteria="cost"):
        pq = [(0, start_node, [start_node], {"total_cost": 0, "total_latency": 0, "reliability_prod": 1.0})]
        visited = set()

        while pq:
            curr_weight, curr_node, path, metrics = heapq.heappop(pq)

            if curr_node == end_node:
                return {
                    "algorithm": "Dijkstra (Shortest/Cheapest Path)",
                    "path": path,
                    "path_display": " ➔ ".join(path),
                    "total_cost": round(metrics["total_cost"], 2),
                    "total_latency": round(metrics["total_latency"], 1),
                    "success_rate": round(metrics["reliability_prod"] * 100, 2),
                    "hops": len(path) - 1
                }

            if curr_node in visited:
                continue
            visited.add(curr_node)

            for neighbor, cost, latency, reliability in self.graph.get(curr_node, []):
                if neighbor not in visited:
                    weight = cost if criteria == "cost" else latency
                    new_metrics = {
                        "total_cost": metrics["total_cost"] + cost,
                        "total_latency": metrics["total_latency"] + latency,
                        "reliability_prod": metrics["reliability_prod"] * (reliability / 100.0)
                    }
                    heapq.heappush(pq, (curr_weight + weight, neighbor, path + [neighbor], new_metrics))
        return None

    # --- Algorithm 2: Greedy Routing Approach (Immediate Local Optimal Choice) ---
    def greedy_route(self, start_node, end_node):
        current = start_node
        path = [current]
        total_cost = 0
        total_latency = 0
        reliability_prod = 1.0
        visited = {current}

        while current != end_node:
            neighbors = [n for n in self.graph.get(current, []) if n[0] not in visited]
            if not neighbors:
                return None

            best_neighbor = min(neighbors, key=lambda edge: edge[1])
            neighbor_node, cost, latency, reliability = best_neighbor

            path.append(neighbor_node)
            visited.add(neighbor_node)
            total_cost += cost
            total_latency += latency
            reliability_prod *= (reliability / 100.0)
            current = neighbor_node

        return {
            "algorithm": "Greedy Approach (Local Optimal)",
            "path": path,
            "path_display": " ➔ ".join(path),
            "total_cost": round(total_cost, 2),
            "total_latency": round(total_latency, 1),
            "success_rate": round(reliability_prod * 100, 2),
            "hops": len(path) - 1
        }

    # --- Algorithm 3: Breadth-First Search (BFS - Minimum Hops Direct Path) ---
    def bfs_route(self, start_node, end_node):
        queue = deque([(start_node, [start_node], 0, 0, 1.0)])
        visited = {start_node}

        while queue:
            curr_node, path, total_cost, total_latency, reliability_prod = queue.popleft()

            if curr_node == end_node:
                return {
                    "algorithm": "BFS (Minimum Hops Direct Path)",
                    "path": path,
                    "path_display": " ➔ ".join(path),
                    "total_cost": round(total_cost, 2),
                    "total_latency": round(total_latency, 1),
                    "success_rate": round(reliability_prod * 100, 2),
                    "hops": len(path) - 1
                }

            for neighbor, cost, latency, reliability in self.graph.get(curr_node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((
                        neighbor,
                        path + [neighbor],
                        total_cost + cost,
                        total_latency + latency,
                        reliability_prod * (reliability / 100.0)
                    ))
        return None

def load_network_from_db():
    network = PaymentNetworkGraph()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT source_node, target_node, cost_inr, latency_ms, reliability_pct FROM routing_edges")
    for row in cursor.fetchall():
        network.add_edge(row["source_node"], row["target_node"], row["cost_inr"], row["latency_ms"], row["reliability_pct"])
    conn.close()
    return network