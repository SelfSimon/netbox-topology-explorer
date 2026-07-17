"""
NetBox topology — targeted CablePath scan with batch object resolution.

For a given set of device PKs we:
1. Find all cable-termination node-strings belonging to those devices.
2. Filter CablePaths at the DB level via _nodes__overlap (GIN-indexed).
3. Parse the raw JSON ``path`` field and batch-fetch referenced objects
   (one query per ContentType instead of one per node).
"""

from collections import defaultdict

CABLE_SCAN_CACHE_TTL = 30

_TERMINATION_MODEL_NAMES = (
    "interface",
    "consoleport",
    "consoleserverport",
    "powerport",
    "poweroutlet",
    "frontport",
    "rearport",
)


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
    role_obj = getattr(device, "role", None) if device else None
    role_color = getattr(role_obj, "color", "") or "" if role_obj else ""
    info = {
        "name": getattr(obj, "name", None) or str(obj),
        "model": model,
        "device": device.name if device else None,
        "device_pk": device.pk if device else None,
        "device_url": device_url,
        "device_role": role_obj.name if role_obj else "",
        "device_role_color": "#" + role_color if role_color else "",
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


def _device_termination_nodes(device_pks):
    """
    Return a list of node-strings (``"<ct_id>:<pk>"``) for all cable
    terminations belonging to the given device PKs.
    """
    from django.contrib.contenttypes.models import ContentType

    nodes = []
    for model_name in _TERMINATION_MODEL_NAMES:
        try:
            ct = ContentType.objects.get(app_label="dcim", model=model_name)
        except ContentType.DoesNotExist:
            continue
        term_pks = (
            ct.model_class()
            .objects.filter(device__pk__in=device_pks)
            .values_list("pk", flat=True)
        )
        for pk in term_pks:
            nodes.append(f"{ct.pk}:{pk}")
    return nodes


def _batch_resolve_objects(path_rows):
    """
    Given raw ``path`` JSON from multiple CablePaths, bulk-fetch every
    referenced object with one query per ContentType.

    Returns ``{node_string: model_instance}``.
    """
    from django.contrib.contenttypes.models import ContentType

    by_ct = defaultdict(set)
    for raw_path in path_rows:
        for step in raw_path:
            for node_str in step:
                ct_id, obj_pk = node_str.split(":")
                by_ct[int(ct_id)].add(int(obj_pk))

    resolved = {}
    for ct_id, pks in by_ct.items():
        ct = ContentType.objects.get_for_id(ct_id)
        model_cls = ct.model_class()
        if model_cls is None:
            continue
        qs = model_cls.objects.filter(pk__in=pks)
        if hasattr(model_cls, "device"):
            qs = qs.select_related("device", "device__role")
        for obj in qs:
            resolved[f"{ct_id}:{obj.pk}"] = obj
    return resolved


def _scan_cable_paths(device_pks):
    """
    Scan CablePaths relevant to the given device PKs.

    1. Build termination node-strings for devices.
    2. Filter CablePaths via _nodes__overlap (GIN-indexed).
    3. Batch-resolve all referenced objects.
    4. Return a list of (elements, device_pks_in_path) tuples.

    Results are cached per device-set for CABLE_SCAN_CACHE_TTL seconds.
    """
    from django.core.cache import cache as django_cache

    cache_key = "netbox_topo:scan:" + _make_cache_key(device_pks)
    cached = django_cache.get(cache_key)
    if cached is not None:
        return cached

    term_nodes = _device_termination_nodes(device_pks)
    if not term_nodes:
        django_cache.set(cache_key, [], CABLE_SCAN_CACHE_TTL)
        return []

    from dcim.models import CablePath

    cable_paths = list(
        CablePath.objects.filter(_nodes__overlap=term_nodes).only("path")
    )

    if not cable_paths:
        django_cache.set(cache_key, [], CABLE_SCAN_CACHE_TTL)
        return []

    raw_paths = [cp.path for cp in cable_paths]
    obj_map = _batch_resolve_objects(raw_paths)

    results = []
    for raw_path in raw_paths:
        elements = []
        path_device_pks = []
        for step in raw_path:
            for node_str in step:
                obj = obj_map.get(node_str)
                if obj is None:
                    continue
                if _is_cable(obj):
                    elements.append({"kind": "link", **_obj_info(obj)})
                else:
                    elements.append({"kind": "port", **_obj_info(obj)})
                    d = _device_of(obj)
                    if d:
                        path_device_pks.append(d.pk)

        if path_device_pks:
            results.append((elements, path_device_pks))

    django_cache.set(cache_key, results, CABLE_SCAN_CACHE_TTL)
    return results


def _make_cache_key(device_pks):
    """Stable short cache key from a set of device PKs."""
    raw = ",".join(str(pk) for pk in sorted(device_pks))
    return _short_hash(raw)


def _short_hash(s):
    import hashlib

    return hashlib.md5(s.encode()).hexdigest()[:12]


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
                role=el.get("device_role", ""),
                color=el.get("device_role_color", ""),
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

    scan_results = _scan_cable_paths(location_pks)
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

    scan_results = _scan_cable_paths(all_location_pks)
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
