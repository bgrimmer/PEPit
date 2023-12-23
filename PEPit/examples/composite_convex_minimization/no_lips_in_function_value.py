import numpy as np

from PEPit import PEP
from PEPit.functions import ConvexFunction
from PEPit.functions import ConvexIndicatorFunction
from PEPit.primitive_steps import bregman_gradient_step


def wc_no_lips_in_function_value(L, gamma, n, wrapper="cvxpy", solver=None, verbose=1):
    """
    Consider the constrainted composite convex minimization problem

    .. math:: F_\\star \\triangleq \\min_x \\{F(x) \\equiv f_1(x) + f_2(x)\\},

    where :math:`f_1` is convex and :math:`L`-smooth relatively to :math:`h`,
    :math:`h` being closed proper and convex,
    and where :math:`f_2` is a closed convex indicator function.

    This code computes a worst-case guarantee for the **NoLips** method.
    That is, it computes the smallest possible :math:`\\tau(n, L)` such that the guarantee

    .. math :: F(x_n) - F_\\star \\leqslant \\tau(n, L) D_h(x_\\star; x_0),

    is valid, where :math:`x_n` is the output of the **NoLips** method,
    where :math:`x_\\star` is a minimizer of :math:`F`,
    and where :math:`D_h` is the Bregman divergence generated by :math:`h`.
    In short, for given values of :math:`n` and :math:`L`,
    :math:`\\tau(n, L)` is computed as the worst-case value of
    :math:`F(x_n) - F_\\star` when :math:`D_h(x_\\star; x_0) \\leqslant 1`.

    **Algorithm**: This method (also known as Bregman Gradient, or Mirror descent) can be found in,
    e.g., [2, Algorithm 1]. For :math:`t \\in \\{0, \\dots, n-1\\}`,

        .. math:: x_{t+1} = \\arg\\min_{u} \\{f_2(u)+\\langle \\nabla f_1(x_t) \\mid u - x_t \\rangle + \\frac{1}{\\gamma} D_h(u; x_t)\\}.

    **Theoretical guarantee**:

    The **tight** guarantee obtained in [2, Theorem 1] is

        .. math :: F(x_n) - F_\\star \\leqslant \\frac{1}{\\gamma n} D_h(x_\\star; x_0),

    for any :math:`\\gamma \\leq \\frac{1}{L}`; tightness is provided in [2, page 23].

    **References**: NoLips was proposed [1] for convex problems involving relative smoothness.
    The worst-case analysis using a PEP, as well as the tightness are provided in [2].

    `[1] H.H. Bauschke, J. Bolte, M. Teboulle (2017).
    A Descent Lemma Beyond Lipschitz Gradient Continuity: First-Order Methods Revisited and Applications.
    Mathematics of Operations Research, 2017, vol. 42, no 2, p. 330-348.
    <https://cmps-people.ok.ubc.ca/bauschke/Research/103.pdf>`_

    `[2] R. Dragomir, A. Taylor, A. d’Aspremont, J. Bolte (2021).
    Optimal complexity and certification of Bregman first-order methods.
    Mathematical Programming, 1-43.
    <https://arxiv.org/pdf/1911.08510.pdf>`_

    Notes:
        Disclaimer: This example requires some experience with PEPit and PEPs ([2], section 4).

    Args:
        L (float): relative-smoothness parameter.
        gamma (float): step-size.
        n (int): number of iterations.
        wrapper (str): the name of the wrapper to be used.
        solver (str): the name of the solver the wrapper should use.
        verbose (int): level of information details to print.
                        
                        - -1: No verbose at all.
                        - 0: This example's output.
                        - 1: This example's output + PEPit information.
                        - 2: This example's output + PEPit information + solver details.

    Returns:
        pepit_tau (float): worst-case value.
        theoretical_tau (float): theoretical value.

    Example:
        >>> L = 1
        >>> gamma = 1 / (2 * L)
        >>> pepit_tau, theoretical_tau = wc_no_lips_in_function_value(L=L, gamma=gamma, n=3, wrapper="cvxpy", solver=None, verbose=1)
        (PEPit) Setting up the problem: size of the Gram matrix: 15x15
        (PEPit) Setting up the problem: performance measure is the minimum of 1 element(s)
        (PEPit) Setting up the problem: Adding initial conditions and general constraints ...
        (PEPit) Setting up the problem: initial conditions and general constraints (1 constraint(s) added)
        (PEPit) Setting up the problem: interpolation conditions for 3 function(s)
        			Function 1 : Adding 20 scalar constraint(s) ...
        			Function 1 : 20 scalar constraint(s) added
        			Function 2 : Adding 20 scalar constraint(s) ...
        			Function 2 : 20 scalar constraint(s) added
        			Function 3 : Adding 16 scalar constraint(s) ...
        			Function 3 : 16 scalar constraint(s) added
        (PEPit) Setting up the problem: additional constraints for 0 function(s)
        (PEPit) Compiling SDP
        (PEPit) Calling SDP solver
        (PEPit) Solver status: optimal (wrapper:cvxpy, solver: MOSEK); optimal value: 0.6666666666481619
        (PEPit) Primal feasibility check:
        		The solver found a Gram matrix that is positive semi-definite
        		All the primal scalar constraints are verified up to an error of 1.4396019099027768e-11
        (PEPit) Dual feasibility check:
        		The solver found a residual matrix that is positive semi-definite up to an error of 1.039633194677115e-21
        		All the dual scalar values associated with inequality constraints are nonnegative up to an error of 1.4920273295805233e-11
        (PEPit) The worst-case guarantee proof is perfectly reconstituted up to an error of 2.426985490058363e-10
        (PEPit) Final upper bound (dual): 0.666666666662425 and lower bound (primal example): 0.6666666666481619 
        (PEPit) Duality gap: absolute: 1.4263146219661849e-11 and relative: 2.139471933008663e-11
        *** Example file: worst-case performance of the NoLips in function values ***
        	PEPit guarantee:		 F(x_n) - F_* <= 0.666667 Dh(x_*; x_0)
        	Theoretical guarantee:	 F(x_n) - F_* <= 0.666667 Dh(x_*; x_0)
    
    """

    # Instantiate PEP
    problem = PEP()

    # Declare two convex functions and a convex indicator function
    d = problem.declare_function(ConvexFunction, reuse_gradient=True)
    func1 = problem.declare_function(ConvexFunction, reuse_gradient=True)
    h = (d + func1) / L
    func2 = problem.declare_function(ConvexIndicatorFunction, D=np.inf)
    # Define the function to optimize as the sum of func1 and func2
    func = func1 + func2

    # Start by defining its unique optimal point xs = x_* and its function value fs = F(x_*)
    xs = func.stationary_point()
    ghs, hs = h.oracle(xs)
    gfs, fs = func1.oracle(xs)

    # Then define the starting point x0 of the algorithm and its function value f0
    x0 = problem.set_initial_point()
    gh0, h0 = h.oracle(x0)
    gf0, f0 = func1.oracle(x0)

    # Set the initial constraint that is the Bregman distance between x0 and x^*
    problem.set_initial_condition(hs - h0 - gh0 * (xs - x0) <= 1)

    # Compute n steps of the NoLips starting from x0
    gfx = gf0
    ffx = f0
    ghx = gh0
    for i in range(n):
        x, _, _ = bregman_gradient_step(gfx, ghx, func2 + h, gamma)
        gfx, ffx = func1.oracle(x)
        gdx = d.gradient(x)
        ghx = (gdx + gfx) / L

    # Set the performance metric to the final distance in function values to optimum
    problem.set_performance_metric(ffx - fs)

    # Solve the PEP
    pepit_verbose = max(verbose, 0)
    pepit_tau = problem.solve(wrapper=wrapper, solver=solver, verbose=pepit_verbose)

    # Compute theoretical guarantee (for comparison)
    theoretical_tau = 1 / (gamma * n)

    # Print conclusion if required
    if verbose != -1:
        print('*** Example file: worst-case performance of the NoLips in function values ***')
        print('\tPEPit guarantee:\t\t F(x_n) - F_* <= {:.6} Dh(x_*; x_0)'.format(pepit_tau))
        print('\tTheoretical guarantee:\t F(x_n) - F_* <= {:.6} Dh(x_*; x_0)'.format(theoretical_tau))
    # Return the worst-case guarantee of the evaluated method (and the upper theoretical value)
    return pepit_tau, theoretical_tau


if __name__ == "__main__":
    L = 1
    gamma = 1 / (2 * L)
    pepit_tau, theoretical_tau = wc_no_lips_in_function_value(L=L, gamma=gamma, n=3,
                                                              wrapper="cvxpy", solver=None,
                                                              verbose=1)
