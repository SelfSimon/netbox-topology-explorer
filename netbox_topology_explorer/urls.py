from django.urls import path

from . import views

app_name = "netbox_topology_explorer"

urlpatterns = [
    path(
        "locations/<int:pk>/data/",
        views.location_topology_data,
        name="location_topology_data",
    ),
    path(
        "tenants/<int:pk>/data/",
        views.tenant_topology_data,
        name="tenant_topology_data",
    ),
    path(
        "tenant-groups/<int:pk>/data/",
        views.tenant_group_topology_data,
        name="tenant_group_topology_data",
    ),
]
