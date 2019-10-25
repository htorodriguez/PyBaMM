#
# Simulations: effect of side reactions for charge of a lead-acid battery
#
import argparse
import matplotlib.pyplot as plt
import numpy as np
import pickle
import pybamm
import shared_plotting
from shared_solutions import model_comparison

try:
    from config import OUTPUT_DIR
except ImportError:
    OUTPUT_DIR = None


def plot_voltages(all_variables, t_eval, bigger_beta=False):
    linestyles = ["k-", "b--"]
    shared_plotting.plot_voltages(all_variables, t_eval, linestyles, figsize=(6.4, 2.5))
    if bigger_beta:
        file_name = "convection_voltage_comparison_bigger_beta.eps"
    else:
        file_name = "convection_voltage_comparison.eps"
    plt.subplots_adjust(bottom=0.4)
    if OUTPUT_DIR is not None:
        plt.savefig(OUTPUT_DIR + file_name, format="eps", dpi=1000)


def plot_variables(all_variables, t_eval, bigger_beta=False):
    # Set up
    times = np.array([0.195])
    linestyles = ["k-", "b--"]
    if bigger_beta:
        var_file_names = {
            "Volume-averaged velocity [m.s-1]"
            + "": "convection_velocity_comparison_bigger_beta.eps",
            "Electrolyte concentration [Molar]"
            + "": "convection_electrolyte_concentration_comparison_bigger_beta.eps",
        }
    else:
        var_file_names = {
            "Volume-averaged velocity [m.s-1]": "convection_velocity_comparison.eps",
            "Electrolyte concentration [Molar]"
            + "": "convection_electrolyte_concentration_comparison.eps",
        }
    for var, file_name in var_file_names.items():
        fig, axes = shared_plotting.plot_variable(
            all_variables, times, var, linestyles=linestyles, figsize=(6.4, 3)
        )
        for ax in axes.flat:
            title = ax.get_title()
            ax.set_title(title, y=1.08)
        plt.subplots_adjust(
            bottom=0.3, top=0.85, left=0.1, right=0.9, hspace=0.08, wspace=0.05
        )
        if OUTPUT_DIR is not None:
            plt.savefig(OUTPUT_DIR + file_name, format="eps", dpi=1000)


def charge_states(compute):
    savefile = "effect_of_convection_data.pickle"
    if compute:
        models = [
            pybamm.lead_acid.Full(
                {"convection": True}, name="With convection"
            ),
            pybamm.lead_acid.Full(name="Without convection"),
        ]
        Crates = [0.5, 1, 5]
        t_eval = np.linspace(0, 1, 100)
        all_variables, t_eval = model_comparison(models, Crates, t_eval)
        with open(savefile, "wb") as f:
            data = (all_variables, t_eval)
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
    else:
        try:
            with open(savefile, "rb") as f:
                (all_variables, t_eval) = pickle.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                "Run script with '--compute' first to generate results"
            )
    plot_voltages(all_variables, t_eval)
    plot_variables(all_variables, t_eval)


def charge_states_bigger_volume_change(compute):
    savefile = "effect_of_convection_bigger_beta_data.pickle"
    if compute:
        models = [
            pybamm.lead_acid.Full(
                {"convection": True}, name="With convection"
            ),
            pybamm.lead_acid.Full(name="Without convection"),
        ]
        Crates = [0.5, 1, 5]
        t_eval = np.linspace(0, 1, 100)
        extra_parameter_values = {"Volume change factor": 10}
        all_variables, t_eval = model_comparison(
            models, Crates, t_eval, extra_parameter_values=extra_parameter_values
        )
        with open(savefile, "wb") as f:
            data = (all_variables, t_eval)
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
    else:
        try:
            with open(savefile, "rb") as f:
                (all_variables, t_eval) = pickle.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                "Run script with '--compute' first to generate results"
            )
    plot_voltages(all_variables, t_eval, bigger_beta=True)
    plot_variables(all_variables, t_eval, bigger_beta=True)


if __name__ == "__main__":
    pybamm.set_logging_level("DEBUG")
    parser = argparse.ArgumentParser()
    parser.add_argument("--compute", action="store_true", help="(Re)-compute results.")
    args = parser.parse_args()
    charge_states(args.compute)
    charge_states_bigger_volume_change(args.compute)
    plt.show()
