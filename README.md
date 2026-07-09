# netbox-topology-explorer

NetBox plugin that adds a **Topology** tab to each location (`dcim.Location`),
each tenant and each tenant group.

The tab shows a graphical view of all devices in the selected scope. Clicking
on a device reveals the **full cable path trace** (port → cable → remote port,
traversing patch panels) and highlights the route. A tabular view with CSV
export is also available.

No data is created or modified: the plugin reads existing NetBox data and
reuses NetBox's native cable tracing engine.

## Compatibility

| Package | NetBox  | Python |
|---------|---------|--------|
| 0.1.x   | ≥ 4.5   | ≥ 3.10 |

## Installation

### 1. Install the package

```bash
pip install netbox-topology-explorer
# or from source:
pip install git+https://github.com/SelfSimon/netbox-topology-explorer.git
```

### 2. Enable the plugin in NetBox

Add the plugin to `configuration.py` (or `configuration/plugins.py` depending
on your setup):

```python
PLUGINS = [
    # ... other plugins
    'netbox_topology_explorer',
]
```

No migrations are required: the plugin does not create any database models.

### 3. Restart NetBox

```bash
sudo systemctl restart netbox netbox-rq
```

## Usage

- **Location** (Infrastructure > Locations) → Topology tab
- **Tenant** (Tenancy > Tenants) → Topology tab
- **Tenant Group** → Topology tab

Keyboard shortcuts in the graphical view:
- `Escape` — deselect the active device
- Mouse wheel — zoom
- Drag background — pan the graph

## License

MIT — see [LICENSE](LICENSE).

## Contributors

- [G1tHub-PRO](https://github.com/G1tHub-PRO) — Original author
- SelfSimon — Contributor

## Developer setup

Quick setup for contributors — creates a virtualenv, installs development
dependencies and installs the `pre-commit` git hooks.

PowerShell (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pre-commit install
pre-commit run --all-files
```

POSIX (macOS / Linux):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
pre-commit install
pre-commit run --all-files
```

If you prefer automation, run `scripts/bootstrap.ps1` on Windows or
`scripts/bootstrap.sh` on POSIX systems to perform these steps.
