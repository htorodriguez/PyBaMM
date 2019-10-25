#
# Full model of electrode employing Ohm's law
#
import pybamm
from .base_ohm import BaseModel


class Full(BaseModel):
    """Full model of electrode employing Ohm's law.

    Parameters
    ----------
    param : parameter class
        The parameters to use for this submodel
    domain : str
        Either 'Negative' or 'Positive'


    **Extends:** :class:`pybamm.electrode.ohm.BaseModel`
    """

    def __init__(self, param, domain, reactions):
        super().__init__(param, domain, reactions)

    def get_fundamental_variables(self):

        if self.domain == "Negative":
            phi_s = pybamm.standard_variables.phi_s_n
        elif self.domain == "Positive":
            phi_s = pybamm.standard_variables.phi_s_p

        variables = self._get_standard_potential_variables(phi_s)

        return variables

    def get_coupled_variables(self, variables):

        phi_s = variables[self.domain + " electrode potential"]
        eps = variables[self.domain + " electrode porosity"]

        if self.domain == "Negative":
            sigma = self.param.sigma_n
            b = self.param.b_n
        elif self.domain == "Positive":
            sigma = self.param.sigma_p
            b = self.param.b_p

        sigma_eff = sigma * (1 - eps) ** b
        i_s = -sigma_eff * pybamm.grad(phi_s)

        variables.update({self.domain + " electrode effective conductivity": sigma_eff})

        variables.update(self._get_standard_current_variables(i_s))

        if self.domain == "Positive":
            variables.update(self._get_standard_whole_cell_variables(variables))

        return variables

    def set_algebraic(self, variables):

        phi_s = variables[self.domain + " electrode potential"]
        i_s = variables[self.domain + " electrode current density"]
        sum_j = sum(
            variables[reaction[self.domain]["aj"]]
            for reaction in self.reactions.values()
        )

        self.algebraic[phi_s] = pybamm.div(i_s) + sum_j

    def set_boundary_conditions(self, variables):

        phi_s = variables[self.domain + " electrode potential"]
        phi_s_cn = variables["Negative current collector potential"]
        eps = variables[self.domain + " electrode porosity"]
        i_boundary_cc = variables["Current collector current density"]

        if self.domain == "Negative":
            lbc = (phi_s_cn, "Dirichlet")
            rbc = (pybamm.Scalar(0), "Neumann")

        elif self.domain == "Positive":
            lbc = (pybamm.Scalar(0), "Neumann")
            sigma_eff = self.param.sigma_p * (1 - eps) ** self.param.b_p
            rbc = (
                i_boundary_cc / pybamm.boundary_value(-sigma_eff, "right"),
                "Neumann",
            )

        self.boundary_conditions[phi_s] = {"left": lbc, "right": rbc}

    def set_initial_conditions(self, variables):

        phi_s = variables[self.domain + " electrode potential"]
        T_ref = self.param.T_ref

        if self.domain == "Negative":
            phi_s_init = pybamm.Scalar(0)
        elif self.domain == "Positive":
            phi_s_init = self.param.U_p(self.param.c_p_init, T_ref) - self.param.U_n(
                self.param.c_n_init, T_ref
            )

        self.initial_conditions[phi_s] = phi_s_init

    @property
    def default_solver(self):
        """
        Create and return the default solver for this model
        """
        return pybamm.ScikitsDaeSolver()
