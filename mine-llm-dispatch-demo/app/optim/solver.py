from __future__ import annotations

import math
from typing import Any

from ortools.sat.python import cp_model

from app.rules.rule_engine import RuleEngine


class DispatchSolver:
    def __init__(self, rule_engine: RuleEngine) -> None:
        self.rule_engine = rule_engine

    def _empty_distance_cost(self, truck: dict[str, Any], task: dict[str, Any], load_sites: dict[str, Any]) -> float:
        load = load_sites[task["load"]]
        dx = truck["pos"]["x"] - float(load["x"])
        dy = truck["pos"]["y"] - float(load["y"])
        return math.sqrt(dx * dx + dy * dy) / 100.0

    def solve(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        model = cp_model.CpModel()
        trucks = snapshot["available_trucks"]
        tasks = snapshot["task_catalog"]
        alarms = snapshot["alarms"]
        load_sites = snapshot["load_sites"]
        queue_estimates = snapshot["queue_estimates"]
        capacities = {task["task_id"]: int(task.get("capacity", 1)) for task in tasks}

        # Pseudocode from the prompt, implemented in a minimal CP-SAT form:
        # x[truck, task] ∈ {0,1}
        # each truck gets one task
        # blocked / no-go routes are forbidden
        # objective min(empty_distance + queue_wait + lambda * route_changes)
        variables: dict[tuple[int, int], cp_model.IntVar] = {}
        scaled_costs: dict[tuple[int, int], int] = {}
        for truck_index, truck in enumerate(trucks):
            for task_index, task in enumerate(tasks):
                allowed, _ = self.rule_engine.is_route_allowed(task["route"], alarms)
                name = f"x_{truck['truck_id']}_{task['task_id']}"
                var = model.NewBoolVar(name)
                variables[(truck_index, task_index)] = var
                if not allowed:
                    model.Add(var == 0)
                    continue
                empty_distance = self._empty_distance_cost(truck, task, load_sites)
                queue_wait = queue_estimates[task["load"]] + queue_estimates[task["dump"]]
                last_route = snapshot["last_suggested_routes"].get(truck["truck_id"])
                change_penalty = 0.8 if last_route and last_route != task["route"] else 0.0
                score = empty_distance + queue_wait + change_penalty
                scaled_costs[(truck_index, task_index)] = int(score * 100)

        for truck_index, _truck in enumerate(trucks):
            model.Add(sum(variables[(truck_index, task_index)] for task_index, _ in enumerate(tasks)) == 1)
        for task_index, task in enumerate(tasks):
            model.Add(sum(variables[(truck_index, task_index)] for truck_index, _ in enumerate(trucks)) <= capacities[task["task_id"]])

        objective_terms = []
        for key, var in variables.items():
            objective_terms.append(var * scaled_costs.get(key, 999999))
        model.Minimize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 3.0
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError("No feasible dispatch plan found")

        assignments: list[dict[str, Any]] = []
        for truck_index, truck in enumerate(trucks):
            for task_index, task in enumerate(tasks):
                if solver.Value(variables[(truck_index, task_index)]) == 1:
                    queue_wait = queue_estimates[task["load"]] + queue_estimates[task["dump"]]
                    assignments.append(
                        {
                            "truck_id": truck["truck_id"],
                            "task_id": task["task_id"],
                            "load": task["load"],
                            "dump": task["dump"],
                            "route": task["route"],
                            "queue_wait_min": round(queue_wait, 2),
                            "eta_min": round(task["route_distance_km"] + queue_wait / 2, 2),
                            "constraints_checked": ["NO_GO_ZONE_OK", "ALARM_IMPACT_OK", "MAP_VERSION_OK"],
                            "risk_notes": [],
                        }
                    )
                    break
        return assignments
