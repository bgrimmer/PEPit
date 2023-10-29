import numpy as np

from PEPit import PEP
from PEPit.functions import ConvexFunction
from PEPit.functions import ConvexIndicatorFunction
from PEPit.primitive_steps import bregman_gradient_step


def wc_no_lips_1(L, gamma, n, wrapper="cvxpy", solver=None, verbose=1):
    """
    Consider the constrainted non-convex minimization problem

    .. math:: F_\\star \\triangleq \\min_x \\{F(x) \equiv f_1(x)+f_2(x) \\}

    where :math:`f_2` is a closed convex indicator function and :math:`f_1` is possibly non-convex
    and :math:`L`-smooth relatively to :math:`h`,
    and where :math:`h` is closed proper and convex.

    This code computes a worst-case guarantee for the **NoLips** method.
    That is, it computes the smallest possible :math:`\\tau(n, L, \\gamma)` such that the guarantee

    .. math:: \\min_{0 \\leqslant t \\leqslant n-1} D_h(x_{t+1}; x_t) \\leqslant \\tau(n, L, \\gamma)  (F(x_0) - F(x_n))

    is valid, where :math:`x_n` is the output of the **NoLips** method,
    and where :math:`D_h` is the Bregman distance generated by :math:`h`:

    .. math:: D_h(x; y) \\triangleq h(x) - h(y) - \\nabla h (y)^T(x - y).

    In short, for given values of :math:`n`, :math:`L`, and :math:`\\gamma`, :math:`\\tau(n, L, \\gamma)` is computed
    as the worst-case value of :math:`\\min_{0 \\leqslant t \\leqslant n-1}D_h(x_{t+1}; x_t)` when
    :math:`F(x_0) - F(x_n) \\leqslant 1`.

    **Algorithms**:  This method (also known as Bregman Gradient, or Mirror descent) can be found in,
    e.g., [1, Section 3]. For :math:`t \\in \\{0, \\dots, n-1\\}`,

    .. math:: x_{t+1} = \\arg\\min_{u \\in R^d} \\nabla f(x_t)^T(u - x_t) + \\frac{1}{\\gamma} D_h(u; x_t).

    **Theoretical guarantees**: The **tight** theoretical upper bound is obtained in [1, Proposition 4.1]

        .. math:: \\min_{0 \\leqslant t \\leqslant n-1} D_h(x_{t+1}; x_t) \\leqslant \\frac{\\gamma}{n(1 - L\\gamma)}(F(x_0) - F(x_n))

    **References**: The detailed setup and results are availaible in [1]. The PEP approach for studying such settings
    is presented in [2].

    `[1] J. Bolte, S. Sabach, M. Teboulle, Y. Vaisbourd (2018).
    First order methods beyond convexity and Lipschitz gradient continuity
    with applications to quadratic inverse problems.
    SIAM Journal on Optimization, 28(3), 2131-2151.
    <https://arxiv.org/pdf/1706.06461.pdf>`_

    `[2] R. Dragomir, A. Taylor, A. d’Aspremont, J. Bolte (2021).
    Optimal complexity and certification of Bregman first-order methods.
    Mathematical Programming, 1-43.
    <https://arxiv.org/pdf/1911.08510.pdf>`_

    DISCLAIMER: This example requires some experience with PEPit and PEPs (see Section 4 in [2]).

    Args:
        L (float): relative-smoothness parameter.
        gamma (float): step-size (equal to 1/(2*L) for guarantee).
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
        >>> pepit_tau, theoretical_tau = wc_no_lips_1(L=L, gamma=gamma, n=5, wrapper="cvxpy", solver=None, verbose=1)
        (PEPit) Setting up the problem: size of the Gram matrix: 20x20
        (PEPit) Setting up the problem: performance measure is minimum of 5 element(s)
        (PEPit) Setting up the problem: Adding initial conditions and general constraints ...
        (PEPit) Setting up the problem: initial conditions and general constraints (1 constraint(s) added)
        (PEPit) Setting up the problem: interpolation conditions for 3 function(s)
        			Function 1 : Adding 30 scalar constraint(s) ...
        			Function 1 : 30 scalar constraint(s) added
        			Function 2 : Adding 30 scalar constraint(s) ...
        			Function 2 : 30 scalar constraint(s) added
        			Function 3 : Adding 49 scalar constraint(s) ...
        			Function 3 : 49 scalar constraint(s) added
        (PEPit) Setting up the problem: additional constraints for 0 function(s)
        (PEPit) Compiling SDP
        (PEPit) Calling SDP solver
        (PEPit) Solver status: optimal (wrapper:cvxpy, solver: MOSEK); optimal value: 0.19999999999153728
        (PEPit) Primal feasibility check:
        		The solver found a Gram matrix that is positive semi-definite
        		All the primal scalar constraints are verified up to an error of 2.4158453015843406e-12
        (PEPit) Dual feasibility check:
        		The solver found a residual matrix that is positive semi-definite
        		All the dual scalar values associated to inequality constraints are nonnegative up to an error of 2.575910023000674e-12
        (PEPit) The worst-case guarantee proof is perfectly reconstituted up to an error of 4.834893737462826e-11
        (PEPit) Final upper bound (dual): 0.19999999999319756 and lower bound (primal example): 0.19999999999153728 
        (PEPit) Duality gap: absolute: 1.6602830221756903e-12 and relative: 8.301415111229714e-12
        *** Example file: worst-case performance of the NoLips in Bregman divergence ***
        	PEPit guarantee:		 min_t Dh(x_(t+1), x_(t)) <= 0.2 (F(x_0) - F(x_n))
        	Theoretical guarantee :	 min_t Dh(x_(t+1), x_(t)) <= 0.2 (F(x_0) - F(x_n))
    
    """

    # Instantiate PEP
    problem = PEP()

    # Declare two convex functions and a convex indicator function
    d1 = problem.declare_function(ConvexFunction, reuse_gradient=True)
    d2 = problem.declare_function(ConvexFunction, reuse_gradient=True)
    func1 = (d2 - d1) / 2
    h = (d1 + d2) / 2 / L
    func2 = problem.declare_function(ConvexIndicatorFunction, D=np.inf)

    # Define the function to optimize as the sum of func1 and func2
    func = func1 + func2

    # Then define the starting point x0 of the algorithm and its function value f0
    x0 = problem.set_initial_point()
    gh0, h0 = h.oracle(x0)
    gf0, f0 = func1.oracle(x0)
    _, F0 = func.oracle(x0)

    # Compute n steps of the NoLips starting from x0
    xx = [x0 for _ in range(n + 1)]
    gfx = gf0
    ghx = [gh0 for _ in range(n + 1)]
    hx = [h0 for _ in range(n + 1)]
    for i in range(n):
        xx[i + 1], _, _ = bregman_gradient_step(gfx, ghx[i], func2 + h, gamma)
        gfx, _ = func1.oracle(xx[i + 1])
        ghx[i + 1], hx[i + 1] = h.oracle(xx[i + 1])
        Dh = hx[i + 1] - hx[i] - ghx[i] * (xx[i + 1] - xx[i])
        # Set the performance metric to the final distance in Bregman distances to the last iterate
        problem.set_performance_metric(Dh)
    _, Fx = func.oracle(xx[n])

    # Set the initial constraint that is the distance in function values between x0 and x^*
    problem.set_initial_condition(F0 - Fx <= 1)

    # Solve the PEP
    pepit_verbose = max(verbose, 0)
    pepit_tau = problem.solve(wrapper=wrapper, solver=solver, verbose=pepit_verbose)

    # Compute theoretical guarantee (for comparison)
    theoretical_tau = gamma / (n * (1 - L * gamma))

    # Print conclusion if required
    if verbose != -1:
        print('*** Example file: worst-case performance of the NoLips in Bregman divergence ***')
        print('\tPEPit guarantee:\t\t min_t Dh(x_(t+1), x_(t)) <= {:.6} (F(x_0) - F(x_n))'.format(pepit_tau))
        print('\tTheoretical guarantee :\t min_t Dh(x_(t+1), x_(t)) <= {:.6} (F(x_0) - F(x_n))'.format(theoretical_tau))

    # Return the worst-case guarantee of the evaluated method (and the upper theoretical value)
    return pepit_tau, theoretical_tau


if __name__ == "__main__":
    L = 1
    gamma = 1 / (2 * L)
    pepit_tau, theoretical_tau = wc_no_lips_1(L=L, gamma=gamma, n=5, wrapper="cvxpy", solver=None, verbose=1)
