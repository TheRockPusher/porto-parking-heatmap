# Porto Parking — Supply & Tariffs

[![Build and checks](https://github.com/TheRockPusher/porto-parking-heatmap/actions/workflows/build.yml/badge.svg)](https://github.com/TheRockPusher/porto-parking-heatmap/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A map of Porto's published parking inventory: paid streets, limited-duration tariff zones, western-area parking spaces, and municipal garages. The repository name retains “heatmap”, but the map's colors represent **tariff categories, not parking demand**.

**This is not live availability or occupancy.** It does not predict whether a space is free, estimate a typical week, or derive occupancy from payments. No usable public citywide automobile parking history was established by the source research. See [TEMPORAL_DATA.md](TEMPORAL_DATA.md) for evidence, limitations, and potential authorized access routes.

## Explore the map

- Toggle the four inventory layers and reset the view to Porto.
- Search names in the bundled inventory, including accent-insensitive matches; this is not an address-geocoding service.
- Select a map feature or search result to inspect its attributes, source, and reference date.
- Compare categorical one-hour tariff references, not calculated stay totals.
- Filter western-area space records by active, inactive, or unknown inventory status. “Active” does **not** mean currently vacant.
- Consult the source/coverage panel and linked official parking rules before relying on the information.

## Run locally

Requirements: **Node.js 22**, **pnpm 10**, and a browser with WebGL support. **Python 3.10+** is needed only to refresh the data or run pipeline tests; the pipeline uses the standard library, without pip dependencies. Docker and a routing server are not required.

```bash
pnpm install --frozen-lockfile
pnpm dev --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173>. If pnpm is not installed, replace `pnpm` with `npx pnpm@10` in these commands, for example `npx pnpm@10 install --frozen-lockfile`.

The committed `public/data/porto-parking.json` snapshot is enough to run or build the app. **Fetching municipal data is not a setup prerequisite.** Parking data is served from the app itself; the background tiles still need external network access.

### Working on a VPS over SSH

Start the loopback-bound development server above in the repository on the VPS. Keep that process running. On your own computer, open a separate terminal and forward the port:

```bash
ssh -N -L 5173:127.0.0.1:5173 work@YOUR_VPS_HOST
```

Then open <http://127.0.0.1:5173> on your computer. Replace `YOUR_VPS_HOST` and, if necessary, `work` with your SSH host/user. There is no need to expose the Vite port publicly or change the VPS firewall. Stop the tunnel and server with Ctrl+C when finished.

### Build and check

```bash
pnpm lint
python3 -m unittest discover -s scripts -p 'test_*.py'
pnpm build
pnpm preview --host 127.0.0.1 --port 4173 --strictPort
```

Preview is at <http://127.0.0.1:4173>; for a VPS, forward port 4173 using the same SSH pattern. `pnpm build` type-checks the frontend and writes the static site to `dist/`. Deploy that directory with a static web server; Vite preview is for checking a build, not a production server. The default build targets the site root; a subdirectory deployment requires the matching Vite `base` setting.

CI installs with `pnpm install --frozen-lockfile`, runs ESLint and the Python normalization regression tests, then builds against the committed snapshot. It does not refresh municipal data or depend on live municipal endpoints.

## Bundled data and refresh workflow

All four layers come from the [Câmara Municipal do Porto open-data portal](https://dadosabertos.cm-porto.pt/). The source catalogs identify these datasets as **CC0**. The JSON bundle records source URLs, metadata URLs, license, reference dates, retrieval timestamps, feature counts, and coverage caveats alongside the GeoJSON collections.

| Layer | Municipal dataset | Coverage and interpretation | Published reference date |
|---|---|---|---|
| Paid streets | [Eixos Tarifados](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=eixos-tarifados) | Street lines, not a citywide bay/meter inventory; no capacity or payment history | 2022-12-20 |
| Tariff zones | [Zonas de Estacionamento de Duração Limitada — ZEDL](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=zonas-de-estacionamento-de-duracao-limitada-zedl) | Polygons for tariff classes I–IV, not individual spaces | 2023-03-21 |
| Western spaces | [Lugares de Estacionamento — Zona Ocidental](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=lugares-de-estacionamento-zonas-de-estacionamento-pago-zona-ocidental) | Western-area points only, including inactive and unknown-status records; not current citywide capacity | 2022-12-15 |
| Municipal garages | [Parques de Estacionamento Municipais](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=parques-de-estacionamento-municipais) | Facility locations and descriptive inventory, not every commercial garage or live free-space counts | 2022-12-16 |

These are the published reference dates documented during source research. Consult the bundled source panel for the actual snapshot metadata. A recent retrieval time, bundle generation time, or portal migration timestamp does **not** make the underlying inventory current. Published update frequencies are not a guarantee that the geometries or attributes were recently revised.

To refresh explicitly, with network access:

```bash
pnpm fetch-data
# Equivalent entry point:
pnpm pipeline
# Or run without Node/pnpm:
python3 scripts/fetch_porto_data.py
```

The script retrieves public catalog metadata and GeoJSON, checks the CC0 license, validates and normalizes all four collections, and writes `public/data/porto-parking.json`. All sources must succeed before the existing snapshot is atomically replaced; a retrieval or validation failure exits nonzero and leaves the previous bundle in place. To inspect a separate output without replacing the committed bundle, use `python3 scripts/fetch_porto_data.py --output /tmp/porto-parking.json`.

Review the generated data and its source dates before committing a refreshed snapshot. Source geometries stay in WGS84; original attributes are retained with normalized values. Unknown values remain `null`, not invented zeros. Garage `lightVehicleCapacity` is a **capacity category**, not total facility capacity and never available spaces. The app loads only the bundled JSON, not municipal endpoints at page load.

## Tariffs and parking rules

The map presents reference **one-hour** prices: Zone I €1.20, Zone II €0.60, and Zones III/IV €0.40. Do not multiply these values to calculate a stay: official tariffs can include non-linear multi-hour or daily prices.

The cited municipal guidance lists paid hours of 09:00–19:00 on weekdays in Zones I–IV, plus 11:00–16:00 on Saturdays in Zone I, excluding holidays. Maximum stays and local restrictions depend on signage. Resident permits in the authorized area and disability-badge exemptions affect payment obligations. Separate restrictions, including Movida night-time restrictions on specified streets, may apply outside paid hours: outside the payment schedule does not mean parking is unrestricted.

Check current official guidance and signs on site:

- [Municipal parking guidance](https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/estacionamento-1)
- [Payment and tariff information](https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/pagamento-das-taxas-e-informacoes)
- [Municipal non-resident parking information](https://portaldomunicipe.cm-porto.pt/-/estacionamento-de-n%C3%A3o-aven%C3%A7ados-1)

This is an independent data exploration tool, not an official parking service or a guarantee of legal parking, current prices, or space availability.

## Mapping and external services

The frontend uses React 19, TypeScript, Vite 7, MapLibre GL and `react-map-gl`; the Vite configuration includes Tailwind CSS v4. Parking layers are local GeoJSON over the standard OpenStreetMap public raster basemap served from `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.

The background map requires external network access; tile requests go directly from the browser to OpenStreetMap's public tile service without API credentials. Browser verification discovered that the previous CARTO endpoint returned “API KEY REQUIRED” placeholder images despite successful HTTP responses, prompting the switch to the public OSM provider. This observation is not a claim that browser verification of the replacement has passed.

Keep the map's linked **[© OpenStreetMap contributors](https://www.openstreetmap.org/copyright)** attribution visible. [OpenStreetMap data is licensed under the ODbL](https://www.openstreetmap.org/copyright), while use of the hosted raster tiles is governed separately by the [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/). The public tile service has no SLA or availability guarantee: do not bulk-download or prefetch tiles, respect browser caching and the service's cache headers, and allow the browser to send its HTTP Referer rather than suppressing it. For heavier deployments, arrange a suitable tile provider or self-host instead of relying on this community-funded service.

Local parking layers do not depend on municipal network access at runtime, but basemap availability and browser WebGL support affect the map experience. OSM data licensing, tile service conditions, and municipal data licensing are separate from the application's MIT license.

## Project layout

- `src/` — Porto map, controls, feature details, and data loading.
- `public/data/porto-parking.json` — committed, normalized parking snapshot.
- `scripts/fetch_porto_data.py` — explicit municipal data refresh.
- `scripts/test_*.py` — offline pipeline regression tests.
- `.github/workflows/build.yml` — locked install, lint, Python tests, and build.
- [TEMPORAL_DATA.md](TEMPORAL_DATA.md) — temporal automobile parking research and access next steps.
- [HANDOFF.md](HANDOFF.md) — research context and project handoff.

## License and credits

Application code is [MIT licensed](LICENSE). This Porto adaptation is derived from [Wolfgang Schoenberger's SF Parking Heatmap](https://github.com/wolfiesch/sf-parking-heatmap); the original copyright and license are retained. Its historical San Francisco occupancy model and routing/data pipeline are not used for Porto.

Thanks to Câmara Municipal do Porto for publishing the municipal datasets, and to MapLibre and OpenStreetMap contributors for the mapping ecosystem. Municipal CC0 data and third-party map data/services retain their own applicable licenses and conditions.
