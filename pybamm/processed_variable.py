#
# Processed Variable class
#
import numbers
import numpy as np
import pybamm
import scipy.interpolate as interp


def post_process_variables(variables, t_sol, u_sol, mesh=None, interp_kind="linear"):
    """
    Post-process all variables in a model

    Parameters
    ----------
    variables : dict
        Dictionary of variables
    t_sol : array_like, size (m,)
        The time vector returned by the solver
    u_sol : array_like, size (m, k)
        The solution vector returned by the solver. Can include solution values that
        other than those that get read by base_variable.evaluate() (i.e. k>=n)
    mesh : :class:`pybamm.Mesh`
        The mesh used to solve, used here to calculate the reference x values for
        interpolation
    interp_kind : str
        The method to use for interpolation

    Returns
    -------
    dict
        Dictionary of processed variables
    """
    processed_variables = {}
    known_evals = {t: {} for t in t_sol}
    for var, eqn in variables.items():
        pybamm.logger.debug("Post-processing {}".format(var))
        processed_variables[var] = ProcessedVariable(
            eqn, t_sol, u_sol, mesh, interp_kind, known_evals
        )

        for t in known_evals:
            known_evals[t].update(processed_variables[var].known_evals[t])
    return processed_variables


class ProcessedVariable(object):
    """
    An object that can be evaluated at arbitrary (scalars or vectors) t and x, and
    returns the (interpolated) value of the base variable at that t and x.

    Parameters
    ----------
    base_variable : :class:`pybamm.Symbol`
        A base variable with a method `evaluate(t,y)` that returns the value of that
        variable. Note that this can be any kind of node in the expression tree, not
        just a :class:`pybamm.Variable`.
        When evaluated, returns an array of size (m,n)
    t_sol : array_like, size (m,)
        The time vector returned by the solver
    u_sol : array_like, size (m, k)
        The solution vector returned by the solver. Can include solution values that
        other than those that get read by base_variable.evaluate() (i.e. k>=n)
    mesh : :class:`pybamm.Mesh`
        The mesh used to solve, used here to calculate the reference x values for
        interpolation
    interp_kind : str
        The method to use for interpolation
    """

    def __init__(
        self,
        base_variable,
        t_sol,
        u_sol,
        mesh=None,
        interp_kind="linear",
        known_evals=None,
    ):
        self.base_variable = base_variable
        self.t_sol = t_sol
        self.u_sol = u_sol
        self.mesh = mesh
        self.interp_kind = interp_kind
        self.domain = base_variable.domain
        self.auxiliary_domains = base_variable.auxiliary_domains
        self.known_evals = known_evals

        if self.known_evals:
            self.base_eval, self.known_evals[t_sol[0]] = base_variable.evaluate(
                t_sol[0], u_sol[:, 0], self.known_evals[t_sol[0]]
            )
        else:
            self.base_eval = base_variable.evaluate(t_sol[0], u_sol[:, 0])

        # handle 2D (in space) finite element variables differently
        if (
            mesh
            and "current collector" in self.domain
            and isinstance(self.mesh[self.domain[0]][0], pybamm.ScikitSubMesh2D)
        ):
            if len(self.t_sol) == 1:
                # space only (steady solution)
                self.initialise_2Dspace_scikit_fem()
            else:
                self.initialise_3D_scikit_fem()

        # check variable shape
        elif (
            isinstance(self.base_eval, numbers.Number)
            or len(self.base_eval.shape) == 0
            or self.base_eval.shape[0] == 1
        ):
            self.initialise_1D()
        else:
            n = self.mesh.combine_submeshes(*self.domain)[0].npts
            base_shape = self.base_eval.shape[0]
            if base_shape in [n, n + 1]:
                self.initialise_2D()
            else:
                self.initialise_3D()

        # Remove base_variable attribute to allow pickling
        del self.base_variable

    def initialise_1D(self):
        # initialise empty array of the correct size
        entries = np.empty(len(self.t_sol))
        # Evaluate the base_variable index-by-index
        for idx in range(len(self.t_sol)):
            t = self.t_sol[idx]
            if self.known_evals:
                entries[idx], self.known_evals[t] = self.base_variable.evaluate(
                    t, self.u_sol[:, idx], self.known_evals[t]
                )
            else:
                entries[idx] = self.base_variable.evaluate(t, self.u_sol[:, idx])

        # No discretisation provided, or variable has no domain (function of t only)
        self._interpolation_function = interp.interp1d(
            self.t_sol,
            entries,
            kind=self.interp_kind,
            fill_value=np.nan,
            bounds_error=False,
        )

        self.entries = entries
        self.dimensions = 1

    def initialise_2D(self):
        len_space = self.base_eval.shape[0]
        entries = np.empty((len_space, len(self.t_sol)))

        # Evaluate the base_variable index-by-index
        for idx in range(len(self.t_sol)):
            t = self.t_sol[idx]
            u = self.u_sol[:, idx]
            if self.known_evals:
                eval_and_known_evals = self.base_variable.evaluate(
                    t, u, self.known_evals[t]
                )
                entries[:, idx] = eval_and_known_evals[0][:, 0]
                self.known_evals[t] = eval_and_known_evals[1]
            else:
                entries[:, idx] = self.base_variable.evaluate(t, u)[:, 0]

        # Process the discretisation to get x values
        nodes = self.mesh.combine_submeshes(*self.domain)[0].nodes
        edges = self.mesh.combine_submeshes(*self.domain)[0].edges
        if entries.shape[0] == len(nodes):
            space = nodes
        elif entries.shape[0] == len(edges):
            space = edges

        # add points outside domain for extrapolation to boundaries
        extrap_space_left = np.array([2 * space[0] - space[1]])
        extrap_space_right = np.array([2 * space[-1] - space[-2]])
        space = np.concatenate([extrap_space_left, space, extrap_space_right])
        extrap_entries_left = 2 * entries[0] - entries[1]
        extrap_entries_right = 2 * entries[-1] - entries[-2]
        entries = np.vstack([extrap_entries_left, entries, extrap_entries_right])

        # assign attributes for reference (either x_sol or r_sol)
        self.entries = entries
        self.dimensions = 2
        if self.domain[0] in ["negative particle", "positive particle"]:
            self.spatial_var_name = "r"
            self.r_sol = space
        elif self.domain[0] in [
            "negative electrode",
            "separator",
            "positive electrode",
        ]:
            self.spatial_var_name = "x"
            self.x_sol = space
        elif self.domain == ["current collector"]:
            self.spatial_var_name = "z"
            self.z_sol = space
        else:
            self.spatial_var_name = "x"
            self.x_sol = space

        # set up interpolation
        # note that the order of 't' and 'space' is the reverse of what you'd expect

        self._interpolation_function = interp.interp2d(
            self.t_sol, space, entries, kind=self.interp_kind, fill_value=np.nan
        )

    def initialise_3D(self):
        """
        Initialise a 3D object that depends on x and r, or x and z.
        Needs to be generalised to deal with other domains.

        Notes
        -----
        There is different behaviour between a variable on an electrode domain
        broadcast to a particle (such as temperature) and a variable on a particle
        domain broadcast to an electrode (such as particle concentration). We deal with
        this by reshaping the former with the Fortran order ("F") and the latter with
        the C order ("C"). These are transposes of each other, so this approach simply
        avoids having to transpose later.
        """
        # Dealt with weird particle/electrode case
        if self.domain in [
            ["negative electrode"],
            ["positive electrode"],
        ] and self.auxiliary_domains["secondary"] in [
            ["negative particle"],
            ["positive particle"],
        ]:
            # Switch domain and auxiliary domains and set order to Fortran order ("F")
            dom = self.domain
            self.domain = self.auxiliary_domains["secondary"]
            self.auxiliary_domains["secondary"] = dom
            order = "F"
        else:
            # Set order to C order ("C")
            order = "C"

        # Process x-r or x-z
        if self.domain == ["negative particle"] and self.auxiliary_domains[
            "secondary"
        ] == ["negative electrode"]:
            x_sol = self.mesh["negative electrode"][0].nodes
            r_nodes = self.mesh["negative particle"][0].nodes
            r_edges = self.mesh["negative particle"][0].edges
            set_up_r = True
        elif self.domain == ["positive particle"] and self.auxiliary_domains[
            "secondary"
        ] == ["positive electrode"]:
            x_sol = self.mesh["positive electrode"][0].nodes
            r_nodes = self.mesh["positive particle"][0].nodes
            r_edges = self.mesh["positive particle"][0].edges
            set_up_r = True
        elif self.domain[0] in [
            "negative electrode",
            "separator",
            "positive electrode",
        ] and self.auxiliary_domains["secondary"] == ["current collector"]:
            x_nodes = self.mesh.combine_submeshes(*self.domain)[0].nodes
            x_edges = self.mesh.combine_submeshes(*self.domain)[0].edges
            z_sol = self.mesh["current collector"][0].nodes
            r_sol = None
            self.first_dimension = "x"
            self.second_dimension = "z"

            if self.base_eval.size // len(z_sol) == len(x_nodes):
                x_sol = x_nodes
            elif self.base_eval.size // len(z_sol) == len(x_edges):
                x_sol = x_edges
            first_dim_nodes = x_sol
            second_dim_nodes = z_sol
            set_up_r = False
        else:
            raise pybamm.DomainError(
                """ Cannot process 3D object with domain '{}'
                and auxiliary_domains '{}'""".format(
                    self.domain, self.auxiliary_domains
                )
            )
        if set_up_r:
            z_sol = None
            self.first_dimension = "x"
            self.second_dimension = "r"
            if self.base_eval.size // len(x_sol) == len(r_nodes):
                r_sol = r_nodes
            elif self.base_eval.size // len(x_sol) == len(r_edges):
                r_sol = r_edges
            first_dim_nodes = x_sol
            second_dim_nodes = r_sol

        first_dim_size = len(first_dim_nodes)
        second_dim_size = len(second_dim_nodes)
        entries = np.empty((first_dim_size, second_dim_size, len(self.t_sol)))

        # Evaluate the base_variable index-by-index
        for idx in range(len(self.t_sol)):
            t = self.t_sol[idx]
            u = self.u_sol[:, idx]
            if self.known_evals:
                eval_and_known_evals = self.base_variable.evaluate(
                    t, u, self.known_evals[t]
                )
                entries[:, :, idx] = np.reshape(
                    eval_and_known_evals[0],
                    [first_dim_size, second_dim_size],
                    order=order,
                )
                self.known_evals[t] = eval_and_known_evals[1]
            else:
                entries[:, :, idx] = np.reshape(
                    self.base_variable.evaluate(t, u),
                    [first_dim_size, second_dim_size],
                    order=order,
                )

        # assign attributes for reference
        self.entries = entries
        self.dimensions = 3
        self.x_sol = x_sol
        self.r_sol = r_sol
        self.z_sol = z_sol

        # set up interpolation
        self._interpolation_function = interp.RegularGridInterpolator(
            (first_dim_nodes, second_dim_nodes, self.t_sol),
            entries,
            method=self.interp_kind,
            fill_value=np.nan,
        )

    def initialise_2Dspace_scikit_fem(self):
        y_sol = self.mesh[self.domain[0]][0].edges["y"]
        len_y = len(y_sol)
        z_sol = self.mesh[self.domain[0]][0].edges["z"]
        len_z = len(z_sol)

        # Evaluate the base_variable
        entries = np.reshape(self.base_variable.evaluate(0, self.u_sol), [len_y, len_z])

        # assign attributes for reference
        self.entries = entries
        self.dimensions = 2
        self.y_sol = y_sol
        self.z_sol = z_sol
        self.first_dimension = "y"
        self.second_dimension = "z"

        # set up interpolation
        self._interpolation_function = interp.interp2d(
            y_sol, z_sol, entries, kind=self.interp_kind, fill_value=np.nan
        )

    def initialise_3D_scikit_fem(self):
        y_sol = self.mesh[self.domain[0]][0].edges["y"]
        len_y = len(y_sol)
        z_sol = self.mesh[self.domain[0]][0].edges["z"]
        len_z = len(z_sol)
        entries = np.empty((len_y, len_z, len(self.t_sol)))

        # Evaluate the base_variable index-by-index
        for idx in range(len(self.t_sol)):
            t = self.t_sol[idx]
            u = self.u_sol[:, idx]
            if self.known_evals:
                eval_and_known_evals = self.base_variable.evaluate(
                    t, u, self.known_evals[t]
                )
                entries[:, :, idx] = np.reshape(eval_and_known_evals[0], [len_y, len_z])
                self.known_evals[t] = eval_and_known_evals[1]
            else:
                entries[:, :, idx] = np.reshape(
                    self.base_variable.evaluate(t, u), [len_y, len_z]
                )

        # assign attributes for reference
        self.entries = entries
        self.dimensions = 3
        self.y_sol = y_sol
        self.z_sol = z_sol
        self.first_dimension = "y"
        self.second_dimension = "z"

        # set up interpolation
        self._interpolation_function = interp.RegularGridInterpolator(
            (y_sol, z_sol, self.t_sol),
            entries,
            method=self.interp_kind,
            fill_value=np.nan,
        )

    def __call__(self, t=None, x=None, r=None, y=None, z=None, warn=True):
        """
        Evaluate the variable at arbitrary t (and x, r, y and/or z), using interpolation
        """
        if self.dimensions == 1:
            out = self._interpolation_function(t)
        elif self.dimensions == 2:
            if t is None:
                out = self._interpolation_function(y, z)
            else:
                out = self.call_2D(t, x, r, z)
        elif self.dimensions == 3:
            out = self.call_3D(t, x, r, y, z)
        if warn is True and np.isnan(out).any():
            pybamm.logger.warning(
                "Calling variable outside interpolation range (returns 'nan')"
            )
        return out

    def call_2D(self, t, x, r, z):
        "Evaluate a 2D variable"
        spatial_var = eval_dimension_name(self.spatial_var_name, x, r, None, z)
        return self._interpolation_function(t, spatial_var)

    def call_3D(self, t, x, r, y, z):
        "Evaluate a 3D variable"
        first_dim = eval_dimension_name(self.first_dimension, x, r, y, z)
        second_dim = eval_dimension_name(self.second_dimension, x, r, y, z)
        if isinstance(first_dim, np.ndarray):
            if isinstance(second_dim, np.ndarray) and isinstance(t, np.ndarray):
                first_dim = first_dim[:, np.newaxis, np.newaxis]
                second_dim = second_dim[:, np.newaxis]
            elif isinstance(second_dim, np.ndarray) or isinstance(t, np.ndarray):
                first_dim = first_dim[:, np.newaxis]
        else:
            if isinstance(second_dim, np.ndarray) and isinstance(t, np.ndarray):
                second_dim = second_dim[:, np.newaxis]

        return self._interpolation_function((first_dim, second_dim, t))


def eval_dimension_name(name, x, r, y, z):
    if name == "x":
        out = x
    elif name == "r":
        out = r
    elif name == "y":
        out = y
    elif name == "z":
        out = z

    if out is None:
        raise ValueError("inputs {} cannot be None".format(name))
    else:
        return out
