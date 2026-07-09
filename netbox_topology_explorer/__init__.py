try:
    from netbox.plugins import PluginConfig
except Exception:
    # Minimal fallback for local development / tests when NetBox is not
    # available. This avoids import-time errors during pytest collection.
    class PluginConfig:  # type: ignore
        pass


class TopologyConfig(PluginConfig):
    name = "netbox_topology_explorer"
    verbose_name = "Topology Explorer"
    description = (
        "Graphically displays devices in a location and the full cable path trace"
    )
    version = "0.1.0"
    author = "G1tHub-PRO"
    base_url = "topology"

    # No custom model: reads only existing NetBox data.


config = TopologyConfig
