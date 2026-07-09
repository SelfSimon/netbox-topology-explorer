from dcim.models import Device, Location
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from netbox.views import generic
from tenancy.models import Tenant, TenantGroup
from utilities.views import ViewTab, register_model_view

from . import topology

# ─── Location ────────────────────────────────────────────────────────────────


@register_model_view(Location, "topology", path="topology")
class LocationTopologyView(generic.ObjectView):
    queryset = Location.objects.all()
    template_name = "netbox_topology_explorer/location_topology.html"

    tab = ViewTab(
        label="Topology",
        badge=lambda obj: Device.objects.filter(location=obj).count(),
        permission="dcim.view_device",
    )

    def get_extra_context(self, request, instance):
        return {
            "device_count": Device.objects.filter(location=instance).count(),
        }


def location_topology_data(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=403)
    location = get_object_or_404(Location, pk=pk)
    return JsonResponse(topology.build_location_topology(location))


# ─── Tenant ───────────────────────────────────────────────────────────────────


def _all_tenant_pks_in_group(group):
    pks = list(group.tenants.values_list("pk", flat=True))
    for child in group.children.all():
        pks.extend(_all_tenant_pks_in_group(child))
    return pks


@register_model_view(Tenant, "topology", path="topology")
class TenantTopologyView(generic.ObjectView):
    queryset = Tenant.objects.all()
    template_name = "netbox_topology_explorer/tenant_topology.html"

    tab = ViewTab(
        label="Topology",
        badge=lambda obj: Location.objects.filter(tenant=obj).count(),
        permission="dcim.view_device",
    )

    def get_extra_context(self, request, instance):
        locations = Location.objects.filter(tenant=instance)
        return {
            "location_count": locations.count(),
            "data_url": f"/plugins/topology/tenants/{instance.pk}/data/",
        }


def tenant_topology_data(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=403)
    tenant = get_object_or_404(Tenant, pk=pk)
    locations = Location.objects.filter(tenant=tenant)
    return JsonResponse(topology.build_multi_location_topology(locations))


# ─── TenantGroup ──────────────────────────────────────────────────────────────


@register_model_view(TenantGroup, "topology", path="topology")
class TenantGroupTopologyView(generic.ObjectView):
    queryset = TenantGroup.objects.all()
    template_name = "netbox_topology_explorer/tenant_topology.html"

    tab = ViewTab(
        label="Topology",
        badge=lambda obj: Location.objects.filter(
            tenant__in=_all_tenant_pks_in_group(obj)
        ).count(),
        permission="dcim.view_device",
    )

    def get_extra_context(self, request, instance):
        tenant_pks = _all_tenant_pks_in_group(instance)
        locations = Location.objects.filter(tenant__in=tenant_pks)
        return {
            "location_count": locations.count(),
            "data_url": f"/plugins/topology/tenant-groups/{instance.pk}/data/",
        }


def tenant_group_topology_data(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=403)
    group = get_object_or_404(TenantGroup, pk=pk)
    tenant_pks = _all_tenant_pks_in_group(group)
    locations = Location.objects.filter(tenant__in=tenant_pks)
    return JsonResponse(topology.build_multi_location_topology(locations))
