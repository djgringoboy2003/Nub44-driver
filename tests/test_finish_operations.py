"""Real pcbnew fixtures for repeatable finish operations; no product boards generated."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import paths  # noqa: E402


@pytest.fixture(scope="module")
def finish_geometry(tmp_path_factory):
    try:
        python = paths.kicad_python()
    except FileNotFoundError:
        pytest.skip("KiCad Python is required for finish integration tests")
    scratch = tmp_path_factory.mktemp("finish_geometry")
    script = r'''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'automation/placement'))
import pcbnew
import pcb_builder as h
result={}
job={'origin':[0,0]}
def board():
    b=pcbnew.BOARD();b.SetCopperLayerCount(4);return b
def count(b):return len(list(b.GetTracks()))

b=board()
source={'net':'A','layer':'F.Cu','width':.2,'pts':[[0,0],[1,0],[1,1]]}
for _ in range(3):h.add_track(b,job,source)
counts=[count(b)]
h.add_track(b,job,{**source,'pts':list(reversed(source['pts']))});counts.append(count(b))
for change in ({'layer':'B.Cu'},{'width':.3},{'net':'B'},
               {'pts':[[0,.1],[1,.1],[1,1.1]]}):
    h.add_track(b,job,{**source,**change});counts.append(count(b))
arc=pcbnew.PCB_ARC(b);arc.SetStart(h.P(job,0,0));arc.SetMid(h.P(job,.5,-.3))
arc.SetEnd(h.P(job,1,0));arc.SetWidth(h.MM(.2));arc.SetLayer(pcbnew.F_Cu)
arc.SetNet(h.get_net(b,'A'));b.Add(arc)
h.add_track(b,job,source);counts.append(count(b));result['track_counts']=counts
b=board();arc=pcbnew.PCB_ARC(b);arc.SetStart(h.P(job,0,0));arc.SetMid(h.P(job,.5,-.3))
arc.SetEnd(h.P(job,1,0));arc.SetWidth(h.MM(.2));arc.SetLayer(pcbnew.F_Cu)
arc.SetNet(h.get_net(b,'A'));b.Add(arc)
h.add_track(b,job,{**source,'pts':[[0,0],[1,0]]});result['arc_and_chord_count']=count(b)

b=board();net=h.get_net(b,'V')
blind=pcbnew.PCB_VIA(b);blind.SetPosition(h.P(job,1,2));blind.SetViaType(pcbnew.VIATYPE_BLIND)
blind.SetLayerPair(pcbnew.F_Cu,pcbnew.In1_Cu);blind.SetWidth(h.MM(.6));blind.SetDrill(h.MM(.3))
blind.SetNet(net);b.Add(blind)
v={'net':'V','x':1,'y':2,'size':.6,'drill':.3}
for _ in range(3):h.add_via(b,job,v)
counts=[count(b)]
for change in ({'size':.8},{'drill':.25},{'net':'OTHER'},{'x':2}):
    h.add_via(b,job,{**v,**change});counts.append(count(b))
result['via_counts']=counts
result['via_spans']=[(x.GetViaType(),b.GetLayerName(x.TopLayer()),b.GetLayerName(x.BottomLayer()))
                     for x in b.GetTracks() if isinstance(x,pcbnew.PCB_VIA)]

b=board()
for width,y,net in ((.1124,0,'WIDTH_A'),(.15,.29,'WIDTH_B'),(.3,2,'WIDTH_A')):
    h.add_track(b,job,{'net':net,'layer':'F.Cu','width':width,'pts':[[0,y],[1,y]]})
h.add_via(b,job,{'net':'WIDTH_A','x':3,'y':3,'size':.12,'drill':.08})
def gap():
    tracks={t.GetNetname():t for t in b.GetTracks() if type(t) is pcbnew.PCB_TRACK and t.GetStart().y<h.MM(1)}
    a,c=tracks['WIDTH_A'],tracks['WIDTH_B']
    return pcbnew.ToMM(abs(a.GetStart().y-c.GetStart().y)-(a.GetWidth()+c.GetWidth())/2)
before=gap();widened=h.normalize_track_widths(b,.15);after=gap()
result['widths']={'widened':widened,'repeat':h.normalize_track_widths(b,.15),
    'tracks':sorted(round(pcbnew.ToMM(t.GetWidth()),4) for t in b.GetTracks() if type(t) is pcbnew.PCB_TRACK),
    'via':round(pcbnew.ToMM(next(t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA)).GetWidth(pcbnew.F_Cu)),4),
    'gap_before':before,'gap_after':after}

b=board()
zjob={'origin':[0,0],'zones_pre':[{'net':'Z','layer':'F.Cu','polygon':[[0,0],[1,0],[1,1],[0,1]]}],
      'zones_post':[{'net':'Z','layer':'F.Cu','polygon':[[3,3],[4,3],[4,4],[3,4]]}]}
h.replace_source_zones(b,zjob)
f=Path(sys.argv[2])/'fixture.kicad_pcb'
pcbnew.SaveBoard(str(f),b)
# Load a valid project file; a zero-byte native save output can open a modal dialog.
f.with_suffix('.kicad_pro').write_text('{}',encoding='utf-8')
b=pcbnew.LoadBoard(str(f));counts=[]
for _ in range(3):h.replace_source_zones(b,zjob);counts.append(len(list(b.Zones())))
zjob['zones_pre'][0]['polygon']=[[5,5],[6,5],[6,6],[5,6]];zjob['zones_post']=[]
h.replace_source_zones(b,zjob)
zone=list(b.Zones())[0];bounds=zone.Outline().BBox()
result['zones']={'counts':counts,'updated_count':len(list(b.Zones())),
                'updated_bounds':[pcbnew.ToMM(bounds.GetLeft()),pcbnew.ToMM(bounds.GetRight())]}

b=board();bad={'net':'REMOVE','layer':'F.Cu','width':.2,'pts':[[.1,0],[1,0]]}
h.add_track(b,job,bad);h.add_track(b,job,{**bad,'layer':'B.Cu'})
h.add_track(b,job,{**bad,'net':'KEEP'})
h.add_via(b,job,{'net':'REMOVE','x':1,'y':0});h.add_via(b,job,{'net':'KEEP','x':1,'y':0})
rjob={'origin':[0,0],'remove_vias_post':[{'net':'REMOVE','x':1,'y':0}],
      'remove_tracks_post':[{'net':'REMOVE','layer':'F.Cu','pts':[[1,0],[.1,0]]}]}
first=h.remove_source_copper(b,rjob);second=h.remove_source_copper(b,rjob)
result['removals']={'first':[r['matches'] for r in first],'second':[r['matches'] for r in second],
                    'remaining':count(b)}
# Tolerance accepts small coordinate quantization, but not a different nearby segment.
h.add_track(b,job,{**bad,'pts':[[.10005,.00001],[1.00005,.00001]]})
near=h.remove_source_copper(b,{'origin':[0,0],'remove_tracks_post':rjob['remove_tracks_post']})
h.add_track(b,job,{**bad,'pts':[[.1002,0],[1.0002,0]]})
far=h.remove_source_copper(b,{'origin':[0,0],'remove_tracks_post':rjob['remove_tracks_post']})
result['removals']['tolerance']=[near[0]['matches'],far[0]['matches']]

b=board();net=h.get_net(b,'AMBIGUOUS')
for _ in range(2):
    t=pcbnew.PCB_TRACK(b);t.SetStart(h.P(job,0,0));t.SetEnd(h.P(job,1,0))
    t.SetWidth(h.MM(.2));t.SetLayer(pcbnew.F_Cu);t.SetNet(net);b.Add(t)
h.add_via(b,job,{'net':'AMBIGUOUS','x':2,'y':2})
try:
    h.remove_source_copper(b,{'origin':[0,0],
        'remove_vias_post':[{'net':'AMBIGUOUS','x':2,'y':2}],
        'remove_tracks_post':[{'net':'AMBIGUOUS','layer':'F.Cu','pts':[[0,0],[1,0]]}]})
except RuntimeError as e:result['ambiguous']={'error':str(e),'remaining':count(b)}
else:raise AssertionError('ambiguous removals must fail')

b=board()
for endpoint in ([1,0],[0,1]):
    h.add_track(b,job,{'net':'DANGLING','layer':'F.Cu','width':.2,'pts':[[0,0],endpoint]})
for point in ([0,0],[2,2]):h.add_via(b,job,{'net':'DANGLING','x':point[0],'y':point[1]})
target=next(t for t in b.GetTracks() if type(t) is pcbnew.PCB_TRACK and t.GetEnd().x==h.MM(1))
keep_via=next(t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetPosition().x==0)
keep_uuid=keep_via.m_Uuid.AsString()
target_via=next(t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetPosition().x==h.MM(2))
drc={'violations':[{'type':'track_dangling','items':[
    {'uuid':target.m_Uuid.AsString(),'pos':{'x':99,'y':99}},
    {'uuid':keep_via.m_Uuid.AsString(),'pos':{'x':0,'y':0}},
    {'pos':{'x':0,'y':0}}]},
    {'type':'via_dangling','items':[{'uuid':target_via.m_Uuid.AsString()}]}]}
f=Path(sys.argv[2])/'cleanup.kicad_pcb';pcbnew.SaveBoard(str(f),b)
f.with_suffix('.kicad_pro').write_text('{}',encoding='utf-8');b=pcbnew.LoadBoard(str(f))
report=Path(sys.argv[2])/'cleanup-drc.json';report.write_text(json.dumps(drc),encoding='utf-8')
n=h.remove_dangling(b,{'drc_report':str(report)})
result['cleanup']={'removed':n,'repeat':h.remove_dangling(b,{'drc_report':str(report)}),'remaining':count(b),
    'kept_endpoint_track':sum(type(t) is pcbnew.PCB_TRACK and t.GetEnd().y==h.MM(1) for t in b.GetTracks()),
    'kept_wrong_type_uuid':sum(t.m_Uuid.AsString()==keep_uuid for t in b.GetTracks())}

b=board();errors=[]
for operation in (
    lambda:h.add_track(b,job,{'net':'LAYER','layer':'Inner2.Cu','width':.15,'pts':[[0,0],[1,0]]}),
    lambda:h.add_zone(b,job,{'net':'LAYER','layer':'Inner2.Cu','polygon':[[0,0],[1,0],[1,1]]}),
    lambda:h.add_texts(b,{'origin':[0,0],'texts':[{'text':'fixture','at':[0,0],'layer':'F.SilkscreenTypo'}]}),
    lambda:h.remove_source_copper(b,{'origin':[0,0],
        'remove_tracks_post':[{'net':'LAYER','layer':'Inner2.Cu','pts':[[0,0],[1,0]]}]})):
    try:operation()
    except ValueError as e:errors.append(str(e))
    else:raise AssertionError('unknown layer must fail before adding or removing geometry')
result['unknown_layers']={'errors':errors,'tracks':count(b),'zones':len(list(b.Zones())),
                           'drawings':len(list(b.GetDrawings()))}
print(json.dumps(result))
'''
    completed = subprocess.run([str(python), "-I", "-c", script, str(ROOT), str(scratch)],
                               capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "swig/python detected a memory leak" not in completed.stdout + completed.stderr
    return json.loads(completed.stdout.splitlines()[-1])


def test_repeated_tracks_preserve_distinct_geometry_layers_widths_nets_and_arcs(finish_geometry):
    assert finish_geometry["track_counts"] == [2, 2, 4, 6, 8, 10, 11]
    assert finish_geometry["arc_and_chord_count"] == 2


def test_repeated_through_vias_preserve_other_spans_dimensions_and_nets(finish_geometry):
    assert finish_geometry["via_counts"] == [2, 3, 4, 5, 6]
    assert [2, "F.Cu", "In1.Cu"] in finish_geometry["via_spans"]
    assert [4, "F.Cu", "B.Cu"] in finish_geometry["via_spans"]


def test_width_restoration_is_repeatable_but_can_introduce_clearance_failure(finish_geometry):
    widths = finish_geometry["widths"]
    assert widths["widened"] == 1 and widths["repeat"] == 0
    assert widths["tracks"] == [0.15, 0.15, 0.3] and widths["via"] == 0.12
    # Actual pcbnew geometry demonstrates why widening must be followed by DRC.
    assert widths["gap_before"] > 0.15 > widths["gap_after"]


def test_loaded_board_zones_are_replaced_without_duplicates_or_stale_polygons(finish_geometry):
    assert finish_geometry["zones"] == {"counts": [2, 2, 2], "updated_count": 1,
                                        "updated_bounds": [5.0, 6.0]}


def test_source_removals_are_exact_tolerant_and_repeatable(finish_geometry):
    assert finish_geometry["removals"] == {"first": [1, 1], "second": [0, 0],
                                           "remaining": 3, "tolerance": [1, 0]}


def test_ambiguous_removal_fails_before_any_requested_item_is_deleted(finish_geometry):
    assert "ambiguous source track removal" in finish_geometry["ambiguous"]["error"]
    assert finish_geometry["ambiguous"]["remaining"] == 3


def test_dangling_cleanup_uses_uuid_and_type_instead_of_shared_positions(finish_geometry):
    assert finish_geometry["cleanup"] == {"removed": 2, "repeat": 0, "remaining": 2,
                                         "kept_endpoint_track": 1, "kept_wrong_type_uuid": 1}


def test_unknown_layers_fail_before_adding_or_removing_geometry(finish_geometry):
    result = finish_geometry["unknown_layers"]
    assert len(result["errors"]) == 4
    assert all("Unknown KiCad layer name" in message for message in result["errors"])
    assert result["tracks"] == result["zones"] == result["drawings"] == 0
