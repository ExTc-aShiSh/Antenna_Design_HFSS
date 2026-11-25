"""
Ansys HFSS Automation Script: 2.4 GHz 5-Element Yagi-Uda Antenna
==============================================================================
Compatible with:
  1. Built-in Ansys Electronics Desktop (AEDT) IronPython 2.7 (`Tools > Run Script...`)
  2. External Python 3 via PyAEDT (`pip install pyaedt`)

Design Overview (2.4 GHz ISM Band, 5-Element Yagi-Uda along +X Axis):
  - Center Frequency (f0): 2.4 GHz
  - Free-Space Wavelength (lambda0): ~124.91 mm
  - Elements (all Z-polarized PEC cylinders spaced along the X-axis):
      1. Reflector (Continuous cylinder at X = -0.20 * lambda0 = -24.98 mm):
         Length L_ref = 0.495 * lambda0 (~61.83 mm)
      2. Driven Dipole (Split cylinder with lumped port at X = 0.0 mm):
         Total Length L_drv = 0.465 * lambda0 (~58.08 mm), Feed Gap g = 1.5 mm
      3. Director 1 (Continuous cylinder at X = +0.20 * lambda0 = +24.98 mm):
         Length L_dir1 = 0.435 * lambda0 (~54.34 mm)
      4. Director 2 (Continuous cylinder at X = +0.45 * lambda0 = +56.21 mm):
         Length L_dir2 = 0.425 * lambda0 (~53.09 mm)
      5. Director 3 (Continuous cylinder at X = +0.70 * lambda0 = +87.44 mm):
         Length L_dir3 = 0.415 * lambda0 (~51.84 mm)
  - Rod Radius (r): 1.0 mm
  - Main Beam Direction: Endfire toward +X (Phi = 0 deg, Theta = 90 deg)
  - Boundary Condition: Open Air Box (lambda0 / 2 padding) with Radiation boundary
    and 3D Far-Field Infinite Sphere Setup.
"""

import math
import time

# ==============================================================================
# 1. USER CONFIGURATION PARAMETERS
# ==============================================================================
PROJECT_NAME = "Yagi_Uda_2p4GHz"
BASE_DESIGN_NAME = "YagiUda_5Elem_2p4GHz"
AEDT_VERSION = None          # Set to e.g. "2024.1" or leave None for latest installed
NON_GRAPHICAL = False        # Set True to run headless in background

FREQ_GHZ = 2.4               # Center operating frequency [GHz]
SWEEP_START_GHZ = 2.0        # Frequency sweep start [GHz]
SWEEP_STOP_GHZ = 2.8         # Frequency sweep stop [GHz]
SWEEP_POINTS = 81            # Number of frequency sweep points
RUN_SIMULATION = True        # Set True to immediately solve setup when script runs

# Derived Physical Constants & Dimensions (in mm)
C0_MM_S = 299792458e3                         # Speed of light [mm/s]
LAMBDA_MM = C0_MM_S / (FREQ_GHZ * 1e9)        # ~124.9135 mm at 2.4 GHz
ROD_RAD_MM = 1.0                              # 1.0 mm element wire radius
FEED_GAP_MM = 1.5                             # 1.5 mm center feed gap on driven element
PAD_MM = LAMBDA_MM / 2.0                      # ~62.4568 mm (lambda/2 radiation padding)

# Element Lengths (in mm)
L_REF_MM = 0.495 * LAMBDA_MM                  # Reflector length (~61.83 mm)
L_DRV_MM = 0.465 * LAMBDA_MM                  # Driven dipole total length (~58.08 mm)
L_DRV_ARM_MM = (L_DRV_MM - FEED_GAP_MM) / 2.0 # Single arm length of driven dipole

# Director lengths and cumulative X positions (in wavelengths -> mm)
DIRECTOR_SPECS = [
    ("Director_1", 0.20 * LAMBDA_MM, 0.435 * LAMBDA_MM),
    ("Director_2", 0.45 * LAMBDA_MM, 0.425 * LAMBDA_MM),
    ("Director_3", 0.70 * LAMBDA_MM, 0.415 * LAMBDA_MM),
]
X_REF_MM = -0.20 * LAMBDA_MM                  # Reflector position along -X (~-24.98 mm)
X_DRV_MM = 0.0                                # Driven element at origin (X = 0 mm)


# ==============================================================================
# 2. NATIVE AEDT OMODULE HELPER FUNCTIONS (IronPython 2.7 & Python 3 Compatible)
# ==============================================================================
def setup_project_variables(oDesign):
    """Registers design variables inside HFSS for easy inspection."""
    params = [
        ("f0", "{0}GHz".format(FREQ_GHZ)),
        ("lambda0", "{0:.4f}mm".format(LAMBDA_MM)),
        ("r_rod", "{0:.4f}mm".format(ROD_RAD_MM)),
        ("g_feed", "{0:.4f}mm".format(FEED_GAP_MM)),
        ("L_ref", "{0:.4f}mm".format(L_REF_MM)),
        ("L_drv", "{0:.4f}mm".format(L_DRV_MM)),
        ("x_ref", "{0:.4f}mm".format(X_REF_MM)),
    ]
    for idx, (d_name, d_x, d_len) in enumerate(DIRECTOR_SPECS):
        params.append(("L_dir{0}".format(idx + 1), "{0:.4f}mm".format(d_len)))
        params.append(("x_dir{0}".format(idx + 1), "{0:.4f}mm".format(d_x)))

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


def build_yagi_geometry_and_port(oDesign, oEditor):
    """Builds the Reflector, Driven Dipole + Lumped Port, 3 Directors, and Radiation AirBox."""
    oEditor.SetModelUnits(["NAME:Units Parameter", "Units:=", "mm", "Rescale:=", False])
    oBoundary = oDesign.GetModule("BoundarySetup")

    # 1. Create Reflector (Continuous PEC Cylinder at X = X_REF_MM)
    oEditor.CreateCylinder(
        [
            "NAME:CylinderParameters",
            "XCenter:=", "{0:.4f}mm".format(X_REF_MM),
            "YCenter:=", "0mm",
            "ZCenter:=", "{0:.4f}mm".format(-L_REF_MM / 2.0),
            "Radius:=", "{0:.4f}mm".format(ROD_RAD_MM),
            "Height:=", "{0:.4f}mm".format(L_REF_MM),
            "WhichAxis:=", "Z",
            "NumSides:=", "0"
        ],
        [
            "NAME:Attributes",
            "Name:=", "Reflector",
            "Flags:=", "",
            "Color:=", "(220 60 60)",
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

    # 2. Create Driven Element (Upper & Lower PEC Dipole Arms at X = 0 mm)
    z_top_start = FEED_GAP_MM / 2.0
    z_bot_start = -FEED_GAP_MM / 2.0
    x_drv_str = "{0:.4f}mm".format(X_DRV_MM)

    oEditor.CreateCylinder(
        [
            "NAME:CylinderParameters",
            "XCenter:=", x_drv_str,
            "YCenter:=", "0mm",
            "ZCenter:=", "{0:.4f}mm".format(z_top_start),
            "Radius:=", "{0:.4f}mm".format(ROD_RAD_MM),
            "Height:=", "{0:.4f}mm".format(L_DRV_ARM_MM),
            "WhichAxis:=", "Z",
            "NumSides:=", "0"
        ],
        [
            "NAME:Attributes",
            "Name:=", "Driven_Upper",
            "Flags:=", "",
            "Color:=", "(255 140 0)",
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

    oEditor.CreateCylinder(
        [
            "NAME:CylinderParameters",
            "XCenter:=", x_drv_str,
            "YCenter:=", "0mm",
            "ZCenter:=", "{0:.4f}mm".format(z_bot_start),
            "Radius:=", "{0:.4f}mm".format(ROD_RAD_MM),
            "Height:=", "{0:.4f}mm".format(-L_DRV_ARM_MM),
            "WhichAxis:=", "Z",
            "NumSides:=", "0"
        ],
        [
            "NAME:Attributes",
            "Name:=", "Driven_Lower",
            "Flags:=", "",
            "Color:=", "(255 140 0)",
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

    # 3. Create Lumped Port Sheet at Driven Element Feed Gap (X = 0 mm)
    port_sheet = "Port_Sheet_1"
    oEditor.CreateRectangle(
        [
            "NAME:RectangleParameters",
            "IsCovered:=", True,
            "XStart:=", x_drv_str,
            "YStart:=", "{0:.4f}mm".format(-ROD_RAD_MM),
            "ZStart:=", "{0:.4f}mm".format(z_bot_start),
            "Width:=", "{0:.4f}mm".format(2.0 * ROD_RAD_MM),
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

    oBoundary.AssignLumpedPort(
        [
            "NAME:Port1",
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
                        "Start:=", [x_drv_str, "0mm", "{0:.4f}mm".format(z_bot_start)],
                        "End:=", [x_drv_str, "0mm", "{0:.4f}mm".format(z_top_start)]
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

    # 4. Create Parasitic Directors (Continuous PEC Cylinders along +X)
    for d_name, d_x_mm, d_len_mm in DIRECTOR_SPECS:
        oEditor.CreateCylinder(
            [
                "NAME:CylinderParameters",
                "XCenter:=", "{0:.4f}mm".format(d_x_mm),
                "YCenter:=", "0mm",
                "ZCenter:=", "{0:.4f}mm".format(-d_len_mm / 2.0),
                "Radius:=", "{0:.4f}mm".format(ROD_RAD_MM),
                "Height:=", "{0:.4f}mm".format(d_len_mm),
                "WhichAxis:=", "Z",
                "NumSides:=", "0"
            ],
            [
                "NAME:Attributes",
                "Name:=", d_name,
                "Flags:=", "",
                "Color:=", "(40 180 99)",
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

    # 5. Create Solid 3D Vacuum AirBox enclosing the entire Yagi-Uda with lambda/2 padding
    max_x_mm = DIRECTOR_SPECS[-1][1]
    air_x_pos = X_REF_MM - PAD_MM
    air_y_pos = -PAD_MM
    air_z_pos = -(L_REF_MM / 2.0) - PAD_MM
    air_x_size = (max_x_mm - X_REF_MM) + 2.0 * PAD_MM
    air_y_size = 2.0 * PAD_MM
    air_z_size = L_REF_MM + 2.0 * PAD_MM

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


def configure_yagi_excitation(oDesign):
    """Excites Port1 at 1W, 0 deg."""
    oSolutions = oDesign.GetModule("Solutions")
    try:
        oSolutions.EditSources(
            [
                [
                    "IncludePortPostProcessing:=", False,
                    "SpecifySystemPower:=", False
                ],
                [
                    "Name:=", "Port1:1",
                    "Magnitude:=", "1W",
                    "Phase:=", "0deg"
                ]
            ]
        )
    except Exception:
        oSolutions.EditSources(
            [
                [
                    "UseIncidentVoltage:=", False,
                    "IncludePortPostProcessing:=", False,
                    "SpecifySystemPower:=", False
                ],
                [
                    "Name:=", "Port1",
                    "Magnitudes:=", ["1W"],
                    "Phases:=", ["0deg"],
                    "Terminated:=", [False],
                    "Impedances:=", ["50ohm"]
                ]
            ]
        )


def configure_analysis_and_reports(oDesign):
    """Creates the 3D Infinite Sphere, 2.4 GHz adaptive setup, frequency sweep, and plots."""
    # 1. Far-Field Infinite Sphere Setup
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

    # 2. Adaptive Solution Setup at 2.4 GHz
    oAnalysis = oDesign.GetModule("AnalysisSetup")
    oAnalysis.InsertSetup(
        "HfssDriven",
        [
            "NAME:Setup_2p4GHz",
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

    # 3. Frequency Sweep (2.0 GHz to 2.8 GHz)
    oAnalysis.InsertFrequencySweep(
        "Setup_2p4GHz",
        [
            "NAME:Sweep_2p0_to_2p8GHz",
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

    # 4. Pre-Configured Plots (Return Loss S11, H-Plane Azimuth, E-Plane Elevation, 3D Gain)
    oReport = oDesign.GetModule("ReportSetup")

    # Return Loss S11 (dB)
    oReport.CreateReport(
        "Return_Loss_S11_dB",
        "Modal Solution Data",
        "Rectangular Plot",
        "Setup_2p4GHz : Sweep_2p0_to_2p8GHz",
        ["Domain:=", "Sweep"],
        ["Freq:=", ["All"]],
        ["X Component:=", "Freq", "Y Component:=", ["dB(S(Port1,Port1))"]]
    )

    # Azimuth H-Plane Cut (X-Y Plane, Theta = 90 deg, Phi = -180 to 180 deg, Yagi beam toward Phi = 0 deg / +X)
    oReport.CreateReport(
        "Yagi_H_Plane_Azimuth_XY",
        "Far Fields",
        "Radiation Pattern",
        "Setup_2p4GHz : LastAdaptive",
        ["Context:=", "Infinite_Sphere_3D"],
        [
            "Phi:=", ["All"],
            "Theta:=", ["90deg"],
            "Freq:=", ["{0}GHz".format(FREQ_GHZ)]
        ],
        ["Ang Component:=", "Phi", "Mag Component:=", ["dB(GainTotal)", "dB(DirTotal)"]]
    )

    # Elevation E-Plane Cut (X-Z Plane, Phi = 0 deg, Theta = -180 to 180 deg, Yagi beam toward Theta = 90 deg / +X)
    oReport.CreateReport(
        "Yagi_E_Plane_Elevation_XZ",
        "Far Fields",
        "Radiation Pattern",
        "Setup_2p4GHz : LastAdaptive",
        ["Context:=", "Infinite_Sphere_3D"],
        [
            "Theta:=", ["All"],
            "Phi:=", ["0deg"],
            "Freq:=", ["{0}GHz".format(FREQ_GHZ)]
        ],
        ["Ang Component:=", "Theta", "Mag Component:=", ["dB(GainTotal)", "dB(DirTotal)"]]
    )

    # 3D Polar Far-Field Gain Plot
    oReport.CreateReport(
        "3D_Yagi_Gain_Pattern",
        "Far Fields",
        "3D Polar Plot",
        "Setup_2p4GHz : LastAdaptive",
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
            "Created fresh design '{0}': 5-Element 2.4 GHz Yagi-Uda Antenna (Main beam toward +X)".format(
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
    build_yagi_geometry_and_port(oDesign, oEditor)
    configure_yagi_excitation(oDesign)
    configure_analysis_and_reports(oDesign)
    configure_yagi_excitation(oDesign)

    oEditor.FitAll()

    if RUN_SIMULATION:
        oDesign.Analyze("Setup_2p4GHz")
        configure_yagi_excitation(oDesign)


if __name__ == "__main__":
    main()