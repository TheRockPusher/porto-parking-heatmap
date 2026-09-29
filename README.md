# Porto Parking — Estimated Pressure, Supply & Tariffs

[![Build and checks](https://github.com/TheRockPusher/porto-parking-heatmap/actions/workflows/build.yml/badge.svg)](https://github.com/TheRockPusher/porto-parking-heatmap/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A map of **estimated relative parking pressure** in Porto, alongside the published parking inventory: paid streets, limited-duration tariff zones, western-area parking spaces, and municipal garages. The repository name retains “heatmap”. The default layer is a hexagonal pressure index (estimated demand versus estimated supply, ranked within Porto); inventory colors represent **tariff categories, not demand**.

**This is not live availability or occupancy.** The index is an estimate that ranks areas relative to each other; it does not say whether a space is free, is not calibrated against observed occupancy, and does not predict anything. No usable public citywide automobile parking history was established by the source research. See [Pressure index method](#pressure-index-method) and [TEMPORAL_DATA.md](TEMPORAL_DATA.md) for the method, evidence, limitations, and potential authorized access routes.

## Explore the map

- View the pressure layer (150 m hexagons) and switch between weekday daytime and overnight (residents); the choice is kept in the URL (`period=`). Cells without enough supply data are shown as “insufficient supply data”.
- Select a cell to see both periods' index and class, ratios, and the components: households without own parking, estimated on-street spaces, public off-street capacity, western active paid spaces, activity score, complaints, restriction days, coverage, and tariff zone.
- Toggle the inventory layers and reset the view to Porto.
- Search names in the loaded inventory, including accent-insensitive matches; this is not an address-geocoding service.
- Select a feature or search result to inspect its attributes, source, and reference date. “Original source attributes” load on demand when expanded.
- Compare categorical one-hour tariff references, not calculated stay totals.
- Filter western-area space records by active, inactive, or unknown inventory status. “Active” does **not** mean currently vacant.
- Consult the source/method dialog and linked official parking rules before relying on the information.

## Run locally

Requirements: **Node.js 22**, **pnpm 10**, and a browser with WebGL support. **Python 3.10+** is needed only to refresh the data or run pipeline tests; the pipeline uses the standard library, without pip dependencies. Docker and a routing server are not required.

```bash
pnpm install --frozen-lockfile
pnpm dev --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173>. If pnpm is not installed, replace `pnpm` with `npx pnpm@10` in these commands, for example `npx pnpm@10 install --frozen-lockfile`.

The committed `public/data/` files (manifest, hashed datasets, attribute tables) are enough to run or build the app. **Fetching data is not a setup prerequisite.** Parking data is served from the app itself; the background tiles still need external network access.

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

CI installs with `pnpm install --frozen-lockfile`, runs ESLint and the offline Python unit tests, then builds against the committed data. It does not refresh data or depend on live municipal endpoints.

## Data layer

All data is static JSON in `public/data/`, produced by `scripts/build_data.py`.

- `manifest.json` is the only mutable file. It holds `schemaVersion: 2`, `generatedAt`, per-dataset `path`, `bytes`, counts (and `attributesPath` for inventory layers), and the source records. The app fetches it with `cache: "no-cache"`.
- Dataset files are named `<name>.<hash10>.json` (first 10 hex characters of the SHA-256 of the content) and never change once published: `zones`, `streets`, `spaces`, `garages`, `pressure`.
- Raw source attributes of each inventory layer live in `<name>.attrs.<hash10>.json`, keyed by feature id. They are fetched only when a user expands “Original source attributes”.
- On publish, hashed files are written first, then the manifest, then stale hashed files and the legacy `porto-parking.json` are deleted. All files are written atomically.

Inventory files are GeoJSON FeatureCollections with trimmed properties (`id`, `kind`, `name`, plus zone/rate, status/resident zone, or garage address/operator/hours/capacity category). The pressure file is columnar: `schemaVersion`, `grid` (hex-axial-pointy, 150 m circumradius, origin, projection), `periods` (`daytime`, `overnight`), `method` constants, and `cells` as parallel arrays ordered by (r, q) (`q`, `r`, `coverage`, `zone`, `households`, `householdsWithParking`, `residentDemand`, `roadLengthM`, `onStreetEstimate`, `offStreetPublic`, `westernActiveSpaces`, `attraction`, `complaints`, `restrictionDays`, ratios and indices). `null` means not computable, never 0.

Sizes (2026-09-29 build): the former single bundle was 2,362,590 B raw / 468,496 B gzip. The initial load is now the manifest plus five datasets, about 1.25 MB raw / 147 KB gzip, with attributes excluded (gzip per file: zones 47.2 KB, streets 31.9 KB, spaces 48.1 KB, garages 1.1 KB, pressure 16.2 KB). Pressure cells render after two requests (manifest 2.4 KB + pressure 16.2 KB gzip). Raw attributes (about 700 KB raw / 153 KB gzip) load on demand.

Recommended hosting headers: `Cache-Control: public, max-age=31536000, immutable` for hashed files, `Cache-Control: no-cache` for `manifest.json`, and gzip or brotli for JSON.

### Inventory sources

The four inventory layers come from the [Câmara Municipal do Porto open-data portal](https://dadosabertos.cm-porto.pt/), catalogued as **CC0**.

| Layer | Municipal dataset | Coverage and interpretation | Published reference date |
|---|---|---|---|
| Paid streets | [Eixos Tarifados](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=eixos-tarifados) | Street lines, not a citywide bay/meter inventory; no capacity or payment history | 2022-12-20 |
| Tariff zones | [Zonas de Estacionamento de Duração Limitada — ZEDL](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=zonas-de-estacionamento-de-duracao-limitada-zedl) | Polygons for tariff classes I–IV, not individual spaces | 2023-03-21 |
| Western spaces | [Lugares de Estacionamento — Zona Ocidental](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=lugares-de-estacionamento-zonas-de-estacionamento-pago-zona-ocidental) | Western-area points only, including inactive and unknown-status records; not current citywide capacity | 2022-12-15 |
| Municipal garages | [Parques de Estacionamento Municipais](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=parques-de-estacionamento-municipais) | Facility locations and descriptive inventory, not every commercial garage or live free-space counts | 2022-12-16 |

These are the published reference dates documented during source research; the source panel shows the actual snapshot metadata. A recent retrieval time or generation time does **not** make the underlying inventory current. Unknown values remain `null`, not invented zeros. Garage `lightVehicleCapacity` is a **capacity category**, not total facility capacity and never available spaces.

### Refreshing the data

Fetching is not a setup prerequisite; the committed files are enough to run or build the app. To refresh, with network access:

```bash
pnpm fetch-data
# Equivalent entry point:
pnpm pipeline
# Or without Node/pnpm:
python3 scripts/build_data.py [--output-dir DIR] [--cache-dir DIR] [--offline]
```

The build takes roughly 15 s (measured 2026-09-29). Raw responses are cached in `.cache/porto-data/` (gitignored). `--offline` rebuilds from that cache only and fails on a cache miss; `--output-dir` writes elsewhere without touching `public/data`. Any source, licence or validation failure exits nonzero. Review generated data and source dates before committing a refresh. The app reads only these files at page load, not municipal or third-party endpoints (basemap tiles excepted).

## Pressure index method

The index is a **relative ranking of estimated demand against estimated supply** on 788 hexagonal cells (150 m circumradius, pointy-top) covering Porto. It is **not occupancy, availability, or a prediction**, and an index of 100 does not mean a full street. It is computed for two periods: weekday daytime and overnight (residents).

### Inputs (retrieved 2026-09-29)

| Input | Use | Licence / terms | Figures |
|---|---|---|---|
| INE Censos 2021 BGRI subsections | Households and households with own parking, apportioned to cells | INE open access, no conditions; cite INE | 1,659 subsections; 102,089 households; 45,074 with own parking |
| OpenStreetMap via Overpass (area 3603372453) | Eligible roads (primary, secondary, tertiary, unclassified, residential, living_street), car parks with `capacity` tags, weighted points of interest | ODbL | 14,255 elements; side-weighted eligible road length 558,445 m |
| PDM 2021 mobility diagnosis | Calibrates total public on-street spaces | Municipal planning document, cited figure | 64,680 spaces |
| Municipal garages (inventory) | Added to public off-street capacity when no qualifying OSM car park lies within 100 m | CC0 | — |
| `condicionamentos-de-transito` | Parking-type restriction days per cell (context only) | CC0 | 9,601 parking-type entries, 2019-03-21 to 2026-04-10 |
| ReportaPorto complaints | Aggregated counts per cell (context only) | No explicit licence | 115 parking-related records, 2025-08-20 to 2026-09-29 |

### Formulas

1. **Households.** Each census subsection's households and households with own parking are split equally across a 25 m lattice inside it and summed per cell. Resident demand = households − households with own parking (minimum 0).
2. **On-street supply (estimate).** OSM road length is side-weighted (two sides by default; sides removed where `parking:*` tags say no parking; private, tunnel and bridge ways excluded). Estimated on-street spaces in a cell = 64,680 × cell length / total length. This distributes a municipal total by road length; it is not a count of marked bays.
3. **Public off-street capacity.** Sum of OSM `capacity` tags on publicly accessible car parks plus municipal garages not within 100 m of one (11,603 in total). Private, permit-only and box/carport parking is excluded.
4. **Activity score.** Weighted count of points of interest (offices, education, hospitals, shops, food and drink, health, lodging, culture, stadiums). Each feature counts once at its highest weight. The weights are documented assumptions, listed in the pressure file's `method.poiWeights`.
5. **Ratios.** Overnight = resident demand / estimated on-street spaces. Daytime = activity score / (estimated on-street + public off-street spaces).
6. **Eligibility.** A ratio is computed only where the relevant supply is at least 5 spaces. 714 of 788 cells have an index for each period; 74 are shown as “insufficient supply data” (`null`, never 0).
7. **Index.** Among eligible cells, the 0–100 average-rank percentile of the ratio (ties share average rank). It is a ranking within Porto, not comparable with other cities or dates.

### Displayed but not part of the index

Parking-related complaints (codes C060901GO sidewalk/irregular parking, C060802GO double parking, C061701GO cycle-lane parking, C061100GO abandoned vehicle), municipal parking restrictions, and western-area paid spaces are shown in cell details and do not change the index. Only complaint code, position and time are kept, aggregated per cell; no text, photos, addresses or identifiers are stored. ReportaPorto exposes no explicit licence; the project relies on Lei 26/2016 art. 21.º(1) for aggregated counts, and this is a project decision, not a licence grant.

### Known biases and limits

- OSM completeness varies: missing `capacity` tags undercount off-street supply; missing parking tags affect side weighting; POI coverage is uneven.
- Census counts are from 2021 and are apportioned uniformly within subsections.
- The PDM total is a single calibration year and is spread by road length, so local street-level supply may differ substantially (for example where bays are absent or where informal parking occurs).
- POI weights are assumptions and no measured demand validates them. Daytime ignores commuters' origin, time-of-day turnover, and events; overnight ignores visitors.
- Household own-parking counts do not capture whether own parking is actually used.
- No occupancy ground truth was available to validate the index. See [TEMPORAL_DATA.md](TEMPORAL_DATA.md) for potential authorized data routes.

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

- `src/` — map, controls, pressure panel and cell details (`components/`), data loading (`hooks/useParkingData.ts`), URL state, and the hexagon/class helpers shared with the pipeline math (`lib/pressure.ts`).
- `public/data/` — committed `manifest.json` plus content-hashed datasets and attribute tables.
- `scripts/build_data.py` — data refresh entry point.
- `scripts/porto_data/` — pipeline modules: `common` (HTTP, raw cache, atomic writes, hashing), `geo` (projections, hex grid, GeoPackage geometry), `inventory` (four CKAN inventory sources), `pressure_sources` (census, OSM, restrictions, complaints), `pressure` (grid aggregation and index), `publish` (manifest, hashed files, pruning).
- `scripts/test_*.py` — offline pipeline unit tests (no network).
- `.cache/porto-data/` — gitignored raw response cache written by the pipeline.
- `.github/workflows/build.yml` — locked install, lint, Python tests, and build.
- [TEMPORAL_DATA.md](TEMPORAL_DATA.md) — temporal automobile parking research and access next steps.
- [HANDOFF.md](HANDOFF.md) — research context and project handoff.

## License and credits

Application code is [MIT licensed](LICENSE). This Porto adaptation is derived from [Wolfgang Schoenberger's SF Parking Heatmap](https://github.com/wolfiesch/sf-parking-heatmap); the original copyright and license are retained. Its historical San Francisco occupancy model and routing/data pipeline are not used for Porto.

### Data attribution

- Municipal inventory and restrictions: Câmara Municipal do Porto open-data portal, CC0.
- Map and pressure inputs: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL. Derived pressure cells incorporate OSM-derived road lengths, capacities and points of interest and remain subject to ODbL share-alike/attribution obligations for redistribution of the derived database.
- Households and own-parking counts: Instituto Nacional de Estatística (INE), Censos 2021, BGRI subsections; cite INE, Censos 2021.
- Complaint counts: Câmara Municipal do Porto ReportaPorto public web API; no explicit licence (see method section).
- Total on-street calibration: Porto Municipal Master Plan (PDM 2021) mobility diagnosis.

Thanks to Câmara Municipal do Porto for publishing the municipal datasets, and to MapLibre and OpenStreetMap contributors for the mapping ecosystem. Municipal CC0 data and third-party map data/services retain their own applicable licenses and conditions.
