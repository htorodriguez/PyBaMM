#
# Class for ohmic electrodes in the surface potential formulation
#
import pybamm

from .base_ohm import BaseModel


class SurfaceForm(BaseModel):
    """A submodel for the electrode with Ohm's law in the surface potential
    formulation.

    Parameters
    ----------
    param : parameter class
        The parameters to use for this submodel
    domain : str
        Either 'Negative' or 'Positive'


    **Extends:** :class:`pybamm.electrode.ohm.BaseModel`
    """

    def __init__(self, param, domain):
        super().__init__(param, domain)

    def get_coupled_variables(self, variables):

        param = self.param
        x_n = pybamm.standard_spatial_vars.x_n
        x_p = pybamm.standard_spatial_vars.x_p
        i_boundary_cc = variables["Current collector current density"]
        i_e = variables[self.domain + " electrolyte current density"]
        eps = variables[self.domain + " electrode porosity"]
        phi_s_cn = variables["Negative current collector potential"]

        i_s = pybamm.PrimaryBroadcast(i_boundary_cc, self.domain_for_broadcast) - i_e

        if self.domain == "Negative":
            conductivity = param.sigma_n * (1 - eps) ** param.b_n
            phi_s = pybamm.PrimaryBroadcast(
                phi_s_cn, "negative electrode"
            ) - pybamm.IndefiniteIntegral(i_s / conductivity, x_n)

        elif self.domain == "Positive":

            phi_e_s = variables["Separator electrolyte potential"]
            delta_phi_p = variables["Positive electrode surface potential difference"]

            conductivity = param.sigma_p * (1 - eps) ** param.b_p
            phi_s = -pybamm.IndefiniteIntegral(
                i_s / conductivity, x_p
            ) + pybamm.PrimaryBroadcast(
                pybamm.boundary_value(phi_e_s, "right")
                + pybamm.boundary_value(delta_phi_p, "left"),
                "positive electrode",
            )

        variables.update(self._get_standard_potential_variables(phi_s))
        variables.update(self._get_standard_current_variables(i_s))

        if (
            "Negative electrode current density" in variables
            and "Positive electrode current density" in variables
        ):
            variables.update(self._get_standard_whole_cell_variables(variables))

        return variables

    @property
    def default_solver(self):
        """
        Create and return the default solver for this model
        """
        return pybamm.ScikitsDaeSolver()
