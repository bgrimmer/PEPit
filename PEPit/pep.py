import numpy as np
import cvxpy as cp

from PEPit.point import Point
from PEPit.expression import Expression
from PEPit.function import Function


class PEP(object):
    """
    PEP class
    """
    # Class counter.
    # It counts the number of PEP defined instantiated.
    counter = 0

    def __init__(self):

        # Set all counters to 0 to recreate points, expressions and functions from scratch at the beginning of each PEP.
        Point.counter = 0
        Expression.counter = 0
        Function.counter = 0

        # Update the class counter
        self.counter = PEP.counter
        PEP.counter += 1

        # Initialize list of functions,
        # points and conditions that are independent of the functions,
        # as well as the list of performance metric.
        # The PEP will maximize the minimum of the latest.
        self.list_of_functions = list()
        self.list_of_points = list()
        self.list_of_conditions = list()
        self.list_of_performance_metrics = list()

    def declare_function(self, function_class, param, is_differentiable=True):
        """
        Instantiate a function

        :param function_class: (class) a class of function that overwrites the class Function
        :param param: (dict) dictionary of variables needed to define the function
        :param is_differentiable: (bool) whether the function can admit different gradients in a same point

        :return: (Function) the newly created function
        """

        # Create the function
        f = function_class(param, is_leaf=True, decomposition_dict=None, is_differentiable=is_differentiable)

        # Store it in list_of_functions
        self.list_of_functions.append(f)

        # Return it
        return f

    def set_initial_point(self):
        """
        Create a new point from scratch

        :return: (Point)
        """

        # Create a new point from scratch
        x = Point(is_leaf=True, decomposition_dict=None)

        # Store it in list_of_points
        self.list_of_points.append(x)

        # Return it
        return x

    def set_initial_condition(self, condition):
        """
        Add a constraint manually, typically an initial condition

        :param condition: (Expression) typically an inequality between expressions
        """

        # Store condition in the appropriate list
        self.list_of_conditions.append(condition)

    def set_performance_metric(self, expression):
        """
        Define a performance metric

        :param expression: (Expression)
        """

        # Store performance metric in the appropriate list
        self.list_of_performance_metrics.append(expression)

    @staticmethod
    def expression_to_cvxpy(expression, F, G):
        """
        Create a cvxpy compatible expression from an Expression

        :param expression: (Expression) Any expression
        :param F: (cvxpy Variable) A vector representing the function values
        :param G: (cvxpy Variable) A matrix representing the gram of all points

        :return: (cvxpy Variable) the expression in terms of F and G
        """
        cvxpy_variable = 0
        Fweights = np.zeros((Expression.counter,))
        Gweights = np.zeros((Point.counter, Point.counter))

        # If simple function value, then simply return the right coordinate in F
        if expression._is_function_value:
            Fweights[expression.counter] += 1
        # If composite, combine all the cvxpy expression found from basis expressions
        else:
            for key, weight in expression.decomposition_dict.items():
                # Function values are stored in F
                if type(key) == Expression:
                    assert key._is_function_value
                    Fweights[key.counter] += weight
                # Inner products are stored in G
                elif type(key) == tuple:
                    point1, point2 = key
                    assert point1._is_leaf
                    assert point2._is_leaf
                    Gweights[point1.counter, point2.counter] += weight
                # Constants are simply constants
                elif key == 1:
                    cvxpy_variable += weight
                # Others don't exist and raise an Exception
                else:
                    raise TypeError("Expressions are made of function values, inner products and constants only!")

        cvxpy_variable += F@Fweights + cp.sum(cp.multiply(G, Gweights))

        # Return the input expression in a cvxpy variable
        return cvxpy_variable

    def solve(self, solver=cp.SCS, verbose=1):
        """
        Solve the PEP

        :param solver: (str) the name of the underlying solver.
        :param verbose: (int) Level of information details to print (0 or 1)

        :return: (float) value of the performance metric
        """

        # Define the cvxpy variables
        objective = cp.Variable((1,))
        F = cp.Variable((Expression.counter,))
        G = cp.Variable((Point.counter, Point.counter), PSD=True)
        if verbose:
            print('(PEP-it) Setting up the problem:'
                  ' size of the main PSD matrix: {}x{}'.format(Point.counter, Point.counter))

        # Express the constraints from F, G and objective
        constraints_list = list()

        # Defining performance metrics
        # Note maximizing the minimum of all the performance metrics
        # is equivalent to maximize objective which is constraint to be smaller than all the performance metrics.
        for performance_metric in self.list_of_performance_metrics:
            constraints_list.append(objective <= self.expression_to_cvxpy(performance_metric, F, G))
        if verbose:
            print('(PEP-it) Setting up the problem:'
                  ' performance measure is minimum of {} element(s)'.format(len(self.list_of_performance_metrics)))

        # Defining initial conditions
        for condition in self.list_of_conditions:
            constraints_list.append(self.expression_to_cvxpy(condition, F, G) <= 0)
        if verbose:
            print('(PEP-it) Setting up the problem:'
                  ' initial conditions ({} constraint(s) added)'.format(len(self.list_of_conditions)))

        # Defining class constraints
        if verbose:
            print('(PEP-it) Setting up the problem:'
                  ' interpolation conditions for {} function(s)'.format(len(self.list_of_functions)))
        function_counter = 0
        for function in self.list_of_functions:
            function.add_class_constraints()
            function_counter += 1
            for constraint in function.list_of_constraints:
                constraints_list.append(self.expression_to_cvxpy(constraint, F, G) <= 0)
            if verbose:
                print('\t\t function', function_counter, ':', len(function.list_of_constraints), 'constraint(s) added')

        # Create the cvxpy problem
        if verbose:
            print('(PEP-it) Compiling SDP')
        prob = cp.Problem(objective=cp.Maximize(objective), constraints=constraints_list)

        # Solve it
        if verbose:
            print('(PEP-it) Calling SDP solver')
        prob.solve(solver=solver)
        if verbose:
            print('(PEP-it) Solver status: {} (solver: {}); optimal value: {}'.format(prob.status,
                                                                                      prob.solver_stats.solver_name,
                                                                                      prob.value))

        # Store all the values of points and function values
        self.eval_points_and_function_values(F.value, G.value)

        # Return the value of the minimal performance metric
        return prob.value

    def eval_points_and_function_values(self, F_value, G_value):
        """
        Store values of points and function values from the result of the PEP

        :param F_value: (nd.array) value of the cvxpy variable F
        :param G_value: (nd.array) value of the cvxpy variable G
        """

        # Write the gram matrix G as M.T M to extract points' values
        eig_val, eig_vec = np.linalg.eig(G_value)

        # Verify negative eigenvalues are only precision mistakes and get rid of negative eigenvalues
        assert np.min(eig_val) >= - 10**-4
        eig_val = np.maximum(eig_val, 0)

        # Extracts points values
        points_values = np.linalg.qr((np.sqrt(eig_val) * eig_vec).T, mode='r')

        # Iterate over point and function value
        # Set the attribute value of all leaf variables to the right value
        # Note the other ones are not stored until user asks to eval them
        for point in self.list_of_points:
            if point._is_leaf:
                point.value = points_values[:, point.counter]
        for function in self.list_of_functions:
            if function._is_leaf:
                for triplet in function.list_of_points:
                    point, gradient, function_value = triplet
                    if point._is_leaf:
                        point.value = points_values[:, point.counter]
                    if gradient._is_leaf:
                        gradient.value = points_values[:, gradient.counter]
                    if function_value._is_function_value:
                        function_value.value = F_value[function_value.counter]
