"""Unit tests for the CAD-generation primitives and engineering calculators."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "automation"))

from nubm44 import sexpr  # noqa: E402
from nubm44.calc import boost, copper  # noqa: E402
from nubm44.schematic import xform  # noqa: E402


def test_sexpr_roundtrip_preserves_strings_and_atoms():
    text = '(kicad_sch (version 20250114) (property "Ref" "(" (at 1.27 -2.54 90)) (x "a\\"b"))'
    node = sexpr.loads(text)
    assert node[0] == "kicad_sch"
    prop = sexpr.child(node, "property")
    assert prop[2] == "(" and not isinstance(prop[2], sexpr.Sym)
    assert sexpr.child(node, "x")[1] == 'a"b'
    again = sexpr.loads(sexpr.dumps(node))
    assert again == node


def test_number_formatting():
    assert sexpr.fmt_num(1.0) == "1"
    assert sexpr.fmt_num(-0.0000001) == "0"
    assert sexpr.fmt_num(2.54) == "2.54"
    assert sexpr.fmt_num(0.1 + 0.2) == "0.3"


def test_symbol_transform_rotation_direction():
    # library point 1 unit up (Y-up) appears 1 unit above the origin on screen (Y-down)
    assert xform(0, 1, 10, 10, 0) == (10, 9)
    # rotating 90 deg counter-clockwise on screen moves a point on +X to screen-up
    assert xform(1, 0, 0, 0, 90) == (0, -1)


def test_boost_power_balance():
    laser = boost.LaserModel(v0=3.9, rd=0.17)
    p = boost.BoostParams(
        r_input_path=0.006, l_h=1.0e-6, dcr=0.004, core_loss_w=0.05,
        rds_ls=0.012, rds_hs=0.014, t_rise=3e-9, t_fall=3e-9, c_oss_total=1.2e-9,
        t_deadtime=20e-9, vf_body=0.7, q_gate_total=20e-9, v_drive=5.0, i_q=1e-3,
        f_sw=600e3, r_shunt=0.005, r_laser_fet=0.006, r_output_path=0.003,
        esr_out=0.003, esr_in=0.003, c_out_eff=30e-6, c_in_eff=30e-6)
    op = boost.solve(3.0, 4.0, laser, p)
    assert op.ccm
    assert math.isclose(op.p_in, op.p_laser + sum(op.losses.values()), rel_tol=1e-6)
    assert math.isclose(op.i_out, op.i_in * (1 - op.duty), rel_tol=1e-6)
    assert 0.80 < op.efficiency < 0.99


def test_copper_sheet_resistance_1oz():
    # 1 oz copper is about 0.49-0.50 milliohm per square at 25 C
    assert 0.47 < copper.sheet_resistance_mohm(1.0, 25) < 0.52
