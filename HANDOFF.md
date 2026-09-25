# Porto Parking Heatmap — Conversation Handoff

## Implemented status — 2026-09-25

The user approved option 3: build the supply/tariff map while pursuing temporal-data access, orchestrate parallel work, launch and personally exercise the application, and commit the result. The sections below “Historical research context” preserve the earlier handoff; their statements about no implementation/installation/testing describe that earlier point, not the current repository.

- **Implemented:** Porto-centered interactive map with paid streets, tariff polygons, western paid-space records and municipal garages; layer toggles, active/inactive/unknown filters, accent-insensitive inventory search, map picking, feature details, source dates/licenses, official-rule links, responsive layout and shareable layer/status/selection URLs. No occupancy, availability, synthetic demand, SF estimates, bike demand or routing is presented.
- **Real snapshot:** `python3 scripts/fetch_porto_data.py` fetched and published 812 streets, 6 tariff features, 3,862 western spaces and 19 garages. Space statuses are 2,766 active / 53 inactive / 1,043 unknown. Published reference dates remain 2022–2023; retrieval in 2026 does not establish current conditions. Trindade's 292 light-vehicle category is explicitly not total capacity or free spaces.
- **Reproducibility:** four-source Python standard-library ingestion verifies CC0 metadata, reference dates, identifiers, geometry and normalized values before atomic publication. The committed bundle runs without municipal network access. Obsolete SF frontend modules, pipelines, assets and routing compose were removed; MIT/upstream attribution retained.
- **External map:** public OpenStreetMap raster tiles with visible attribution and documented tile-use policy. Actual browser inspection found CARTO returning “API KEY REQUIRED” image placeholders, so the implementation was corrected; OSM Porto road tiles were then visually verified. No tile credential is configured.
- **Temporal access:** see [TEMPORAL_DATA.md](TEMPORAL_DATA.md) for fresh catalog/broker/operator evidence and two ready-to-send Portuguese requests. No email was sent. The current public automobile `OffStreetParking` endpoint works, superseding the earlier endpoint finding: 20 entities, only one timestamped availability record, from **2020-08-07**. It is excluded as stale and without verified observation reuse rights. SABA pages expose free-space displays but usable timestamps/history and reuse permission remain unestablished. No feed met the integration requirements; actual occupancy remains conditional on provider data and rights.
- **Gates exercised:** frozen pnpm install, ESLint, 16 offline Python regression tests, TypeScript/Vite production build, and actual ingestion succeeded. Host verification used Node 26.9.0; CI is configured for Node 22, not locally exercised. No language server is configured; TypeScript compilation supplied type diagnostics.
- **Browser verification:** launched the production build on loopback port 4173 and exercised real Chromium at 1440×1000 and 390×844. Verified actual basemap/layers, direct garage marker picking, all four layer toggles, status counts, accent-insensitive search, all four feature-detail kinds, MultiPolygon selection, missing capacity, unknown/inactive spaces, source dialog, rules, reload persistence, malformed/absent URL selections, reset, mobile focus and no horizontal overflow. Corrected an unnamed mobile reset control and the search input's accessible label.
- **Failure scenarios:** intercepted snapshot HTTP 503 and malformed schema produced explicit errors; retry restored real data. Blocking external tiles produced a resource warning while local Trindade search/details remained usable.
- **Non-blocking gate output:** Vite warns about the MapLibre chunk exceeding 500 kB; Node 26 emits a dependency deprecation notice. pnpm skips esbuild's install script, but the production build succeeds using the installed platform binary.
- **Access:** [README.md](README.md) documents install, refresh, build, preview and an SSH tunnel from the user's PC. The verification preview is a loopback-bound development service, not a public production deployment. Browser dependencies were provisioned in the `work` user's cache without sudo or system-package changes.

## Historical research context — purpose and prior status

The user asked whether data sources exist to build something like https://github.com/wolfiesch/sf-parking-heatmap for the city of Porto, Portugal, and explicitly requested orchestration. Research was split into parallel investigations of parking temporal data/access and geographic/mobility sources, followed by verification of actual downloadable payloads.

The user subsequently requested a new folder inside their home projects folder and a fork of the original repository, using the authenticated GitHub CLI. This was completed. The latest request is this complete context handoff.

**Main conclusion:** Porto has usable public parking geography and regulatory data. No public citywide street-meter transaction history or block/hour automobile occupancy dataset was located. A parking supply/tariff map is feasible with the verified data; an SF-equivalent typical-week occupancy map requires additional data access. This is a research finding, not proof that such data does not exist privately.

No Porto application adaptation, dependency installation, build, or application tests have been performed. No implementation scope was approved. Do not confuse the recommendations below with work already done.

## Repository and environment

- Local repository: `/home/work/projects/porto-parking-heatmap`.
- Fork: https://github.com/TheRockPusher/porto-parking-heatmap
- Original/upstream: https://github.com/wolfiesch/sf-parking-heatmap
- GitHub account verified with `gh auth status`: `TheRockPusher`; Git protocol SSH. Never copy credentials or tokens into documentation.
- Executed: `gh repo fork wolfiesch/sf-parking-heatmap --fork-name porto-parking-heatmap --clone=false`.
- Executed: `gh repo clone TheRockPusher/porto-parking-heatmap /home/work/projects/porto-parking-heatmap`.
- Clone output confirmed automatic fetching of `upstream/main` from `wolfiesch/sf-parking-heatmap`.
- `gh repo view TheRockPusher/porto-parking-heatmap --json nameWithOwner,url,isFork,parent` verified `isFork: true` and the correct upstream parent.
- No commit was requested or created during this conversation.
- Research occurred on 2026-09-24; repository setup and handoff request followed on 2026-09-25. Endpoint accessibility, feed validity, and inventories are mutable.
- Host context: user's netcup VPS, Debian 13, x86_64, execution user `work`, home `/home/work`, no sudo privileges. This is not the user's separate PC. Preserve other projects and root configuration. Repo context/instructions applicable to future work must still be followed.

## User intent and interaction history

1. Research data sources that could make the SF project possible for Porto municipality, Portugal; orchestrate the investigation.
2. Create a folder in the home projects directory and fork/clone the original project there.
3. Write a complete handoff file in that repository containing the conversation context.

The research response distinguished verified sources from catalog claims, automobile parking from micromobility, city from metropolitan coverage, live snapshots from historical data, and inventory from measured occupancy. Maintain these distinctions in subsequent work.

## Reference application's functionality and assumptions

Source: https://github.com/wolfiesch/sf-parking-heatmap (README inspected).

- Typical-week parking visualization: 168 slots per block, seven days by 24 hours.
- City heatmap, neighborhood 3D columns, street/block paths and meter dots.
- Time playback, reference-time comparison, block details, address/radius search, shareable URL state.
- Optional bike-share demand overlay and drive/bike/walk isochrones.
- Stack: Vite 7, React 19, TypeScript, Tailwind CSS v4, deck.gl v9, MapLibre/react-map-gl; Python standard-library pipeline; optional local Valhalla Docker service; CARTO basemap.
- README identifies SF SODA datasets `8vzz-qzz9` for meters and `imvp-dq3v` for sessions, plus 311 parking-pressure information and Bay Wheels data.
- The README describes approximately 206 million meter transactions and a trailing 90-day aggregation window.
- Occupancy is estimated from session counts, not directly measured. Its stated formula uses sessions/week, `AVG_SESSION_HOURS = 1.2`, `COMPLIANCE_FACTOR = 1.33`, and meter count, clamped to [0,1]. Off-hours blend in 311 pressure.
- Do not transfer SF duration/compliance assumptions or off-hours pressure logic to Porto without local evidence.
- Paid sessions are not physical occupancy: residents/exemptions, unpaid parking, early departures, extensions and multiple payment channels matter.
- README describes files such as `scripts/aggregate_parking.py`, `fetch_meter_locations.py`, `fetch_enforcement_schedules.py`, `fetch_parking_supply.py`, `compute_block_paths.py`, and optional mobility/routing scripts. These were not modified or locally audited in this conversation.
- Original license: MIT.

## Critical portal access findings

Current portal: https://dadosabertos.cm-porto.pt/

- Homepage announces a new portal version under preparation; CKAN 2.11.6 is advertised.
- Legacy `https://opendata.porto.digital` failed DNS from the research environment. Old indexed URLs are leads, not verified working resources.
- Anonymous CKAN `package_list` and `package_show` worked:
  - https://dadosabertos.cm-porto.pt/api/3/action/package_list
  - https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=parques-de-estacionamento-municipais
- `package_search?q=estacionamento&rows=100` returned zero results despite relevant packages existing. Do not infer absence from search alone.
- Several resource URLs incorrectly advertise the private origin `http://192.168.221.240:8443`. Replacing only that origin with `https://dadosabertos.cm-porto.pt`, preserving the dataset/resource/download path, successfully downloaded the tested resources. This workaround was actually exercised.
- Many geographic datasets advertise CC0, public/free access and fortnightly updates. Their September 2026 metadata migration dates do not establish freshness: reference dates are often 2022–2023.
- Prefer GeoJSON for mapping: verified GeoJSON uses Porto longitude/latitude coordinates; some CSV geometry fields use projected coordinates. Establish CRS before converting CSV.
- Contact and API guidance: https://dadosabertos.cm-porto.pt/faqs ; municipal contact `dados@cm-porto.pt`.

## Verified parking geography

### 1. Paid streets — Eixos Tarifados

Metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=eixos-tarifados

Working download:
https://dadosabertos.cm-porto.pt/dataset/564ca386-9e19-11f1-84ed-6abdb6d5cf34/resource/3a72d8f7-a5a6-4d35-b58f-0bbe5a3b9999/download/ext-eixos-tarifados-geojson.geojson

- HTTP 200; 812 LineString features. Independently fetched and counted by the orchestrator after the research agent's report.
- Fields include `toponimo`, `tarifado`, `objectid`, `globalid`, geometry; all inspected `tarifado` values were `Sim`.
- CC0; reference date 2022-12-20.
- Useful for paid-street geometry and spatial joins.
- No capacity, meter ID, tariff-zone ID, payment events or enforcement hours. Not an SF-style meter/block-face inventory.

### 2. Limited-duration tariff zones — ZEDL

Metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=zonas-de-estacionamento-de-duracao-limitada-zedl

Working download:
https://dadosabertos.cm-porto.pt/dataset/67480551-9e19-11f1-84ed-6abdb6d5cf34/resource/982e8ba5-340d-4dc5-be03-1ba1521cbe56/download/ext-zonas-de-estacionamento-de-duracao-limitada-zedl-geojson.geojson

- Agent downloaded and parsed six polygons: one each for I, II, III and three for IV.
- Fields: `zona`, `valor_taxa`, `last_update`, `objectid`, geometry.
- Rate values: I 1.2; II 0.6; III and IV 0.4. Units not explicit in schema; values match official one-hour prices.
- CC0; reference date 2023-03-21.
- Catalog notes misleadingly describe individual parking spaces. Actual payload is tariff polygons, not space points or occupancy.

### 3. Individual paid spaces — western area

Metadata:
https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=lugares-de-estacionamento-zonas-de-estacionamento-pago-zona-ocidental

Working download:
https://dadosabertos.cm-porto.pt/dataset/5c04defd-9e19-11f1-84ed-6abdb6d5cf34/resource/ed32ec82-efbd-4921-8c4d-3fa4ac1597b0/download/ext-lugares-de-estacionamento-zonas-de-estacionamento-pago-zona-ocidental-geojson.geojson

- HTTP 200; 3,862 Point features. Independently fetched and counted by the orchestrator.
- Status counts: `Ativo` 2,766; `Inativo` 53; null 1,043.
- Fields include `toponimo`, `estado`, `num_zona`, `objectid`, `globalid`, geometry.
- CC0; reference date 2022-12-15.
- Closest verified bay-level supply source, but only western-area coverage. Do not call 3,862 current active capacity or extrapolate citywide.
- No meter/session/history fields. Resolve inactive/unknown records and coverage before using as an occupancy denominator.

### 4. Resident-permit zones

Metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=zonas-de-avencas-de-residentes

Working download:
https://dadosabertos.cm-porto.pt/dataset/6737d87d-9e19-11f1-84ed-6abdb6d5cf34/resource/f85dbf94-efcc-4ac6-a19f-cc338e324fd6/download/ext-zonas-de-avencas-de-residentes-geojson.geojson

- Agent parsed 87 polygons; fields include `num_zona`, `nom_zona`, `objectid`, geometry.
- CC0; reference date 2023-01-04.
- Potential geographic join to western spaces, but join completeness was not established.
- Resident zones are not the four tariff classes. No permit counts or occupied-space observations.

### 5. Municipal parking facilities

Metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=parques-de-estacionamento-municipais

Working downloads:
- GeoJSON: https://dadosabertos.cm-porto.pt/dataset/5ea79d81-9e19-11f1-84ed-6abdb6d5cf34/resource/7364670a-1fa0-4189-9729-5d314f8701f1/download/ext-parques-de-estacionamento-municipais-geojson.geojson
- CSV: https://dadosabertos.cm-porto.pt/dataset/5ea79d81-9e19-11f1-84ed-6abdb6d5cf34/resource/e9898000-f437-42d3-8c5b-22c5594052b2/download/ext-parques-de-estacionamento-municipais.csv
- DATEX II: https://dadosabertos.cm-porto.pt/dataset/5ea79d81-9e19-11f1-84ed-6abdb6d5cf34/resource/0a80df53-72a4-475b-914d-bd664872e4f9/download/parques_municipais.xml

CSV and GeoJSON were directly retrieved by the orchestrator; XML inspected by the temporal-data agent.

- 19 facilities, with names, streets, operators, concession status, opening hours, capacity categories and coordinates.
- CSV/GeoJSON reference date 2022-12-16; CC0; some capacities absent.
- XML is `ParkingTablePublication`, not `ParkingStatusPublication`; 19 parking records.
- XML publication/version timestamp `2026-09-04T11:00:00.072396` is not an occupancy observation timestamp.
- `parkingOccupancyDetectionType=manual` does not provide occupied/free counts. No actual occupancy observations found.
- Capacity inconsistency example: Trindade XML says 360 spaces, current STCP page says 345; GeoJSON lists 292 under its light-vehicle category with other categories separately. Reconcile category semantics, dates and authoritative totals before calculation.

### 6. Planning map, not operational inventory

Metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=carta-da-estrutura-viaria-e-estacionamento-pdm-2021

GeoPackage:
https://dadosabertos.cm-porto.pt/dataset/69fb64a5-9e19-11f1-84ed-6abdb6d5cf34/resource/2ff464dc-b9cf-4dce-8fa1-d8e03339d0c3/download/po_ceve.gpkg

Agent verified HEAD HTTP 200, 137,506,816 bytes; contents were not downloaded/inspected. CC0; reference 2021-07-08; planning road/parking provision rather than operational capacity. Advertised WMS GetCapabilities returned HTTP 500.

## Parking rules and operators

Official sources:
- https://portaldomunicipe.cm-porto.pt/-/estacionamento-de-n%C3%A3o-aven%C3%A7ados-1
- https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/estacionamento-1
- https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/pagamento-das-taxas-e-informacoes

Agent verified:
- Zones I–IV weekdays 09:00–19:00; Zone I also Saturday 11:00–16:00; holidays excluded per municipal mobility page.
- One-hour rates €1.20 / €0.60 / €0.40 / €0.40 for I / II / III / IV.
- Full tariffs are not universally linear: Zone II four hours €2.00 and daily €3.60 were shown.
- Maximum stays depend on signage, reported as two to ten hours.
- EPorto responsible for zones I–III; STCP Serviços for western/Foz zone-IV subzones 58–67 in the cited page.
- Resident-permit holders in their authorized area do not pay hourly fees and have no time limit; disability-badge exemptions also matter.
- Separate Movida street restrictions exist Friday/Saturday/holiday eves 20:00–08:00 on specified streets. Outside paid hours does not imply unrestricted parking.
- Official page links municipal GIS: https://portalgeo.cm-porto.pt/arcgis/apps/sites/#/mapas-do-porto/apps/d2308b9828a84777ab1c4cbc27b0e278/explore . Attempted ArcGIS item-data access returned HTTP 500; no operational feature service was verified.
- Some mobility pages triggered an erroneous reader `.md` variant; raw HTML retrieval succeeded. Do not treat that reader failure as proof the source is unavailable.

## Temporal automobile parking data: findings and limits

### No verified public street-level history

No publicly usable citywide Porto meter-session/payment-event dataset, block-hour occupancy history, or hourly street-demand aggregates were found. Static zones, bay locations and road lines cannot substitute for them.

### Coarse historical statistics exist

2023 STCP Serviços annual report, actually retrieved by the agent:
https://www.stcpservicos.pt/storage/app/media/Documentos%20Gerais/relatorio-stcpcompressed-1.pdf

- Printed p20: garage capacity 2,542, average occupancy 57.40%, users 591,441; separate street-parking column capacity 2,820 and users 164,660.
- Section 2.3.4: STCP assumed non-concessioned ZEDL operation on 2023-09-01; 124 meters operating since January 2020, 2,820 spaces across ten resident zones in Zone IV.
- Printed p61 / PDF page31: September–December 2023 revenue split 53% meters, 47% Via Verde app. This is revenue share, not necessarily session share.
- These broad historical indicators cannot generate 168 block-hour profiles. An app-only extract would not cover every payment channel.
- No open reuse license for the report was established.

2025 report was retrievable but text extraction incomplete across 117 pages; detailed indicators were NOT verified:
https://www.stcpservicos.pt/storage/app/media/Relat%C3%B3rio%20e%20Contas%20STCP%20Servi%C3%A7os_2025_Assinado%20com%20CLC%202.pdf

### Operational garage occupancy is a strong access lead

Sources:
- https://www.stcpservicos.pt/comunicacao/noticia/paineis-de-mensagem-variavel-mostram-ocupacao-dos-parques-de-estacionamento
- https://www.porto.pt/pt/noticia/paineis-de-mensagem-variavel-mostram-ocupacao-dos-parques-de-estacionamento
- https://www.stcpservicos.pt/estacionamento/parque-de-estacionamento-da-trindade

STCP article read by both agent and orchestrator confirms real-time occupancy information on roadside panels for Alfândega, Casa da Música, Cardosas, Duque de Loulé, Palácio da Justiça, Praça de Lisboa including Carlos Alberto/Praça dos Leões, Trindade and Ribeira. Partners: municipality, STCP Serviços, SABA; communications by Porto Digital; Cooperative-Streets project. Original municipal article dated 2023-01-27.

This proves an operational system was implemented, not that a public API, open license, historical archive, or continued operation today was verified. Current Trindade page provides capacity/opening/address information, not live vacancies.

**Inference/recommendation:** authorized garage-feed access may be an easier partnership route than citywide street transactions. Do not present this as an existing verified public integration.

### Formal municipal garage reporting route

Municipal code:
https://mobilidade.cm-porto.pt/files/uploads/cms/CRMP_vers%C3%A3o_atualizada_20251127.pdf

Agent read article D-3/58.º, printed p185: public-access car-park operators must provide supply, price and demand statistics, particularly monthly occupancy rates, submitted semiannually within 15 business days after semester end. This supports a data request, not a claim that reports are public. Monthly rates cannot reproduce hourly profiles.

### Telpark is not an open citywide dataset

Sources inspected by agent:
- https://www.telpark.com/pt/cidades/porto/
- https://www.telpark.com/pt/parquimetro/
- https://app.telpark.com/terms
- https://www.telpark.com/pt/empresas/telpark-business/

Porto payment/garage services and personal transaction history exist, but history requires account credentials. Business dashboards concern contracted accounts/fleets, not public citywide data. Terms restrict content reuse/derived services absent permission. No public transaction/history/live API was found. Payment/reservation also does not establish actual use of a space.

Geographic caution: Telpark's Porto listing includes Instituto CUF Porto in Senhora da Hora, Matosinhos, not Porto municipality; confirmed by https://www.cuf.pt/hospitais-e-clinicas/instituto-cuf-porto . Clip inventories to the municipal boundary.

### Legacy and national leads that must not be oversold

- FIWARE OffStreetParking specification contains an old Porto/Trindade example, not a verified live feed: https://fiware-datamodels.readthedocs.io/en/stable/Parking/OffStreetParking/doc/spec/index.html . Historic FIWARE announcement: https://www.fiware.org/2016/03/17/fiware-and-ngsiv2-towards-harmonized-apis-and-data-models-for-real-time-context-data/ . Example observations/dates are old; do not use example numbers as current occupancy.
- A documented legacy OffStreetParking host tested by the agent failed DNS; no working automobile feed was established from that lead.
- National Access Point actual endpoints tested:
  - https://www.nap-portugal.imt-ip.pt/API/api/informationTypes?local=pt
  - https://www.nap-portugal.imt-ip.pt/API/api/mapElements/?infotype=14&infotype=15&infotype=16&local=pt
  Parking category IDs 14/15/16 returned `active:false`; filtered map elements/suppliers were empty. UI parking categories do not prove Porto feed availability.
- https://dados.gov.pt/pt/datasets/ocupacao-de-parques-de-estacionamento-historico is EMEL/Lisbon history for 2020–2022, not Porto.
- Old U.Porto research lead: https://patents.google.com/patent/WO2015114592A1/en . Cited `http://www.dcc.fc.up.pt/~michel/parking.csv` returned 404 over HTTP and HTTPS. Described one free off-street lot's 24-hour entry/exit observations, not citywide meter demand. Not a usable replacement.

## Complementary mobility and routing sources

### Cycle infrastructure

Metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=ciclovias

Download:
https://dadosabertos.cm-porto.pt/dataset/53435aca-9e19-11f1-84ed-6abdb6d5cf34/resource/e5dd5310-1711-4cda-9759-1401a23f0965/download/ext-ciclovias-geojson.geojson

Agent parsed 358 lines: 258 `Executado`, 100 `Planeado`. Fields include street/name, surface, width, state and IDs. CC0, reference 2022-12-12. Filter planned segments for existing-network displays; lines alone are not a complete routable graph. This is infrastructure, not bike-share trip demand.

### Micromobility parking inventory

Metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=modos-suaves-de-transporte-implementado

Download:
https://dadosabertos.cm-porto.pt/dataset/5d103425-9e19-11f1-84ed-6abdb6d5cf34/resource/b7a7fdb3-8731-4ec2-968d-89262dc13e64/download/ext-modos-suaves-de-transporte-implementado-geojson.geojson

Agent parsed 230 points: 228 active, two inactive; attributes include `toponimo`, `n_id`, `estado`, `tipo_estac`, signage fields and `n_lugares`. CC0; reference 2022-12-20. Not automobile parking.

### Shared-mobility NGSI snapshot

Metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=urban-platform-sharing-spots-location

Endpoint actually retrieved anonymously by agent:
https://broker.fiware.urbanplatform.portodigital.pt/v2/entities?q=allowedVehicleType==twoWheeledVehicle&type=OnStreetParking&limit=1000

- Returned 230 entities; fields include `id`, location, address, description, `totalSpotNumber`, `occupiedSpotNumber`, `availableSpotNumber`, `vehicle_ids`, `allowedVehicleType`.
- Snapshot vehicle IDs included bicycle/scooter types from Bird, Bolt and Circ.
- Catalog CC0/free access; declared daily frequency.
- **Despite `OnStreetParking`, this query is for two-wheeled micromobility, not cars.**
- `availableSpotNumber` refers to free parking spots, not necessarily rentable bikes.
- No observation timestamp found in retrieved entities; freshness not established.
- No trip starts/ends, OD history or verified GBFS feed. Availability snapshots are not equivalent to trip demand.

### Routing with OSM/Geofabrik

- https://download.geofabrik.de/europe/portugal.html
- https://download.geofabrik.de/europe/portugal-latest.osm.pbf
- License: https://www.openstreetmap.org/copyright

Agent retrieved the download page and verified PBF HEAD HTTP 200, 423,811,894 bytes, Last-Modified 2026-09-24; source timestamp 2026-09-23T20:22:04Z. Large PBF was not downloaded. Use for Valhalla or other road/walk/bike routing and isochrones, clipping municipality rather than district/metro. Prefer raw PBF for routing tags. ODbL attribution and applicable share-alike obligations apply. Open map data does not promise free hosted routing/tiles, measured parking occupancy, complete parking capacity, or historical traffic speeds.

### STCP schedules and live buses

GTFS metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=horarios-paragens-e-rotas-stcp

GTFS download tested:
https://dadosabertos.cm-porto.pt/dataset/71490e40-9e19-11f1-84ed-6abdb6d5cf34/resource/51340c18-0ef5-4895-b099-cf7247ea54f4/download/gtfs_feed.zip

Agent opened 4,512,116-byte ZIP: 71 routes, 2,548 stops; schedule files present. Catalog CC0. **Feed validity 20260901–20260923: expired at research retrieval on September 24.** `calendar.txt` empty; schedules use `calendar_dates`. Metropolitan coverage; schedules are not passenger demand.

Live metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=urban-platform-bus-location

Endpoint: https://broker.fiware.urbanplatform.portodigital.pt/v2/entities?q=vehicleType==bus&limit=1000

Agent retrieved anonymous JSON, sample `observationDateTime=2026-09-24T21:24:53.00Z`; coordinates, speed, bearing, fleet ID, route/trip annotations and municipality information. Catalog CC0. NGSI snapshot, not verified GTFS-Realtime or passenger history. Check stale vehicles and coverage.

### Metro do Porto schedules

Operator page: https://www.metrodoporto.pt/pages/337

Working operator GTFS inspected:
https://www.metrodoporto.pt/metrodoporto/uploads/document/file/794/google_transit_04_09_2026.zip

Agent opened 332,920-byte ZIP: 85 stops, seven routes; calendars 20260907–20261025. Publicly linked for applications. **No explicit open reuse license verified.** Municipal catalog metadata has null license and `isopen:false`; do not label CC0.

Municipal metadata: https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=horarios-paragens-e-rotas-metro-porto

Catalog July ZIP returned HTTP 200 with zero bytes; operator link was working/fresher. Coverage is metropolitan, not just municipal Porto.

### National transit catalogs

- https://www.nap-portugal.imt-ip.pt/nap/multimodal
- https://www.nap-portugal.imt-ip.pt/nap/search
- https://www.stepp.pt/sigweb/

Agent retrieved pages/map shell describing stops/routes and shapefile exports, GTFS conversion pilot and NeTEx profile. No Porto-specific bulk history dataset verified here. STePP warns submitted information may be incomplete/unvalidated. No blanket license inferred. A search result at `/nap/multimodalsupplydetail/10201` concerned Pentágono Urbano/Cávado, not Porto.

## Recommended data request

Verified contacts:
- Municipal open data: `dados@cm-porto.pt`.
- EPorto: `eporto@eporto.pt`.
- STCP street parking: `estacionamento@stcpservicos.pt`.
- STCP garages: `parques@stcpservicos.pt`.

Request, without personal identifiers:
1. At least 90 days of anonymized paid sessions with start/end or paid duration and stable meter/street/zone IDs; alternatively hourly paid-occupancy/demand aggregates by street or zone.
2. Mapping from those IDs to geography, effective capacity and enforcement schedules, including changes over time.
3. Coverage of all payment channels, cancellations, extensions and semantics of overlapping records.
4. For garages: timestamped occupancy/free-space observations, capacity, closures and history; or authorized ongoing feed access and collection rights.
5. Reuse/publication license, rate limits, refresh cadence, retention and completeness/freshness guarantees.

No number plates, payment credentials or customer identifiers are needed. No request email was sent during this conversation.

## Feasibility and recommended decision

| Product | Evidence-based assessment |
| --- | --- |
| Paid-street, tariff, garage and accessibility map | Feasible with verified public sources, subject to freshness and coverage checks. |
| Live garage availability map | Conditional on obtaining authorized feed access; no public live feed verified. |
| Typical-week garage occupancy heatmap | Requires historical observations or authorized collection of a live feed over time. |
| SF-equivalent street/block-hour occupancy heatmap | Public sources located are insufficient; needs history and more complete effective capacity mapping. |
| Micromobility/cycle/transit overlays | Feasible in varying degrees; do not mistake infrastructure or snapshots for trip-demand history. |

Recommendation given to user: secure temporal parking data before investing in a claimed occupancy heatmap. A supply/tariff map is useful but must not be labeled measured demand or availability. If a later implementation is requested, confirm the intended product against these constraints rather than silently substituting synthetic demand or narrowing scope.

## Verification provenance and limits

- Parallel research agents investigated temporal/access and geographic/mobility slices. Findings above identify agent-only checks where relevant.
- Orchestrator directly retrieved the reference README, current portal, CKAN package list and garage package metadata, garage CSV and GeoJSON, FAQ, and STCP real-time-panel article.
- Orchestrator independently executed a Python network smoke check for paid-street and western-space GeoJSON, obtaining HTTP 200 and counts 812 / 3,862, with western status counts 2,766 active / 53 inactive / 1,043 null.
- An attempted Python eval tool failed before execution with EACCES creating its runner under `/tmp/omp-python-runner`; this was reported through the tool issue channel. The same verification was then successfully run through `python3 -c` in the shell. This was a tooling issue, not a repository/application failure.
- No permanent research scripts, downloaded datasets or implementation files were created during research. This handoff is the requested documentation artifact.
- No browser UI verification or application runtime/build verification was appropriate or performed: this was research plus repository creation, not a behavioral code change.
- Absence claims are bounded by the sources searched and endpoints exercised. Public accessibility does not automatically establish an open reuse license, freshness, complete geographic coverage or operational reliability.
