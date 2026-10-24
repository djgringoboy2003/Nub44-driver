"""Regressions for placement transforms and real KiCad copper geometry."""
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
from floorplan import geometry_cache_is_current, xform  # noqa: E402


@pytest.fixture(scope="module")
def kicad_geometry():
    try:
        python = paths.kicad_python()
    except FileNotFoundError:
        pytest.skip("KiCad Python is required for placement integration tests")
    script = r'''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'automation/placement'))
import pcbnew
import pcb_builder as builder

def pad(fp,number,x,y,layer,net=None):
    p=pcbnew.PAD(fp)
    p.SetNumber(number)
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    p.SetShape(pcbnew.PAD_SHAPE_RECT)
    p.SetSize(pcbnew.VECTOR2I(builder.MM(0.4),builder.MM(0.4)))
    p.SetPosition(pcbnew.VECTOR2I(builder.MM(x),builder.MM(y)))
    layers=pcbnew.LSET();layers.AddLayer(layer);p.SetLayerSet(layers)
    if net is not None:p.SetNet(net)
    fp.Add(p)
    return p

results={'placements':[]}
for native_back in (False,True):
    board=pcbnew.BOARD()
    fp=pcbnew.FOOTPRINT(board)
    fp.SetLayer(pcbnew.B_Cu if native_back else pcbnew.F_Cu)
    board.Add(fp)
    p=pad(fp,'1',0.8,-0.3,pcbnew.B_Cu if native_back else pcbnew.F_Cu)
    item={}
    # Reuse a footprint in the same changing order as an automatic placer.
    for side in ('B','F','B'):
        for angle in (0,90,180,270,0,180,90,270):
            builder.place_fp(board,{'origin':[10,20]},fp,item,1,2,angle,side)
            results['placements'].append({'native_back':native_back,'side':side,'angle':angle,
                'x':pcbnew.ToMM(p.GetPosition().x),'y':pcbnew.ToMM(p.GetPosition().y),
                'actual_side':'B' if fp.GetLayer()==pcbnew.B_Cu else 'F'})

board=pcbnew.BOARD();fp=pcbnew.FOOTPRINT(board);board.Add(fp)
net=builder.get_net(board,'GND')
source=pad(fp,'1',0,0,pcbnew.F_Cu,net)
paste=pad(fp,'',0,0,pcbnew.F_Paste)
# Opposite-side copper may obstruct a through via, but not the source's top trace.
opposite=pad(fp,'2',0,0,pcbnew.B_Cu,builder.get_net(board,'OTHER'))
results['copper_flags']=[builder.copper_pad(p) for p in (source,paste,opposite)]
report=[]
builder.fanout(board,{'origin':[0,0],'placement_radius':5},'GND',report,width=0.15)
results['fanout']=report
print(json.dumps(results))
'''
    result = subprocess.run([str(python), "-I", "-c", script, str(ROOT)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_repeated_placements_match_source_transform(kicad_geometry):
    for p in kicad_geometry["placements"]:
        mirror = (p["side"] == "B") != p["native_back"]
        expected = xform(0.8, -0.3, 11, 22, p["angle"], mirror)
        assert p["actual_side"] == p["side"]
        assert math.isclose(p["x"], expected[0], abs_tol=2e-6), p
        assert math.isclose(p["y"], expected[1], abs_tol=2e-6), p


def test_fanout_ignores_paste_and_opposite_side_trace_obstacles(kicad_geometry):
    assert kicad_geometry["copper_flags"] == [True, False, True]
    assert kicad_geometry["fanout"] == [{"fanout": "GND", "connected": 1, "failed": 0}]


def test_geometry_cache_rejects_changed_or_missing_sources(tmp_path):
    source = tmp_path / "fixture.kicad_mod"
    source.write_text("initial", encoding="utf-8")
    stat = source.stat()
    geo = {"__meta__": {"format_version": 2, "sources": [{
        "path": str(source), "mtime_ns": stat.st_mtime_ns, "size": stat.st_size}]}}
    assert geometry_cache_is_current(geo)
    source.write_text("changed geometry", encoding="utf-8")
    assert not geometry_cache_is_current(geo)
    source.unlink()
    assert not geometry_cache_is_current(geo)
    assert not geometry_cache_is_current({})
