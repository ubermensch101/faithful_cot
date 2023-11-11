'''This module contains the functions to generate a plan for a goal using the online PDDL planner at http://solver.planning.domains/solve.'''

import os
cwd = os.getcwd()
if cwd.endswith("source/model/solver/saycan"):
	os.chdir("../../../..")  # change the working directory to the root directory
import requests
from model.solver.saycan.goal_reformatter import reformat_goal
from model.solver.saycan.saycan_utils import check_goals_equivalence, check_goal_validity
import json
import time

def generate_plan_for_goal(goal, prompt_name):
	'''Generate a plan for a goal.
	@:param goal (str): the goal string
	@:param prompt_name (str): the name of the prompt

	@:return (list): the plan
	'''

	# reformat the goal
	goal = reformat_goal(goal)

	# load the domain and problem files
	if "variation2" in prompt_name: # prompt variation2 uses different variable names, thus requires a different domain file and problem file
		suffix = "_variation2"
	else:
		suffix = ""
	domain_frn = f"source/model/solver/saycan/pddl_files/domain/domain{suffix}.pddl"
	problem_frn = f"source/model/solver/saycan/pddl_files/problem/problem{suffix}.pddl"

	with open(domain_frn, "r") as f:
		domain_str = f.read()

	# check if the goal requires a special initial environment
	goals_with_special_env = load_special_env_goals()
	for special_goal_key, special_goal_value in goals_with_special_env.items():
		if check_goals_equivalence(goal, special_goal_key):
			problem_frn = f"source/model/solver/saycan/pddl_files/problem/problem_{special_goal_value}{suffix}.pddl"
			break

	with open(problem_frn, "r") as f:
		problem_str = f.read()

	# add the goal to the problem file
	problem_str = add_goal_to_problem(goal, problem_str)

	# generate the plan using the online planner
	data = {'domain': domain_str,
	        'problem': problem_str}

	n_tries = 0
	max_retries = 10
	while n_tries <= max_retries:
		resp = requests.post('http://solver.planning.domains/solve', verify=True, json=data)
		resp = resp.json()

		if resp["status"] == "error":
			print(goal)
			print(resp)
			if resp["result"] == "Server busy...":
				# sleep for 5 seconds and try again
				time.sleep(5)
				n_tries += 1
				continue
			else:
				return resp["result"]["error"]
		else:
			if type(resp["result"]["plan"][0]) is str:
				return resp["result"]["plan"]
			else:
				return [act['name'] for act in resp['result']['plan']]
	print("Failed to generate a plan for the goal after 10 tries.")
	return "[invalid]"

def convert_plan_to_nl(plan, goal):
	"""Convert a PDDL plan to natural language.
	@:param plan (list): the PDDL plan, generated by the planner

	@:return (str): the natural language plan, as required by the saycan dataset

	Example:
	Input:
	['(find me water)', '(pick me water initial)', '(go me initial user)', '(put me water user)', '(go me user initial)', '(find me energy-bar)', '(pick me energy-bar initial)', '(go me initial user)', '(put me energy-bar user)', '(reach-goal)']
	Output:
	"1. find(water)
	2. pick(water)
	3. find(user)
	4. put(water)
	5. find(energy bar)
	6. pick(energy bar)
	7. find(user)
	8. put(energy bar)
	9. done()."
	"""
	if not isinstance(plan, list):
		print(f"Error:{plan}")
		return "[error]"

	if "visited" in goal:
		goal_type = "visit"  # the goal is to visit some location(s)
	else:
		goal_type = "retrieve"  # the goal is to retrieve some object(s)

	prev_action = ""
	step_count = 0
	step_strs = []
	for step in plan:
		step = step.strip('()')
		action, args = step.split()[0], step.split()[1:]
		if action == "find":  # find an object
			arg = args[1]
			action_name = action
		elif action == "pick":  # pick up an object
			arg = args[1]
			action_name = action
		elif action == "go":  # go to a location
			if goal_type != "visit" and prev_action == "go":  # if there are two consecutive "go" actions (a to b and b to c), then they can be merged (a to c)
				step_strs.pop()
				step_count -= 1
			action_name = "find"  # the saycan dataset defines this action still as "find"
			arg = args[2]
			if arg == "initial":
				continue
		elif action == "put":  # put down an object
			arg = args[1]
			action_name = action
		elif action == "reach-goal":  # the goal has been reached
			continue
		else:
			raise ValueError(f"Unrecognized action: {action}")
		prev_action = action
		step_count += 1
		arg = map_object_name(arg)
		step_str = f"{step_count}. {action_name}({arg})"
		step_strs.append(step_str)
	step_strs.append(f"{step_count + 1}. done().\n")
	return '\n'.join(step_strs)

def load_special_env_goals():
	''' Load the goals that require a special initial environment (domain file).
	For example, the goal "letting go of coke" requires the initial condition to be "the coke is held by the robot".

	:return (dict): a dictionary mapping the goal to its domain file name.
	'''
	frn = "source/model/solver/saycan/goals_with_special_env.json"
	with open(frn, "r") as f:
		goals_with_special_env = json.load(f)
	return goals_with_special_env

def add_goal_to_problem(goal_str: str, problem_str: str):
	"""Add the goal to the problem string.
	@:param goal_str (str): the goal string
	@:param problem_str (str): the problem string

	@:return (str): the new problem string
	"""
	# validate the domain str
	goal_str = goal_str.strip()
	new_problem_str = problem_str.rstrip()
	assert new_problem_str.endswith(")")
	new_problem_str = problem_str[:-1]

	new_problem_str += f"\n{goal_str}\n)"
	return new_problem_str

def map_object_name(object_name):
	'''Map the object name to the name used in the saycan dataset.
	@:param object_name (str): the object name

	@:return (str): the mapped object name
	'''
	object_name = object_name.replace("-", " ")
	if object_name == "seven up":
		object_name = "7up"
	return  object_name


if __name__ == "__main__":

	goal = '''
  (:goal
	; I need to find a soda that satisfies the following conditions
	(exists (?s - soda)
		; it's not a coke
		(not (= ?s coke))
		; bring it to the user
		(at ?s user)
	)
)
'''

	is_valid = check_goal_validity(goal)
	if not is_valid:
		print("Goal is not valid: ", goal)
		exit(-1)
	plan = generate_plan_for_goal(goal, prompt_name = "noNL")
	print(plan)
	plan_nl = convert_plan_to_nl(plan, goal)
	print(plan_nl)



