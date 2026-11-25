"""
Ansys HFSS Automation Script: 5.0 GHz Inset-Fed Circular Microstrip Patch Antenna
=================================================================================
Compatible with:
  1. Built-in Ansys Electronics Desktop (AEDT) IronPython 2.7 (`Tools > Run Script...`)
  2. External Python 3 via PyAEDT (`pip install pyaedt`)

Design Overview (5.0 GHz C-Band / Wi-Fi 5 GHz, FR4 Substrate):
  - Center Frequency (f0): 5.0 GHz
  - Free-Space Wavelength (lambda0): ~59.96 mm
  - Substrate: FR4_epoxy (er = 4.4, tan_delta = 0.02, h = 1.6 mm), 40 mm x 40 mm
  - Circular Patch (TM110 Dominant Mode, Balanis Formula):
      * Calculated Patch Radius (a): ~7.97 mm (Diameter ~15.93 mm)
      * Copper/PEC Sheet at Z = h (1.6 mm) with PerfectE boundary
  - Feed Network (50-Ohm Inset Microstrip Line along -X):
      * 50-Ohm Microstrip Width (W_50): 3.06 mm
      * Inset Depth (y0): ~2.79 mm (0.35 * a), Inset Gap: 0.8 mm on each side
      * Vertical 50-Ohm Lumped Port at substrate edge (X = -20 mm) from Z = 0 to Z = h
  - Main Beam Direction: Broadside toward +Z (Theta = 0 deg)
  - Boundary Condition: Open Air Box (lambda0 / 2 padding) with Radiation boundary
    and 3D Far-Field Infinite Sphere Setup.
"""

import math
import time

# ==============================================================================
# 1. USER CONFIGURATION PARAMETERS
# ==============================================================================
PROJECT_NAME = "Circular_Patch_5GHz"
BASE_DESIGN_NAME = "CircularPatch_5GHz"
AEDT_VERSION = None          # Set to e.g. "2024.1" or leave None for latest installed
NON_GRAPHICAL = False        # Set True to run headless in background

FREQ_GHZ = 5.0               # Center operating frequency [GHz]
SWEEP_START_GHZ = 4.0        # Frequency sweep start [GHz]
SWEEP_STOP_GHZ = 6.0         # Frequency sweep stop [GHz]
SWEEP_POINTS = 101           # Number of frequency sweep points
RUN_SIMULATION = True        # Set True to immediately solve setup when script runs

# Substrate Parameters (Standard 1.6 mm FR4_epoxy)
SUB_MATERIAL = '"FR4_epoxy"' # Built-in AEDT FR4 material (er = 4.4, tand = 0.02)
SUB_ER = 4.4                 # Relative permittivity used for analytical sizing
SUB_H_MM = 1.6               # Substrate thickness [mm]
SUB_L_MM = 40.0              # Substrate & ground plane length along X [mm]
SUB_W_MM = 40.0              # Substrate & ground plane width along Y [mm]

# 50-Ohm Microstrip Feedline Parameters (for FR4, h = 1.6 mm)
FEED_W_MM = 3.06             # 50-Ohm microstrip line width [mm]
INSET_GAP_MM = 0.8           # Air gap on each side of the inset feedline [mm]

# Derived Physical Constants & Balanis Circular Patch Dimensions (in mm)
C0_MM_S = 299792458e3                         # Speed of light [mm/s]
LAMBDA_MM = C0_MM_S / (FREQ_GHZ * 1e9)        # ~59.9585 mm at 5.0 GHz
PAD_MM = LAMBDA_MM / 2.0                      # ~29.9792 mm (lambda/2 radiation padding)

# Balanis Eq. (14-69) for circular patch radius a (computed in cm, converted to mm)
_h_cm = SUB_H_MM / 10.0
_F_cm = 8.791e9 / ((FREQ_GHZ * 1e9) * math.sqrt(SUB_ER))
_fringing = 1.0 + (2.0 * _h_cm / (math.pi * SUB_ER * _F_cm)) * (
    math.log((math.pi * _F_cm) / (2.0 * _h_cm)) + 1.7726
)
PATCH_RAD_MM = (_F_cm / math.sqrt(_fringing)) * 10.0   # ~7.966 mm at 5.0 GHz
INSET_DEPTH_MM = 0.35 * PATCH_RAD_MM                   # ~2.788 mm for ~50-Ohm match


# ==============================================================================
# 2. NATIVE AEDT OMODULE HELPER FUNCTIONS (IronPython 2.7 & Python 3 Compatible)
# ==============================================================================
def setup_project_variables(oDesign):
    """Registers design variables inside HFSS for reference and inspection."""
    params = [
        ("f0", "{0}GHz".format(FREQ_GHZ)),
        ("lambda0", "{0:.4f}mm".format(LAMBDA_MM)),
        ("sub_h", "{0:.4f}mm".format(SUB_H_MM)),
        ("sub_L", "{0:.4f}mm".format(SUB_L_MM)),
        ("sub_W", "{0:.4f}mm".format(SUB_W_MM)),
        ("a_patch", "{0:.4f}mm".format(PATCH_RAD_MM)),
        ("W_feed", "{0:.4f}mm".format(FEED_W_MM)),
        ("y0_inset", "{0:.4f}mm".format(INSET_DEPTH_MM)),
        ("g_inset", "{0:.4f}mm".format(INSET_GAP_MM)),
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


def build_circular_patch_geometry_and_port(oDesign, oEditor):
    """Builds the Ground Plane, FR4 Substrate, Inset-Fed Circular Patch, Port, and AirBox."""
    oEditor.SetModelUnits(["NAME:Units Parameter", "Units:=", "mm", "Rescale:=", False])
    oBoundary = oDesign.GetModule("BoundarySetup")

    sub_x_start = -SUB_L_MM / 2.0
    sub_y_start = -SUB_W_MM / 2.0

    # 1. Create Ground Plane Sheet at Z = 0 mm
    oEditor.CreateRectangle(
        [
            "NAME:RectangleParameters",
            "IsCovered:=", True,
            "XStart:=", "{0:.4f}mm".format(sub_x_start),
            "YStart:=", "{0:.4f}mm".format(sub_y_start),
            "ZStart:=", "0mm",
            "Width:=", "{0:.4f}mm".format(SUB_L_MM),
            "Height:=", "{0:.4f}mm".format(SUB_W_MM),
            "WhichAxis:=", "Z"
        ],
        [
            "NAME:Attributes",
            "Name:=", "GroundPlane",
            "Flags:=", "",
            "Color:=", "(200 130 40)",
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

    # 2. Create Dielectric Substrate Box (Z = 0 to SUB_H_MM)
    oEditor.CreateBox(
        [
            "NAME:BoxParameters",
            "XPosition:=", "{0:.4f}mm".format(sub_x_start),
            "YPosition:=", "{0:.4f}mm".format(sub_y_start),
            "ZPosition:=", "0mm",
            "XSize:=", "{0:.4f}mm".format(SUB_L_MM),
            "YSize:=", "{0:.4f}mm".format(SUB_W_MM),
            "ZSize:=", "{0:.4f}mm".format(SUB_H_MM)
        ],
        [
            "NAME:Attributes",
            "Name:=", "Substrate",
            "Flags:=", "",
            "Color:=", "(40 160 80)",
            "Transparency:=", 0.5,
            "PartCoordinateSystem:=", "Global",
            "UDMId:=", "",
            "MaterialValue:=", SUB_MATERIAL,
            "SurfaceMaterialValue:=", '""',
            "SolveInside:=", True,
            "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False,
            "IsLightweight:=", False
        ]
    )

    # Explicitly enforce SolveInside=True on Substrate
    oEditor.AssignMaterial(
        [
            "NAME:Selections",
            "AllowRegionDependentPartSelectionForPMLCreation:=", True,
            "AllowRegionSelectionForPMLCreation:=", True,
            "Selections:=", "Substrate"
        ],
        [
            "NAME:Attributes",
            "MaterialValue:=", SUB_MATERIAL,
            "SolveInside:=", True,
            "ShellElement:=", False,
            "ShellElementThickness:=", "0mm",
            "ReferenceTemperature:=", "20cel",
            "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False,
            "IsLightweight:=", False
        ]
    )

    # 3. Create Circular Patch Sheet at Z = SUB_H_MM
    oEditor.CreateCircle(
        [
            "NAME:CircleParameters",
            "IsCovered:=", True,
            "XCenter:=", "0mm",
            "YCenter:=", "0mm",
            "ZCenter:=", "{0:.4f}mm".format(SUB_H_MM),
            "Radius:=", "{0:.4f}mm".format(PATCH_RAD_MM),
            "WhichAxis:=", "Z",
            "NumSegments:=", "0"
        ],
        [
            "NAME:Attributes",
            "Name:=", "Patch",
            "Flags:=", "",
            "Color:=", "(255 140 0)",
            "Transparency:=", 0.0,
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

    # 4. Create Inset Cutout Rectangle and Subtract from Circular Patch
    cutout_x_start = -PATCH_RAD_MM - 1.0
    cutout_x_len = 1.0 + INSET_DEPTH_MM
    cutout_w = FEED_W_MM + 2.0 * INSET_GAP_MM
    cutout_y_start = -cutout_w / 2.0

    oEditor.CreateRectangle(
        [
            "NAME:RectangleParameters",
            "IsCovered:=", True,
            "XStart:=", "{0:.4f}mm".format(cutout_x_start),
            "YStart:=", "{0:.4f}mm".format(cutout_y_start),
            "ZStart:=", "{0:.4f}mm".format(SUB_H_MM),
            "Width:=", "{0:.4f}mm".format(cutout_x_len),
            "Height:=", "{0:.4f}mm".format(cutout_w),
            "WhichAxis:=", "Z"
        ],
        [
            "NAME:Attributes",
            "Name:=", "Inset_Cutout",
            "Flags:=", "",
            "Color:=", "(200 60 60)",
            "Transparency:=", 0.0,
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

    oEditor.Subtract(
        [
            "NAME:Selections",
            "Blank Parts:=", "Patch",
            "Tool Parts:=", "Inset_Cutout"
        ],
        [
            "NAME:SubtractParameters",
            "KeepOriginals:=", False
        ]
    )

    # 5. Create 50-Ohm Microstrip Feedline and Unite with Patch
    feed_x_start = sub_x_start
    feed_x_len = (SUB_L_MM / 2.0) - PATCH_RAD_MM + INSET_DEPTH_MM + 0.5
    feed_y_start = -FEED_W_MM / 2.0

    oEditor.CreateRectangle(
        [
            "NAME:RectangleParameters",
            "IsCovered:=", True,
            "XStart:=", "{0:.4f}mm".format(feed_x_start),
            "YStart:=", "{0:.4f}mm".format(feed_y_start),
            "ZStart:=", "{0:.4f}mm".format(SUB_H_MM),
            "Width:=", "{0:.4f}mm".format(feed_x_len),
            "Height:=", "{0:.4f}mm".format(FEED_W_MM),
            "WhichAxis:=", "Z"
        ],
        [
            "NAME:Attributes",
            "Name:=", "Feedline",
            "Flags:=", "",
            "Color:=", "(255 140 0)",
            "Transparency:=", 0.0,
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

    oEditor.Unite(
        [
            "NAME:Selections",
            "Selections:=", "Patch,Feedline"
        ],
        [
            "NAME:UniteParameters",
            "KeepOriginals:=", False
        ]
    )

    # 6. Assign PerfectE Boundaries to GroundPlane and Patch
    oBoundary.AssignPerfectE(
        [
            "NAME:PerfE_Ground",
            "Objects:=", ["GroundPlane"],
            "InfGroundPlane:=", False
        ]
    )

    oBoundary.AssignPerfectE(
        [
            "NAME:PerfE_Patch",
            "Objects:=", ["Patch"],
            "InfGroundPlane:=", False
        ]
    )

    # 7. Create Vertical Lumped Port Sheet at Substrate Edge (X = -SUB_L_MM / 2)
    port_sheet = "Port_Sheet_1"
    oEditor.CreateRectangle(
        [
            "NAME:RectangleParameters",
            "IsCovered:=", True,
            "XStart:=", "{0:.4f}mm".format(sub_x_start),
            "YStart:=", "{0:.4f}mm".format(feed_y_start),
            "ZStart:=", "0mm",
            "Width:=", "{0:.4f}mm".format(FEED_W_MM),
            "Height:=", "{0:.4f}mm".format(SUB_H_MM),
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
                        "Start:=", ["{0:.4f}mm".format(sub_x_start), "0mm", "0mm"],
                        "End:=", ["{0:.4f}mm".format(sub_x_start), "0mm", "{0:.4f}mm".format(SUB_H_MM)]
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

    # 8. Create Solid 3D Vacuum AirBox enclosing substrate with lambda/2 padding
    air_x_pos = sub_x_start - PAD_MM
    air_y_pos = sub_y_start - PAD_MM
    air_z_pos = -PAD_MM
    air_x_size = SUB_L_MM + 2.0 * PAD_MM
    air_y_size = SUB_W_MM + 2.0 * PAD_MM
    air_z_size = SUB_H_MM + 2.0 * PAD_MM

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

    # Explicitly enforce SolveInside=True on AirBox
    oEditor.AssignMaterial(
        [
            "NAME:Selections",
            "AllowRegionDependentPartSelectionForPMLCreation:=", True,
            "AllowRegionSelectionForPMLCreation:=", True,
            "Selections:=", "AirBox"
        ],
        [
            "NAME:Attributes",
            "MaterialValue:=", '"vacuum"',
            "SolveInside:=", True,
            "ShellElement:=", False,
            "ShellElementThickness:=", "0mm",
            "ReferenceTemperature:=", "20cel",
            "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False,
            "IsLightweight:=", False
        ]
    )

    # 9. Assign Radiation Boundary to AirBox (with 6-face fallback)
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


def configure_patch_excitation(oDesign):
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
    """Creates the 3D Infinite Sphere, 5.0 GHz adaptive setup, frequency sweep, and plots."""
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

    # 2. Adaptive Solution Setup at 5.0 GHz
    oAnalysis = oDesign.GetModule("AnalysisSetup")
    oAnalysis.InsertSetup(
        "HfssDriven",
        [
            "NAME:Setup_5GHz",
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

    # 3. Frequency Sweep (4.0 GHz to 6.0 GHz)
    oAnalysis.InsertFrequencySweep(
        "Setup_5GHz",
        [
            "NAME:Sweep_4p0_to_6p0GHz",
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

    # 4. Pre-Configured Plots (Return Loss S11, E-Plane XZ, H-Plane YZ, 3D Gain)
    oReport = oDesign.GetModule("ReportSetup")

    # Return Loss S11 (dB)
    oReport.CreateReport(
        "Return_Loss_S11_dB",
        "Modal Solution Data",
        "Rectangular Plot",
        "Setup_5GHz : Sweep_4p0_to_6p0GHz",
        ["Domain:=", "Sweep"],
        ["Freq:=", ["All"]],
        ["X Component:=", "Freq", "Y Component:=", ["dB(S(Port1,Port1))"]]
    )

    # E-Plane Cut (X-Z Plane, Phi = 0 deg, Theta = -180 to 180 deg, Broadside peak at Theta = 0 deg / +Z)
    oReport.CreateReport(
        "Patch_E_Plane_XZ",
        "Far Fields",
        "Radiation Pattern",
        "Setup_5GHz : LastAdaptive",
        ["Context:=", "Infinite_Sphere_3D"],
        [
            "Theta:=", ["All"],
            "Phi:=", ["0deg"],
            "Freq:=", ["{0}GHz".format(FREQ_GHZ)]
        ],
        ["Ang Component:=", "Theta", "Mag Component:=", ["dB(GainTotal)", "dB(DirTotal)"]]
    )

    # H-Plane Cut (Y-Z Plane, Phi = 90 deg, Theta = -180 to 180 deg, Broadside peak at Theta = 0 deg / +Z)
    oReport.CreateReport(
        "Patch_H_Plane_YZ",
        "Far Fields",
        "Radiation Pattern",
        "Setup_5GHz : LastAdaptive",
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
        "3D_Patch_Gain_Pattern",
        "Far Fields",
        "3D Polar Plot",
        "Setup_5GHz : LastAdaptive",
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
            "Created fresh design '{0}': 5.0 GHz Circular Patch (a = {1:.2f} mm, FR4 h = {2} mm)".format(
                unique_design_name, PATCH_RAD_MM, SUB_H_MM
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
    build_circular_patch_geometry_and_port(oDesign, oEditor)
    configure_patch_excitation(oDesign)
    configure_analysis_and_reports(oDesign)
    configure_patch_excitation(oDesign)

    oEditor.FitAll()

    if RUN_SIMULATION:
        oDesign.Analyze("Setup_5GHz")
        configure_patch_excitation(oDesign)


if __name__ == "__main__":
    main()