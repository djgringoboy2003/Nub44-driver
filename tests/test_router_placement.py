"""Router keep-outs, source-via reservation and the placement optimiser."""
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
sys.path.insert(0, str(ROOT / "automation/placement"))
from nubm44 import paths  # noqa: E402


@pytest.fixture(scope="module")
def keepout_result(tmp_path_factory):
    try:
        python = paths.kicad_python()
    except FileNotFoundError:
        pytest.skip("KiCad Python is required for pcbnew integration tests")
    scratch = tmp_path_factory.mktemp("router_keepout")
    script = r'''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'automation/placement'))
import pcbnew
import pcb_builder as h
job={'origin':[0,0],'rules':{'min_clearance':0.15},'vias':[{'net':'V','x':1.0,'y':2.0}],
     'zones_pre':[{'net':'P','layer':'F.Cu','polygon':[[0,0],[2,0],[2,2],[0,2]]}],'zones_post':[]}
b=pcbnew.BOARD();b.SetCopperLayerCount(4)
area=h.add_router_keepout(b,job,{'layer':'In2.Cu','polygon':[[0,0],[1,0],[1,1],[0,1]]})
flags={'rule':area.GetIsRuleArea(),'tracks':area.GetDoNotAllowTracks(),'vias':area.GetDoNotAllowVias(),
       'fills':area.GetDoNotAllowZoneFills(),'pads':area.GetDoNotAllowPads(),'layer':b.GetLayerName(area.GetLayer())}
h.replace_source_zones(b,job)
zones=[{'rule':z.GetIsRuleArea(),'net':z.GetNetname()} for z in b.Zones()]
occupied={'F':[],'B':[]};h.reserve_source_vias(job,occupied)
print(json.dumps({'flags':flags,'after_finish':zones,'occupied':occupied}))
'''
    completed = subprocess.run([str(python), "-I", "-c", script, str(ROOT), str(scratch)],
                               capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout.splitlines()[-1])


def test_router_keepout_bars_tracks_and_vias_but_not_pours(keepout_result):
    assert keepout_result["flags"] == {"rule": True, "tracks": True, "vias": True, "fills": False,
                                       "pads": False, "layer": "In2.Cu"}


def test_finish_zone_rebuild_removes_router_keepouts(keepout_result):
    assert keepout_result["after_finish"] == [{"rule": False, "net": "P"}]


def test_source_vias_are_reserved_on_both_sides(keepout_result):
    box = [1.0 - 0.45, 2.0 - 0.45, 1.0 + 0.45, 2.0 + 0.45]
    for side in "FB":
        assert keepout_result["occupied"][side] == [pytest.approx(box)]


# ------------------------------------------------------------------ placement optimiser
import place_opt  # noqa: E402


def part(cx, cy, w, h, nets, back=False):
    pads = [{"num": str(i + 1), "net": n, "x": (-w / 4 if i == 0 else w / 4), "y": 0.0, "kind": "B" if back else "F",
             "outline": [], "drill": 0.0} for i, n in enumerate(nets)]
    return {"native_back": back, "pads": pads, "courtyard": [-w / 2, -h / 2, w / 2, h / 2]}


@pytest.fixture
def synthetic(monkeypatch):
    geo = {"A": part(0, 0, 2.0, 1.0, ["/N1", "/N2"]), "B": part(0, 0, 1.0, 1.0, ["/N1", "GND"]),
           "C": part(0, 0, 1.0, 1.0, ["/N2", "/VBAT"])}
    place = {"board": {"outline": {"type": "circle", "radius": 11}}, "placement_radius": 6.0, "courtyard_gap": 0.02,
             "parts": {"A": {"pos": [0, 0, 0], "side": "F"}, "B": {"pos": [4.0, 0, 0], "side": "F"},
                       "C": {"pos": [-4.0, 2.0, 0], "side": "F"}},
             "vias": [{"net": "N1", "x": 2.0, "y": 0.0}],
             "zones_pre": [{"net": "/VBAT", "layer": "F.Cu", "polygon": [[-5, -5], [-3, -5], [-3, -3], [-5, -3]]}],
             "place_opt": {"near": {"C": [-4.0, -4.0]}, "near_weight": 3.0}}
    monkeypatch.setattr(place_opt.floorplan, "load", lambda variant: (place, geo, {}))
    return place


def test_point_polygon_distance():
    sq = [(0, 0), (2, 0), (2, 2), (0, 2)]
    assert place_opt.point_poly_dist(1, 1, sq) == 0.0
    assert place_opt.point_poly_dist(3, 1, sq) == pytest.approx(1.0)
    assert place_opt.point_poly_dist(3, 3, sq) == pytest.approx(math.sqrt(2))


def test_anneal_shortens_nets_and_never_breaks_hard_rules(synthetic):
    model = place_opt.Model("synthetic", ["B", "C"])
    before = model.total()
    after = place_opt.anneal(model, 4000, seed=3)
    assert after < before
    assert after == pytest.approx(model.total())                    # incremental bookkeeping is exact
    for ref in ("B", "C"):
        assert model.feasible(ref, model.state[ref])
        box, _ = model.placed(ref)
        r = 0.3 + 0.15                                              # the source via at (2, 0) blocks both sides
        assert box[2] <= 2.0 - r or box[0] >= 2.0 + r or box[3] <= -r or box[1] >= r
    x, y = model.state["C"][:2]
    assert math.hypot(x + 4.0, y + 4.0) < 2.0                      # pulled toward its "near" target


def test_repair_moves_an_overlapping_start_to_a_feasible_spot(synthetic):
    synthetic["parts"]["B"]["pos"] = [0.2, 0.0, 0]                 # overlaps A
    model = place_opt.Model("synthetic", ["B"])
    assert not model.feasible("B", model.state["B"])
    assert place_opt.repair(model, seed=1) == []
    assert model.feasible("B", model.state["B"])


def test_router_keepout_is_cut_back_around_vias_of_other_routed_nets(tmp_path):
    """A through via of a routed net inside a keep-out is unreachable for the router: cut the area there."""
    try:
        python = paths.kicad_python()
    except FileNotFoundError:
        pytest.skip("KiCad Python is required for pcbnew integration tests")
    script = r'''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'automation/placement'))
import pcbnew
import pcb_builder as h
b=pcbnew.BOARD();b.SetCopperLayerCount(4)
for name in ('S','P','GND'):
    b.Add(pcbnew.NETINFO_ITEM(b,name))
def via(net,x,y):
    v=pcbnew.PCB_VIA(b);v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
    v.SetWidth(pcbnew.FromMM(0.6));v.SetDrill(pcbnew.FromMM(0.3));v.SetNet(b.FindNet(net));b.Add(v)
via('S',0.5,0.5);via('P',2.5,2.5);via('GND',2.5,0.5)
job={'origin':[0,0],'rules':{'min_clearance':0.15},'fanout_nets':['GND']}
area=h.add_router_keepout(b,job,{'layer':'F.Cu','net':'P','polygon':[[0,0],[3,0],[3,3],[0,3]]})
inside=lambda x,y:area.Outline().Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
print(json.dumps({'S':inside(0.5,0.5),'S_edge':inside(0.5,0.5+0.45),'P':inside(2.5,2.5),'GND':inside(2.5,0.5),
                  'far':inside(1.5,1.5)}))
'''
    completed = subprocess.run([str(python), "-I", "-c", script, str(ROOT)], capture_output=True, text=True,
                               timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    got = json.loads(completed.stdout.splitlines()[-1])
    assert got == {"S": False, "S_edge": False, "P": True, "GND": True, "far": True}
