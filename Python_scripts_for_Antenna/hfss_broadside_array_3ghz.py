"""
Ansys HFSS Automation Script: 3.0 GHz 4-Element Broadside Dipole Antenna Array
==============================================================================
Compatible with:
  1. Built-in Ansys Electronics Desktop (AEDT) IronPython 2.7 (`Tools > Run Script...`)
  2. External Python 3 via PyAEDT (`pip install pyaedt`)

Design Overview (3.0 GHz S-Band):
  - Center Frequency (f0): 3.0 GHz
  - Free-Space Wavelength (lambda0): ~99.93 mm
  - Array Configuration: 4-element uniform linear array (ULA) of Z-directed half-wave
    dipoles spaced along the +X axis.
  - Element Spacing (d): 0.5 * lambda0 (~49.97 mm) for maximum broadside directivity
    without grating lobes.
  - Broadside Progressive Phase Shift (beta):
      * Broadside (Maximum radiation normal to array axis along +/-Y, Phi = +/-90 deg,
        Theta = 90 deg): beta = 0 deg per element (all elements fed in-phase:
        0 deg, 0 deg, 0 deg, 0 deg at 1W each).
  - Dipole Geometry (tuned for 50-73 Ohm resonance at 3.0 GHz):
      * Total Dipole Length (L): 0.475 * lambda0 (~47.47 mm)
      * Dipole Wire Radius (r): 0.8 mm
      * Feed Gap (g): 1.2 mm
  - Boundary Condition: Open Air Box (lambda0 / 2 padding) with Radiation boundary
    and 3D Far-Field Infinite Sphere Setup.
"""

import math
import time

# ==============================================================================
# 1. USER CONFIGURATION PARAMETERS
# ==============================================================================
PROJECT_NAME = "Broadside_Array_3GHz"
BASE_DESIGN_NAME = "Dipole_Broadside_3GHz"
AEDT_VERSION = None          # Set to e.g. "2024.1" or leave None for latest installed
NON_GRAPHICAL = False        # Set True to run headless in background

FREQ_GHZ = 3.0               # Center operating frequency [GHz]
SWEEP_START_GHZ = 2.5        # Frequency sweep start [GHz]
SWEEP_STOP_GHZ = 3.5         # Frequency sweep stop [GHz]
SWEEP_POINTS = 101           # Number of frequency sweep points

NUM_ELEMENTS = 4             # Number of array elements (N)
SPACING_LAMBDA = 0.50        # Inter-element spacing along +X in wavelengths (lambda/2 for broadside)
BETA_DEG = 0.0               # Broadside progressive phase shift (0 deg = all elements in-phase)
RUN_SIMULATION = True        # Set True to immediately solve setup when script runs

# Derived Physical Constants & Dimensions (in mm)
C0_MM_S = 299792458e3                         # Speed of light [mm/s]
LAMBDA_MM = C0_MM_S / (FREQ_GHZ * 1e9)        # ~99.9308 mm at 3.0 GHz
SPACING_MM = SPACING_LAMBDA * LAMBDA_MM       # ~49.9654 mm (lambda/2)
DIPOLE_LEN_MM = 0.475 * LAMBDA_MM             # ~47.4671 mm (velocity factor shortened)
DIPOLE_RAD_MM = 0.8                           # 0.8 mm cylinder radius (scaled for 3 GHz)
FEED_GAP_MM = 1.2                             # 1.2 mm center feed gap
ARM_LEN_MM = (DIPOLE_LEN_MM - FEED_GAP_MM) / 2.0
PAD_MM = LAMBDA_MM / 2.0                      # ~49.9654 mm (lambda/2 radiation padding)


# ==============================================================================
# 2. NATIVE AEDT OMODULE HELPER FUNCTIONS (IronPython 2.7 & Python 3 Compatible)
# ==============================================================================
def setup_project_variables(oDesign):
    """Registers design variables for reference and inspection inside HFSS."""
    params = [
        ("f0", "{0}GHz".format(FREQ_GHZ)),
        ("lambda0", "{0:.4f}mm".format(LAMBDA_MM)),
        ("d_elem", "{0:.4f}mm".format(SPACING_MM)),
        ("L_dipole", "{0:.4f}mm".format(DIPOLE_LEN_MM)),
        ("r_dipole", "{0:.4f}mm".format(DIPOLE_RAD_MM)),
        ("g_feed", "{0:.4f}mm".format(FEED_GAP_MM)),
        ("L_arm", "{0:.4f}mm".format(ARM_LEN_MM)),
        ("beta_deg", "{0:.2f}deg".format(BETA_DEG)),
    ]
    for var_name, var_val in params:
        oDesign.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:LocalVariableTab",
                    ["NAME:PropServers", "LocalVariables"],
                    [
                        "NAME:NewProps",
                        [
                            "NAME:{0}".format(var_name),
                            "PropType:=", "VariableProp",
                            "UserDef:=", True,
                            "Value:=", var_val
                        ]
                    ]
                ]
            ]
        )


def build_broadside_geometry_and_ports(oDesign, oEditor):
    """Builds the 4 dipole elements, lumped ports, and radiation airbox using exact coordinates."""
    oEditor.SetModelUnits(["NAME:Units Parameter", "Units:=", "mm", "Rescale:=", False])
    oBoundary = oDesign.GetModule("BoundarySetup")

    z_top_start = FEED_GAP_MM / 2.0
    z_bot_start = -FEED_GAP_MM / 2.0

    for i in range(NUM_ELEMENTS):
        idx = i + 1
        x_num = i * SPACING_MM
        x_str = "{0:.4f}mm".format(x_num)

        # 1. Upper Dipole Arm (+Z)
        upper_name = "Dipole_{0}_Upper".format(idx)
        oEditor.CreateCylinder(
            [
                "NAME:CylinderParameters",
                "XCenter:=", x_str,
                "YCenter:=", "0mm",
                "ZCenter:=", "{0:.4f}mm".format(z_top_start),
                "Radius:=", "{0:.4f}mm".format(DIPOLE_RAD_MM),
                "Height:=", "{0:.4f}mm".format(ARM_LEN_MM),
                "WhichAxis:=", "Z",
                "NumSides:=", "0"
            ],
            [
                "NAME:Attributes",
                "Name:=", upper_name,
                "Flags:=", "",
                "Color:=", "(255 128 0)",
                "Transparency:=", 0.0,
                "PartCoordinateSystem:=", "Global",
                "UDMId:=", "",
                "MaterialValue:=", '"pec"',
                "SurfaceMaterialValue:=", '""',
                "SolveInside:=", False,
                "IsMaterialEditable:=", True,
                "UseMaterialAppearance:=", False,
                "IsLightweight:=", False
            ]
        )

        # 2. Lower Dipole Arm (-Z)
        lower_name = "Dipole_{0}_Lower".format(idx)
        oEditor.CreateCylinder(
            [
                "NAME:CylinderParameters",
                "XCenter:=", x_str,
                "YCenter:=", "0mm",
                "ZCenter:=", "{0:.4f}mm".format(z_bot_start),
                "Radius:=", "{0:.4f}mm".format(DIPOLE_RAD_MM),
                "Height:=", "{0:.4f}mm".format(-ARM_LEN_MM),
                "WhichAxis:=", "Z",
                "NumSides:=", "0"
            ],
            [
                "NAME:Attributes",
                "Name:=", lower_name,
                "Flags:=", "",
                "Color:=", "(255 128 0)",
                "Transparency:=", 0.0,
                "PartCoordinateSystem:=", "Global",
                "UDMId:=", "",
                "MaterialValue:=", '"pec"',
                "SurfaceMaterialValue:=", '""',
                "SolveInside:=", False,
                "IsMaterialEditable:=", True,
                "UseMaterialAppearance:=", False,
                "IsLightweight:=", False
            ]
        )

        # 3. Lumped Port Sheet in Y-Z plane spanning the feed gap at X = i * SPACING_MM
        port_sheet = "Port_Sheet_{0}".format(idx)
        oEditor.CreateRectangle(
            [
                "NAME:RectangleParameters",
                "IsCovered:=", True,
                "XStart:=", x_str,
                "YStart:=", "{0:.4f}mm".format(-DIPOLE_RAD_MM),
                "ZStart:=", "{0:.4f}mm".format(z_bot_start),
                "Width:=", "{0:.4f}mm".format(2.0 * DIPOLE_RAD_MM),
                "Height:=", "{0:.4f}mm".format(FEED_GAP_MM),
                "WhichAxis:=", "X"
            ],
            [
                "NAME:Attributes",
                "Name:=", port_sheet,
                "Flags:=", "",
                "Color:=", "(0 128 255)",
                "Transparency:=", 0.2,
                "PartCoordinateSystem:=", "Global",
                "UDMId:=", "",
                "MaterialValue:=", '"vacuum"',
                "SurfaceMaterialValue:=", '""',
                "SolveInside:=", True,
                "IsMaterialEditable:=", True,
                "UseMaterialAppearance:=", False,
                "IsLightweight:=", False
            ]
        )

        # 4. Assign Lumped Port (DrivenModal syntax with explicit integration line)
        oBoundary.AssignLumpedPort(
            [
                "NAME:Port{0}".format(idx),
                "Objects:=", [port_sheet],
                "DoDeembed:=", False,
                "RenormalizeAllTerminals:=", True,
                [
                    "NAME:Modes",
                    [
                        "NAME:Mode1",
                        "ModeNum:=", 1,
                        "UseIntLine:=", True,
                        [
                            "NAME:IntLine",
                            "Start:=", [x_str, "0mm", "{0:.4f}mm".format(z_bot_start)],
                            "End:=", [x_str, "0mm", "{0:.4f}mm".format(z_top_start)]
                        ],
                        "AlignmentGroup:=", 0,
                        "CharImp:=", "Zpi",
                        "RenormImp:=", "50ohm"
                    ]
                ],
                "ShowReporterFilter:=", False,
                "ReporterFilter:=", [True],
                "Impedance:=", "50ohm"
            ]
        )

    # 5. Create Solid 3D Vacuum AirBox enclosing the entire array with lambda/2 padding
    air_x_pos = -PAD_MM
    air_y_pos = -PAD_MM
    air_z_pos = -(DIPOLE_LEN_MM / 2.0) - PAD_MM
    air_x_size = (NUM_ELEMENTS - 1) * SPACING_MM + 2.0 * PAD_MM
    air_y_size = 2.0 * PAD_MM
    air_z_size = DIPOLE_LEN_MM + 2.0 * PAD_MM

    oEditor.CreateBox(
        [
            "NAME:BoxParameters",
            "XPosition:=", "{0:.4f}mm".format(air_x_pos),
            "YPosition:=", "{0:.4f}mm".format(air_y_pos),
            "ZPosition:=", "{0:.4f}mm".format(air_z_pos),
            "XSize:=", "{0:.4f}mm".format(air_x_size),
            "YSize:=", "{0:.4f}mm".format(air_y_size),
            "ZSize:=", "{0:.4f}mm".format(air_z_size)
        ],
        [
            "NAME:Attributes",
            "Name:=", "AirBox",
            "Flags:=", "",
            "Color:=", "(143 175 143)",
            "Transparency:=", 0.85,
            "PartCoordinateSystem:=", "Global",
            "UDMId:=", "",
            "MaterialValue:=", '"vacuum"',
            "SurfaceMaterialValue:=", '""',
            "SolveInside:=", True,
            "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False,
            "IsLightweight:=", False
        ]
    )

    # 6. Assign Radiation Boundary to AirBox (with fallback to face IDs if needed)
    try:
        oBoundary.AssignRadiation(
            [
                "NAME:Rad_AirBox",
                "Objects:=", ["AirBox"],
                "IsFssReference:=", False,
                "IsForPML:=", False
            ]
        )
    except Exception:
        face_ids = [int(f) for f in oEditor.GetFaceIDs("AirBox")]
        oBoundary.AssignRadiation(
            [
                "NAME:Rad_AirBox",
                "Faces:=", face_ids,
                "IsFssReference:=", False,
                "IsForPML:=", False
            ]
        )


def configure_broadside_excitations(oDesign):
    """Excites ALL 4 ports in-phase (1W, 0 deg each) for broadside radiation along +/-Y."""
    oSolutions = oDesign.GetModule("Solutions")

    # Try modern AEDT EditSources format first, with fallback for older/newer AEDT versions
    source_args_v1 = [
        [
            "IncludePortPostProcessing:=", False,
            "SpecifySystemPower:=", False
        ]
    ]
    for i in range(NUM_ELEMENTS):
        phase_val = i * BETA_DEG
        source_args_v1.append(
            [
                "Name:=", "Port{0}:1".format(i + 1),
                "Magnitude:=", "1W",
                "Phase:=", "{0:.2f}deg".format(phase_val)
            ]
        )

    try:
        oSolutions.EditSources(source_args_v1)
    except Exception:
        source_args_v2 = [
            [
                "UseIncidentVoltage:=", False,
                "IncludePortPostProcessing:=", False,
                "SpecifySystemPower:=", False
            ]
        ]
        for i in range(NUM_ELEMENTS):
            phase_val = i * BETA_DEG
            source_args_v2.append(
                [
                    "Name:=", "Port{0}".format(i + 1),
                    "Magnitudes:=", ["1W"],
                    "Phases:=", ["{0:.2f}deg".format(phase_val)],
                    "Terminated:=", [False],
                    "Impedances:=", ["50ohm"]
                ]
            )
        oSolutions.EditSources(source_args_v2)


def configure_analysis_and_reports(oDesign):
    """Creates the 3D Infinite Sphere, 3.0 GHz adaptive setup, frequency sweep, and plots."""
    # 1. Far-Field Infinite Sphere Setup (Created right after Radiation Boundary exists)
    oRadField = oDesign.GetModule("RadField")
    oRadField.InsertInfiniteSphereSetup(
        [
            "NAME:Infinite_Sphere_3D",
            "UseCustomRadiationSurface:=", False,
            "CSDefinition:=", "Theta-Phi",
            "Polarization:=", "Linear",
            "ThetaStart:=", "-180deg",
            "ThetaStop:=", "180deg",
            "ThetaStep:=", "2deg",
            "PhiStart:=", "-180deg",
            "PhiStop:=", "180deg",
            "PhiStep:=", "2deg",
            "UseLocalCS:=", False
        ]
    )

    # 2. Adaptive Solution Setup at 3.0 GHz (SaveRadFieldsOnly=False, SaveAnyFields=True)
    oAnalysis = oDesign.GetModule("AnalysisSetup")
    oAnalysis.InsertSetup(
        "HfssDriven",
        [
            "NAME:Setup_3GHz",
            "AdaptMultipleFreqs:=", False,
            "Frequency:=", "{0}GHz".format(FREQ_GHZ),
            "MaxDeltaS:=", 0.02,
            "PortsOnly:=", False,
            "UseMatrixConv:=", False,
            "MaximumPasses:=", 15,
            "MinimumPasses:=", 2,
            "MinimumConvergedPasses:=", 2,
            "PercentRefinement:=", 30,
            "IsEnabled:=", True,
            ["NAME:MeshLink", "ImportMesh:=", False],
            "BasisOrder:=", 1,
            "DoLambdaRefine:=", True,
            "DoMaterialLambda:=", True,
            "SetLambdaTarget:=", False,
            "Target:=", 0.3333,
            "UseMaxTetIncrease:=", False,
            "PortAccuracy:=", 2,
            "UseABCOnPort:=", False,
            "SetPortMinMaxTri:=", False,
            "UseDomains:=", False,
            "UseIterativeSolver:=", False,
            "SaveRadFieldsOnly:=", False,
            "SaveAnyFields:=", True,
            "IESolverType:=", "Auto",
            "LambdaTargetForIESolver:=", 0.15,
            "UseDefaultLambdaTgtForIESolver:=", True
        ]
    )

    # 3. Frequency Sweep (2.5 GHz to 3.5 GHz)
    oAnalysis.InsertFrequencySweep(
        "Setup_3GHz",
        [
            "NAME:Sweep_2p5_to_3p5GHz",
            "IsEnabled:=", True,
            "RangeType:=", "LinearCount",
            "RangeStart:=", "{0}GHz".format(SWEEP_START_GHZ),
            "RangeEnd:=", "{0}GHz".format(SWEEP_STOP_GHZ),
            "RangeCount:=", SWEEP_POINTS,
            "Type:=", "Interpolating",
            "SaveFields:=", False,
            "SaveRadFields:=", False,
            "InterpTolerance:=", 0.5,
            "InterpMaxSolns:=", 250,
            "InterpMinSolns:=", 0,
            "InterpMinSubranges:=", 1
        ]
    )

    # 4. Pre-Configured Plots (S-Parameters, Active S-Parameters, 2D & 3D Far-Field Gain)
    oReport = oDesign.GetModule("ReportSetup")

    # Standard Return Loss S11, S22, S33, S44
    s_traces = ["dB(S(Port{0},Port{0}))".format(i + 1) for i in range(NUM_ELEMENTS)]
    oReport.CreateReport(
        "Reflection_S_Parameters_dB",
        "Modal Solution Data",
        "Rectangular Plot",
        "Setup_3GHz : Sweep_2p5_to_3p5GHz",
        ["Domain:=", "Sweep"],
        ["Freq:=", ["All"]],
        ["X Component:=", "Freq", "Y Component:=", s_traces]
    )

    # Active S-Parameters (Accounts for mutual coupling when all 4 ports are excited in-phase)
    active_s_traces = ["dB(ActiveS(Port{0}:1))".format(i + 1) for i in range(NUM_ELEMENTS)]
    oReport.CreateReport(
        "Active_S_Parameters_dB",
        "Modal Solution Data",
        "Rectangular Plot",
        "Setup_3GHz : Sweep_2p5_to_3p5GHz",
        ["Domain:=", "Sweep"],
        ["Freq:=", ["All"]],
        ["X Component:=", "Freq", "Y Component:=", active_s_traces]
    )

    # Azimuth H-Plane Pattern Cut (X-Y Plane, Theta = 90 deg, Phi = -180 to 180 deg)
    # Since array is along X-axis with beta = 0 deg, Broadside maxima occur at Phi = +90 deg and -90 deg (+/-Y)
    oReport.CreateReport(
        "Broadside_Azimuth_Pattern_XY",
        "Far Fields",
        "Radiation Pattern",
        "Setup_3GHz : LastAdaptive",
        ["Context:=", "Infinite_Sphere_3D"],
        [
            "Phi:=", ["All"],
            "Theta:=", ["90deg"],
            "Freq:=", ["{0}GHz".format(FREQ_GHZ)]
        ],
        ["Ang Component:=", "Phi", "Mag Component:=", ["dB(GainTotal)", "dB(DirTotal)"]]
    )

    # Broadside E-Plane Elevation Pattern Cut (Y-Z Plane, Phi = 90 deg, Theta = -180 to 180 deg)
    oReport.CreateReport(
        "Broadside_Elevation_Pattern_YZ",
        "Far Fields",
        "Radiation Pattern",
        "Setup_3GHz : LastAdaptive",
        ["Context:=", "Infinite_Sphere_3D"],
        [
            "Theta:=", ["All"],
            "Phi:=", ["90deg"],
            "Freq:=", ["{0}GHz".format(FREQ_GHZ)]
        ],
        ["Ang Component:=", "Theta", "Mag Component:=", ["dB(GainTotal)", "dB(DirTotal)"]]
    )

    # 3D Polar Far-Field Gain Plot
    oReport.CreateReport(
        "3D_Broadside_Gain_Pattern",
        "Far Fields",
        "3D Polar Plot",
        "Setup_3GHz : LastAdaptive",
        ["Context:=", "Infinite_Sphere_3D"],
        [
            "Phi:=", ["All"],
            "Theta:=", ["All"],
            "Freq:=", ["{0}GHz".format(FREQ_GHZ)]
        ],
        [
            "Phi Component:=", "Phi",
            "Theta Component:=", "Theta",
            "Mag Component:=", ["dB(GainTotal)"]
        ]
    )


# ==============================================================================
# 3. ENTRY POINT (Always Creates a Fresh Timestamped Design to Prevent Collisions)
# ==============================================================================
def main():
    # Generate a unique design name every run so an open/active design never blocks deletion
    unique_design_name = "{0}_{1}".format(BASE_DESIGN_NAME, int(time.time()) % 10000)

    if "oDesktop" in globals():
        # Running directly inside Ansys Electronics Desktop (Tools > Run Script)
        desktop = globals()["oDesktop"]
        desktop.RestoreWindow()
        oProject = desktop.GetActiveProject()
        if oProject is None:
            oProject = desktop.NewProject()

        oProject.InsertDesign("HFSS", unique_design_name, "DrivenModal", "")
        oDesign = oProject.SetActiveDesign(unique_design_name)
        desktop.AddMessage(
            "", "", 0,
            "Created fresh design '{0}': 4-element 3.0 GHz Broadside Array (d = 0.5*lambda, beta = 0 deg)".format(
                unique_design_name
            )
        )
    else:
        # Running externally from standard Python using PyAEDT
        try:
            from ansys.aedt.core import Hfss
        except ImportError:
            from pyaedt import Hfss

        hfss_app = Hfss(
            project=PROJECT_NAME,
            design=unique_design_name,
            solution_type="DrivenModal",
            version=AEDT_VERSION,
            non_graphical=NON_GRAPHICAL,
            new_desktop=False
        )
        oDesign = hfss_app.odesign
        oProject = hfss_app.oproject

    oEditor = oDesign.SetActiveEditor("3D Modeler")

    setup_project_variables(oDesign)
    build_broadside_geometry_and_ports(oDesign, oEditor)
    configure_broadside_excitations(oDesign)
    configure_analysis_and_reports(oDesign)
    # Re-apply excitations after setup creation so all 4 ports stay locked at 1W, 0 deg
    configure_broadside_excitations(oDesign)

    oEditor.FitAll()

    if RUN_SIMULATION:
        oDesign.Analyze("Setup_3GHz")
        # Ensure post-processing sources remain active after solve finishes
        configure_broadside_excitations(oDesign)


if __name__ == "__main__":
    main()