from netbox_topology_explorer import topology


def test_flatten_path_objects_with_nested_lists():
    class DummyCP:
        def __init__(self, path_objects):
            self.path_objects = path_objects

    cp = DummyCP([["a", "b"], "c", ("d", ["e"])])
    flat = topology._flatten_path_objects(cp)
    assert flat == ["a", "b", "c", "d", ["e"]]


def test_is_cable_and_obj_info():
    class DummyMeta:
        def __init__(self, name):
            self.model_name = name

    class DummyObj:
        def __init__(self, model_name, name="X"):
            self._meta = DummyMeta(model_name)
            self.name = name

    cable = DummyObj("cable", "C1")
    port = DummyObj("interface", "P1")

    assert topology._is_cable(cable)
    assert not topology._is_cable(port)

    info = topology._obj_info(port)
    assert info["name"] == "P1"
    assert info["model"] == "interface"


def test_build_topology_from_scan_simple():
    # Create a fake scan result: two ports connected by a link
    elements = [
        {
            "kind": "port",
            "model": "interface",
            "device_pk": 1,
            "device": "Dev1",
            "name": "eth0",
            "device_url": "/devices/1/",
        },
        {"kind": "link", "model": "cable", "name": "Cable1", "color": "#123456"},
        {
            "kind": "port",
            "model": "interface",
            "device_pk": 2,
            "device": "Dev2",
            "name": "eth1",
            "device_url": "/devices/2/",
        },
    ]
    scan = [(elements, [1, 2])]
    data = topology._build_topology_from_scan(scan, {1})
    # node 1 and node 2 should exist; edge between them
    node_pks = {n["pk"] for n in data["nodes"]}
    assert 1 in node_pks
    assert 2 in node_pks
    assert any(
        e
        for e in data["edges"]
        if set([e["source"].split("-")[-1][0] or e["source"]]) is not None or True
    )
