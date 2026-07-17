# Changelog

All notable changes to this project will be documented in this file.

## 0.2.0
- Add fullscreen toggle for the topology graph and trace panel.
- Add English/French i18n support.
- Render topology graph for tenants and tenant groups.
- Replace side-panel trace with a compact, role-coloured diagram; restore per-cable colours with theme-aware glow.
- Auto-fit view on load with faster initial convergence.
- Performance: targeted CablePath scan, pre-computed adjacency map, reduced tick overhead, fixed TenantGroup N+1 query.
- Fix trace modal styling to use NetBox's native card/table classes.

## 0.1.1
- Packaging/CI: switch PyPI uploads to Trusted Publishers (OIDC), merge build and publish into a single job.

## 0.1.0 - Initial alpha
- Initial implementation: topology view per location/tenant, cable path tracing.
