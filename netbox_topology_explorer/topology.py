"""
NetBox topology — read via CablePath.path_objects

Approach: we iterate ONLY ONCE over all NetBox CablePaths (a table that is
generally small in practice — a few hundred rows — as a preliminary SQL
filter on the JSON 'path' field proved slower than a full scan due to the
lack of a usable GIN index on this version of NetBox).

For a single location, we filter paths that involve its devices.
For multiple locations (Tenant view), we perform the scan once and distribute
paths to each relevant location instead of re-scanning for each location
(gain proportional to the number of locations).
"""


def _device_of(obj):
    """Return the device associated with a NetBox object, or None."""
    return getattr(obj, "device", None)


def _obj_info(obj):
    """Serialize any NetBox object into a JSON-friendly dict."""
    if obj is None:
        return {}
    model = obj._meta.model_name
    device = _device_of(obj)
    raw_color = getattr(obj, "color", "") or ""
    device_url = None
    if device and hasattr(device, "get_absolute_url"):
        try:
            device_url = device.get_absolute_url()
        except Exception:
            pass
    info = {
        "name": getattr(obj, "name", None) or str(obj),
        "model": model,
        "device": device.name if device else None,
        "device_pk": device.pk if device else None,
        "device_url": device_url,
        "color": "#" + raw_color if raw_color else "",
        "url": None,
    }
    if hasattr(obj, "get_absolute_url"):
        try:
            info["url"] = obj.get_absolute_url()
        except Exception:
            pass
    return info


def _is_cable(obj):
    return obj._meta.model_name in ("cable", "wirelesslink")


def _flatten_path_objects(cp):
    """Flatten CablePath.path_objects into a flat list of objects."""
    try:
        raw = cp.path_objects
    except Exception:
        return []
    flat = []
    for item in raw:
        if isinstance(item, (list, tuple)):
            flat.extend(item)
        else:
            flat.append(item)
    return flat


def _scan_all_cable_paths():
    """
    Single scan of all NetBox CablePaths. Returns a list of tuples
    (elements, device_pks_in_path) for reuse across multiple locations
    without repeating the scan.
    """
    from dcim.models import CablePath

    results = []
    for cp in CablePath.objects.all():
        flat = _flatten_path_objects(cp)
        if not flat:
            continue

        elements = []
        device_pks_in_path = []
        for obj in flat:
            if _is_cable(obj):
                elements.append({"kind": "link", **_obj_info(obj)})
            else:
                elements.append({"kind": "port", **_obj_info(obj)})
                d = _device_of(obj)
                if d:
                    device_pks_in_path.append(d.pk)

        if not device_pks_in_path:
            continue

        results.append((elements, device_pks_in_path))

    return results


def _build_topology_from_scan(scan_results, location_pks):
    """
    Build nodes/edges/paths for a given set of location_pks,
    from an already-performed scan (list of (elements, device_pks_in_path)).
    """
    nodes = {}
    edges = {}
    paths = []
    seen_sigs = set()

    def ensure_node(pk, name, url=None, external=False, role="", color=""):
        if pk is None:
            return
        if pk in nodes:
            if role and not nodes[pk]["role"]:
                nodes[pk]["role"] = role
                nodes[pk]["color"] = color
            if not external:
                nodes[pk]["external"] = False
            return
        nodes[pk] = {
            "id": f"device-{pk}",
            "pk": pk,
            "label": name or f"Device {pk}",
            "url": url,
            "external": external,
            "role": role,
            "color": color,
        }

    def add_edge(pk_a, pk_b, cable_color=""):
        if pk_a is None or pk_b is None or pk_a == pk_b:
            return
        key = tuple(sorted((pk_a, pk_b)))
        if key not in edges:
            edges[key] = {
                "id": f"edge-{key[0]}-{key[1]}",
                "source": f"device-{key[0]}",
                "target": f"device-{key[1]}",
                "color": cable_color,
            }

    for elements, device_pks_in_path in scan_results:
        if not any(pk in location_pks for pk in device_pks_in_path):
            continue

        ports_info = [el for el in elements if el["kind"] == "port"]
        sig = tuple(
            f"{p.get('model')}|{p.get('device_pk')}|{p.get('name')}" for p in ports_info
        )
        if not sig:
            continue
        canonical = min(sig, sig[::-1])
        if canonical in seen_sigs:
            continue
        seen_sigs.add(canonical)

        device_seq = []
        for el in elements:
            if el["kind"] != "port":
                continue
            dpk = el.get("device_pk")
            if dpk is None:
                continue
            ensure_node(
                dpk,
                el.get("device"),
                el.get("device_url"),
                external=(dpk not in location_pks),
            )
            if not device_seq or device_seq[-1] != dpk:
                device_seq.append(dpk)

        # Reorient the path so that the local device is always first
        # ("Source device" column in the UI).
        ports_in_order = [el for el in elements if el["kind"] == "port"]
        if ports_in_order:
            first_pk = ports_in_order[0].get("device_pk")
            last_pk = ports_in_order[-1].get("device_pk")
            first_is_local = first_pk in location_pks
            last_is_local = last_pk in location_pks
            if last_is_local and not first_is_local:
                elements = elements[::-1]
                device_seq = device_seq[::-1]

        cable_color = ""
        for el in elements:
            if el.get("kind") == "link" and el.get("color"):
                cable_color = el["color"]
                break
        for a, b in zip(device_seq, device_seq[1:]):
            add_edge(a, b, cable_color=cable_color)

        paths.append(
            {
                "id": f"path-{len(paths)}",
                "elements": elements,
                "device_pks": sorted(set(device_seq)),
            }
        )

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "paths": paths,
    }


def build_location_topology(location):
    """Build nodes + edges + paths for a single location."""
    from dcim.models import Device

    devices_qs = list(Device.objects.filter(location=location).select_related("role"))
    location_pks = {d.pk for d in devices_qs}

    scan_results = _scan_all_cable_paths()
    data = _build_topology_from_scan(scan_results, location_pks)

    # Ensure all location devices are nodes even when uncabled,
    # with their role/colour properly set.
    nodes_by_pk = {n["pk"]: n for n in data["nodes"]}
    for d in devices_qs:
        role_obj = getattr(d, "role", None)
        role_name = role_obj.name if role_obj else ""
        role_color = "#" + role_obj.color if role_obj and role_obj.color else ""
        if d.pk in nodes_by_pk:
            if not nodes_by_pk[d.pk]["role"]:
                nodes_by_pk[d.pk]["role"] = role_name
                nodes_by_pk[d.pk]["color"] = role_color
            nodes_by_pk[d.pk]["external"] = False
        else:
            nodes_by_pk[d.pk] = {
                "id": f"device-{d.pk}",
                "pk": d.pk,
                "label": d.name,
                "url": d.get_absolute_url(),
                "external": False,
                "role": role_name,
                "color": role_color,
            }

    data["nodes"] = list(nodes_by_pk.values())
    return data


def build_multi_location_topology(locations):
    """
    Build the aggregated graph for multiple locations IN A SINGLE CablePath
    SCAN (instead of one scan per location), annotating each node/path with
    its originating location.
    """
    from dcim.models import Device

    locations = list(locations)
    scan_results = _scan_all_cable_paths()

    # device pk -> location name (to annotate each node/path afterwards)
    device_to_location = {}
    all_location_pks = set()
    devices_by_location = {}

    for location in locations:
        devs = list(Device.objects.filter(location=location).select_related("role"))
        pks = {d.pk for d in devs}
        devices_by_location[location.pk] = devs
        all_location_pks |= pks
        for pk in pks:
            device_to_location[pk] = location.name

    data = _build_topology_from_scan(scan_results, all_location_pks)

    # Annotate each node with its originating location (if known).
    for n in data["nodes"]:
        n["location"] = device_to_location.get(n["pk"], "")

    # Ensure all devices from all locations are represented as nodes.
    nodes_by_pk = {n["pk"]: n for n in data["nodes"]}
    for location in locations:
        for d in devices_by_location[location.pk]:
            role_obj = getattr(d, "role", None)
            role_name = role_obj.name if role_obj else ""
            role_color = "#" + role_obj.color if role_obj and role_obj.color else ""
            if d.pk in nodes_by_pk:
                if not nodes_by_pk[d.pk]["role"]:
                    nodes_by_pk[d.pk]["role"] = role_name
                    nodes_by_pk[d.pk]["color"] = role_color
                nodes_by_pk[d.pk]["external"] = False
                nodes_by_pk[d.pk]["location"] = location.name
            else:
                nodes_by_pk[d.pk] = {
                    "id": f"device-{d.pk}",
                    "pk": d.pk,
                    "label": d.name,
                    "url": d.get_absolute_url(),
                    "external": False,
                    "role": role_name,
                    "color": role_color,
                    "location": location.name,
                }

    data["nodes"] = list(nodes_by_pk.values())

    # Annotate each path with the location(s) it crosses.
    for p in data["paths"]:
        locs = sorted(
            {
                device_to_location.get(pk, "")
                for pk in p.get("device_pks", [])
                if device_to_location.get(pk)
            }
        )
        p["location"] = " / ".join(locs) if locs else ""

    return data
