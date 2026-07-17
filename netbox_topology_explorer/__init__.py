try:
    from netbox.plugins import PluginConfig
except Exception:
    # Minimal fallback for local development / tests when NetBox is not
    # available. This avoids import-time errors during pytest collection.
    class PluginConfig:  # type: ignore
        pass


try:
    from django.utils.translation import gettext_lazy as _
except Exception:
    # Same rationale as the PluginConfig fallback above: Django is not a
    # declared dependency of this package (it's provided by NetBox at
    # runtime), so pytest collection must not require it.
    def _(s):
        return s


class TopologyConfig(PluginConfig):
    name = "netbox_topology_explorer"
    verbose_name = _("Topology Explorer")
    description = _(
        "Graphically displays devices in a location and the full cable path trace"
    )
    version = "0.2.0"
    author = "G1tHub-PRO"
    base_url = "topology"

    # No custom model: reads only existing NetBox data.


config = TopologyConfig
