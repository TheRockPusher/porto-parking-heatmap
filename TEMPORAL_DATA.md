# Porto automobile parking: temporal-data access and unsent requests

**Research date:** 2026-09-25. Fresh HTTP checks below were performed anonymously against public pages and documented/catalog-linked infrastructure. Times ending in `Z` are retrieval times in UTC, not necessarily observation times. No emails or contact forms were sent, no accounts were created, and no authentication or access controls were bypassed. No temporal values from this investigation are included in the application.

## Decision

**No automobile dataset found in this investigation meets the combined requirements for current availability or a typical-week demand map: meaningful observations, usable timestamps/history, and verified reuse/collection rights.** This is a bounded finding, not a claim that the operators lack such data.

There are concrete public leads, including evidence beyond the earlier HANDOFF:

- The current urban-platform broker **does expose automobile `OffStreetParking` entities**. One Trindade entity has a real returned `dateObserved` and availability count, but its observation is from **2020-08-07**, not 2026. The other 19 garage entities contain inventory, not occupancy observations. The endpoint is accessible; a usable live feed is not established.
- Public automobile `OnStreetParking` entities also exist: 812 paid-street geometries, 669 loading/unloading geometries, and 75 taxi-rank entities. The paid streets contain no occupancy counts. Taxi ranks contain untimestamped count-like values and invalid/missing sentinels; they are not general-public car parking.
- SABA's official Ribeira and Cardosas HTML pages expose numbers labelled **“lugares livres”**. Their observation time, historical archive, and open reuse rights were not established. Their linked legal notice is not an open-data license. These are actionable partnership leads, not approved scraping integrations.
- Municipal/STCP announcements identify an operational roadside-panel occupancy system involving STCP, SABA and Porto Digital. They do not publish a verified public panel API or archive.

Keep the product labelled **parking supply/tariff information, not live occupancy/availability**. Do not extrapolate automobile demand from micromobility, taxi ranks, payment revenue, static capacity, or old example observations.

## Update 2026-09-29: the app's pressure index is not temporal data

The application now publishes an **estimated relative parking pressure index** on a 150 m hexagonal grid, for two periods (weekday daytime, overnight). It is derived entirely from **static open data**: INE Censos 2021 households, OpenStreetMap roads/POIs/car parks, and the PDM 2021 figure of 64,680 public on-street spaces distributed by road length. It ranks cells by *estimated demand versus estimated supply* within Porto.

- It contains **no observation with a timestamp**, no sessions and no garage counts. It does **not** satisfy the section 4 acceptance contract for temporal occupancy (no `observed_at`/session times, no 90-day history, no channel coverage, no dataset-specific reuse rights for observations) and **must not be presented as occupancy, availability, paid demand or a prediction**.
- Its two periods are modelling assumptions, not measured hours. A cell's index says how it compares with other cells, not how full it is at any time.
- ReportaPorto complaint counts and municipal restriction records are displayed for context only and do not enter the index. Complaints do not measure parking demand or illegal parking prevalence.
- The decision above stands: no feed met the section 4 gates, and this update adds none. If real temporal data is obtained, it should be evaluated against section 4 and shown as a separate, labelled layer; it should not be blended into the index without a documented method.
- Additional access routes identified on 2026-09-29 (EPorto concession monitoring platform, Porto Digital QuantumLeap history, LADA/CADA procedure) are recorded as addenda in section 5 and in the section 6 next actions. They are leads, not data in hand.

## 1. Current CKAN inventory and resources

### Scope actually checked

At **17:01:09Z**, [`package_list`](https://dadosabertos.cm-porto.pt/api/3/action/package_list) returned **HTTP 200**, `success: true`, and **69 packages**. Each package was then retrieved using `package_show?id=<name>`: **69/69 HTTP 200** between **17:01:56Z and 17:03:41Z**, containing **214 resource descriptors**. Titles, descriptions and resource metadata/URLs were reviewed for parking, occupancy, sessions and historical access. This was a catalog-metadata survey, **not a download of all 214 resources**.

The catalog exposes eight resources marked `resource_type: api`: air-quality type/entity queries, bus locations, noise type/entity queries, shared two-wheel parking, and weather type/entity queries. **The only parking API catalog resource is the two-wheel query below.** No catalog resource describing automobile payment-session history, hourly automobile occupancy, or a parking time-series API was identified. Catalog search alone was not used to establish absence; HANDOFF records its unreliable zero-result search behavior.

| Catalog package | Published resources and reference dates | Temporal/reuse interpretation |
| --- | --- | --- |
| [Municipal garages](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=parques-de-estacionamento-municipais) | GeoJSON, CSV: reference **2022-12-16**; DATEX II XML | `license_id: cc-zero`, `isopen: true`. Static inventory. XML publication time is not an occupancy observation. |
| [Paid streets](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=eixos-tarifados) | CSV, GeoJSON: **2022-12-20** | CC0; street geometry/regulation, not paid sessions. |
| [Western paid-space inventory](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=lugares-de-estacionamento-zonas-de-estacionamento-pago-zona-ocidental) | GeoJSON, CSV: **2022-12-15** | CC0; inventory/status is not occupied/free state. |
| [ZEDL](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=zonas-de-estacionamento-de-duracao-limitada-zedl) | CSV, GeoJSON: **2023-03-21** | CC0; tariff/regulatory geography, not observations. |
| [Resident zones](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=zonas-de-avencas-de-residentes) | GeoJSON, CSV: **2023-01-04** | CC0; permit geography, not resident presence or parking use. |
| [Reserved parking](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=parques-privativos) | CSV, GeoJSON: **2022-12-20**; DATEX II XML | CC0. **Metadata/content mismatch:** linked `estacionamento_rua.xml` describes priced street zones, not the reserved-space points; see below. |
| [Shared-mobility parking](https://dadosabertos.cm-porto.pt/api/3/action/package_show?id=urban-platform-sharing-spots-location) | One NGSI API; reference **2022-07-16**, declared daily frequency | CC0 applies to the catalogued **bicycle/scooter** dataset. It does not establish a blanket license for every automobile entity on the same broker. |

Parking-related planning, motorcycle and soft-mobility inventories were also present. Neither their titles nor their resource descriptions establish automobile occupancy. All parking-related packages in the table had `datastore_active: false` on their resources. September 2026 CKAN migration/modification timestamps do not establish that underlying reference data is current.

### Actual DATEX II downloads

Both downloads returned **HTTP 200** at **17:03:54–55Z**:

1. [Municipal garage XML](https://dadosabertos.cm-porto.pt/dataset/5ea79d81-9e19-11f1-84ed-6abdb6d5cf34/resource/0a80df53-72a4-475b-914d-bd664872e4f9/download/parques_municipais.xml): DATEX II v3 `par:ParkingTablePublication`, **19 `par:parkingRecord` elements**, publication time `2026-09-04T11:00:00.072396`. Schema includes record IDs, `parkingNumberOfSpaces`, `parkingOccupancyDetectionType`, location, assigned vehicle types and opening times. The detection value `manual` is not an occupancy measurement. No occupancy/status publication or occupied/free observation series was found.
2. [XML linked from reserved-parking package](https://dadosabertos.cm-porto.pt/dataset/5ee2d191-9e19-11f1-84ed-6abdb6d5cf34/resource/e9f2719b-c359-4d2b-b8d7-bd2b69894ad5/download/estacionamento_rua.xml): `par:ParkingTablePublication`, **812 records**, table name **“Zonas de Estacionamento Tarifado”**, publication time `2026-09-04T10:55:00.611622`. IDs use `urn:ngsi-ld:OnStreetParking:porto:ParkingZones:cmp:…`; fields include line geometry, vehicle eligibility, permits and zone, not occupancy. The package placement is misleading; the XML's actual content is decisive.

Neither XML publication timestamp includes an explicit UTC offset. Do not assign `Europe/Lisbon` or `UTC` to those timestamps without provider confirmation, and do not substitute them for observation timestamps.

## 2. Actual public urban-platform automobile responses

The host was taken from the municipal catalog's public NGSI resource. Only anonymous GET requests were used; no private tenant/service headers, credentials, guessed historical hosts, subscriptions or write operations were attempted.

| Requested URL | Fresh result | What it establishes |
| --- | --- | --- |
| [OffStreetParking, limit 1000, count](https://broker.fiware.urbanplatform.portodigital.pt/v2/entities?type=OffStreetParking&limit=1000&options=count) | **200**, 17:01:10Z; JSON array **20**; `Fiware-Total-Count: 20` | A publicly reachable automobile-eligible garage endpoint. Only one returned entity has `availableSpotNumber` and `dateObserved`. |
| [OnStreetParking, first page](https://broker.fiware.urbanplatform.portodigital.pt/v2/entities?type=OnStreetParking&limit=1000&options=count) | **200**, 17:01:10Z; **1,000** rows; `Fiware-Total-Count: 1786` | First page only; stopping here would miss entities. |
| [OnStreetParking, offset 1000](https://broker.fiware.urbanplatform.portodigital.pt/v2/entities?type=OnStreetParking&limit=1000&offset=1000&options=count) | **200**, 17:01:56Z; **786** rows; same total header | Combined pages contain **1,786 unique IDs**. This is a short multi-request snapshot, not an atomic transaction/history export. |
| [Public type inventory](https://broker.fiware.urbanplatform.portodigital.pt/v2/types?limit=1000&options=count) | **200**, 17:01:41Z; **18 types** | Type descriptors include OffStreetParking count 20 and OnStreetParking count 1,786. Type/attribute presence is not proof of freshness. |

### OffStreetParking: stale observation versus static inventory

The only entity with an observation timestamp was returned with these exact relevant values (reduced to attribute values for readability):

```json
{
  "id": "urn:ngsi-ld:OffStreetParking:portoparking:CMP:Trindade_1_Rotacao",
  "type": "OffStreetParking",
  "name": "Trindade Parking",
  "allowedVehicleType": ["anyVehicle"],
  "availableSpotNumber": 218,
  "totalSpotNumber": 346,
  "dateObserved": "2020-08-07T10:56:12.699467Z",
  "occupancyDetectionType": ["singleSpaceDetection"]
}
```

The actual response uses NGSI-v2 attribute objects `{type, value, metadata}`; `dateObserved` is typed `Text`, and the returned metadata objects are empty. This is **evidence of one timestamped value exposed by the broker**, not proof of its original measurement quality or a historical series. **It is excluded from the app because it is stale and no verified license for this observation was found.** A fresh HTTP response cannot make a six-year-old observation current.

The remaining **19 entities** explicitly allow cars, alongside other vehicle categories. Their schemas include `id`, `location`, `name`, `allowedVehicleType`, `category`, `source`, `openingHours`, `occupancyDetectionType` and `status`; 14 of those 19 have `totalSpotNumber`. They have **no returned `dateObserved`, `availableSpotNumber` or `occupiedSpotNumber`**. Their `source` points to municipal geographic inventory. A static `status: ["open"]` without an observation time is not a real-time closure guarantee.

Capacity also requires reconciliation: the stale Trindade entity says 346, the garage inventory/XML uses a different total, and the [current STCP Trindade page](https://www.stcpservicos.pt/estacionamento/parque-de-estacionamento-da-trindade) states **345 total places**. The application’s light-vehicle category is not automatically the denominator for any of these measurements.

### OnStreetParking: all returned groups

| Group | Count | Actual observation fields | Integration decision |
| --- | ---: | --- | --- |
| `category: ["shortTerm","mediumTerm","feeCharged"]`, `allowedVehicleType: ["anyVehicle"]` | **812** | No `availableSpotNumber`, `occupiedSpotNumber`, `totalSpotNumber` or date/time attribute | Paid-street geography only; cannot calculate occupancy. |
| `category: ["forLoadUnload","free","shortTerm"]`, `allowedVehicleType: ["anyVehicle"]` | **669** | No availability, occupancy, capacity or date/time attribute | Loading/unloading regulation, not car-parking demand. |
| `allowedVehicleType: "car"`, TaxiDigital taxi ranks | **75** | `totalSpotNumber`; occupied/free counts encoded as **Text**; **no date/time attribute** | Taxi-only use, not general-public spaces. 74 use `category: ["taxiStop"]`, one `"taxiSpot"`. |
| `allowedVehicleType: ["twoWheeledVehicle"]` | **230** | Count fields and `vehicle_ids`; **no date/time attribute** | Bicycle/scooter parking. Explicitly excluded from automobile analysis. |

None of the 1,786 returned entities had a date/time attribute, and all returned attribute metadata objects were empty. This statement concerns the actual default responses, not every possible server-side system attribute or private database.

Concrete taxi examples: `urn:ngsi-ld:OnStreetParking:porto:taxirank:56` returned available `"11"`, occupied `"1"`, total `12`; `…:taxirank:23` returned available `"None"`, occupied `"-1"`, total `4`. Across the taxi snapshot, 11 had available `"None"`, including ten with occupied `"-1"`. Missing/negative sentinels must not become zero, and these untimestamped values must not be labelled live. No license specifically authorizing reuse of TaxiDigital counts was identified.

### History and rights boundary

The inspected `/v2/entities` responses are entity snapshots, not time-series archives. No public automobile historical API was linked from the 69 catalog records or the inspected official parking/platform sources. The [Porto Digital platform brochure](https://portodigital.pt/documents/d/guest/porto-urban-platform_brochura_small-1) describes historical storage and API architecture, but its examples include environmental monitoring, traffic and soft mobility; it does not establish public automobile parking-history access, retention or a parking-data license.

A generic Smart Data Models specification, an architectural “historical” box, a public HTTP 200, or the CC0 license of the two-wheel catalog entry does **not** license an unrelated automobile feed. This investigation found no documented automobile history endpoint to exercise; it did not attempt to discover private hosts by brute force. Ask Porto Digital/municipal open data for the supported endpoint and dataset-specific authorization.

## 3. STCP/SABA panel and public-page leads

### Municipal panel system

The [STCP announcement](https://www.stcpservicos.pt/comunicacao/noticia/paineis-de-mensagem-variavel-mostram-ocupacao-dos-parques-de-estacionamento) returned **HTTP 200 at 17:03:42Z**. Its [municipal source](https://www.porto.pt/pt/noticia/paineis-de-mensagem-variavel-mostram-ocupacao-dos-parques-de-estacionamento) has publication metadata **2023-01-27**. It describes real-time occupancy information for **Alfândega, Casa da Música, Cardosas, Duque de Loulé, Palácio da Justiça, Praça de Lisboa (including Carlos Alberto/Praça dos Leões), Trindade and Ribeira**. Partners are the municipality, STCP Serviços and SABA, with communications supplied by Porto Digital under Cooperative-Streets.

The article proves that a panel integration was announced. It does **not** verify continued operation of every panel today, publish a current feed contract/URL, expose history, or grant reuse rights. Ask for the existing authorized panel upstream rather than inventing a new API or copying panel images.

The [Trindade facility page](https://www.stcpservicos.pt/estacionamento/parque-de-estacionamento-da-trindade), **HTTP 200 at 17:03:42Z**, publishes address, 24-hour opening, 345 total places, payment/season-ticket information and `parques@stcpservicos.pt`. It links a WhatsApp channel for operational notices, not a machine-readable timestamped occupancy/closure feed. No live vacancy count was found on this page.

### SABA publicly displayed automobile counts

Anonymous GETs of official pages returned **HTTP 200 at 17:03:42Z**:

| Official page | Exact HTML content observed | Missing contract |
| --- | --- | --- |
| [SABA Ribeira](https://www.saba.pt/pt/estacionamento-porto/parque-de-estacionamento-saba-ribeira) | Car icon (`icon-saba_CAR`) followed by **`89 lugares livres`**; Rua do Infante Dom Henrique; “Aberto 24 horas” | No associated observation timestamp, refresh guarantee, archival interface or integration license established. |
| [SABA Cardosas](https://www.saba.pt/pt/estacionamento-porto/parque-de-estacionamento-saba-cardosas) | **`94 lugares livres`** | Same limitations. |

These are **retrieved display values, not a claim of present-day availability to a driver**. The reader’s simplified extraction omitted the counts; original HTML was inspected. “Última vista / Faz 0h” in the page is not established as the measurement time and must not be used as such. HTTP retrieval time is only collection provenance. Indexed search snippets showed other numbers and were not treated as observation evidence.

The [SABA legal page](https://www.saba.pt/pt/aviso-legal) links the [legal notice dated 2020-06-26](https://www.saba.pt/documents/32346/773628/AVISO+LEGAL_26.06.2020.pdf/065da766-7656-cd1c-1b58-072423343090?t=1630578685177), retrieved **HTTP 200 at 17:04:02Z**. Clause **2(c)** restricts reproduction, copying, distribution and public communication except with rights-holder authorization or where legally permitted; clause **7** reserves intellectual-property rights and requires express written authorization for the uses it describes. Clause **4** disclaims continuity/availability guarantees. This is **not an open license**. No automated collection or republication permission was obtained. The document identifies `geral@sabagroup.com` as a general contact, usable for an authorized-feed referral if STCP/municipality cannot cover SABA rights.

No SABA login, purchase flow, JSF form submission or protected API was used. Publicly seeing a number is distinct from having permission and a stable, timestamped feed suitable for integration.

### Existing historical/request leads, not newly measured here

HANDOFF's 2026-09-24 research records coarse figures in the [STCP 2023 annual report](https://www.stcpservicos.pt/storage/app/media/Documentos%20Gerais/relatorio-stcpcompressed-1.pdf), including annual garage occupancy and street payment-channel revenue shares. Those are not hourly histories; revenue shares are not session shares. The [municipal code](https://mobilidade.cm-porto.pt/files/uploads/cms/CRMP_vers%C3%A3o_atualizada_20251127.pdf), article D-3/58.º as identified in HANDOFF, provides a route to request operators’ submitted occupancy statistics. Neither source was re-audited in this fresh pass. Monthly/annual statistics may inform context but cannot support 168 block-hour profiles, and open reuse rights must still be clarified.

## 4. Acceptance contract before adding temporal data

A response is integration-ready only when these conditions are evidenced by a sample export/API response, dictionary and written terms. These are project acceptance requirements, **not claims about existing provider guarantees**.

1. **Scope and identity:** stable meter, street-segment, zone and/or garage IDs; authoritative WGS84 geometry or a documented CRS; a versioned crosswalk to municipal geography with `valid_from`/`valid_to`; explicit Porto-municipality and operator coverage. Names alone are not join keys. Taxi, motorcycle, delivery and bicycle/scooter spaces must be distinguishable from general automobile spaces.
2. **Time semantics:** actual `observed_at` for counts or `started_at`/`ended_at` (or paid duration) for sessions; distinguish observation, ingestion, publication and correction times. Use ISO 8601 with UTC offset or UTC plus a documented conversion to **`Europe/Lisbon`**, including DST repeated/missing hours. Define aggregation interval boundaries, units and whether sessions represent paid entitlement or physical presence.
3. **Capacity and closures:** effective available capacity for the same vehicle/user category as the numerator, with temporal validity; resident/season-ticket, reserved, accessible, EV and temporarily unavailable places documented without double counting. Provide complete/partial closure periods, meter outages, enforcement hours, holidays and changes. A closed or unknown site is not an empty one.
4. **Channel and event coverage:** enumerate cash/card meters, every app/payment provider, subscriptions/season tickets and exemptions, with date/geography coverage and omissions. Define cancellations, refunds, extensions, duplicated/overlapping records, corrections and reconciliation across channels. Prefer provider-side anonymous hourly aggregates if session linkage would expose individuals. Paid demand remains labelled **paid demand**, not measured physical occupancy.
5. **Historical completeness:** at least **90 consecutive days** for a typical-week profile, with hourly or finer temporal resolution, start/end dates, expected-versus-delivered records by site/channel/day, and explicit gaps, outages, suppression and revisions. Zero, missing and closed must be separate states. Each displayed weekday/hour profile must retain its sample count and coverage; do not silently fill missing periods. Monthly/annual summaries or one stale snapshot fail this requirement.
6. **Garage observations/live collection:** stable facility ID, `observed_at`, occupied/free counts, compatible effective capacity and quality/closure state. Explain whether free capacity excludes reservations or season-ticket allocations and how sensors/barriers are reconciled. Provide existing history or express authorization to collect and retain future snapshots. Agree a numeric refresh interval and maximum age before enabling any “live” label; show source age and suppress availability beyond that threshold. Future collection alone does not supply the initial 90-day history.
7. **Rights and operating contract:** a dataset-specific open license or written permission covering automated collection, storage, historical retention, analysis, derived-map publication and any redistribution; attribution and third-party/operator limits; supported URL/schema/version, authentication if authorized, pagination, rate limits, refresh cadence, retention horizon and deletion obligations. A publicly reachable broker or web page is insufficient. Include a data owner/contact and the stated completeness/freshness commitment.
8. **Privacy:** no number plates (including hashed plates), customer/account/device IDs, payment credentials, bank/card details or movement traces. Minimize source fields; agree aggregation/suppression for small cells. If provider-side de-duplication needs identifiers, do it at the provider and deliver only anonymous aggregates or non-linkable records. Publish no small-cell data contrary to the agreed privacy rules.

**Promotion decision:** static inventory stays in the present app. A licensed but incomplete export may be described with its actual limited scope; it must not silently become a citywide or typical-week occupancy claim. An authorized fresh garage feed would enable only the covered garages, not street availability. No response yet satisfies these gates.

## 5. Ready-to-send Portuguese drafts — NOT SENT

The drafts intentionally contain no invented person, institution, funding claim or sender identity. The real sender can append their normal signature. Recipients were rechecked on official public pages: [municipal open-data FAQ](https://dadosabertos.cm-porto.pt/faqs), [street-payment/operator information](https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/pagamento-das-taxas-e-informacoes), and [STCP Trindade](https://www.stcpservicos.pt/estacionamento/parque-de-estacionamento-da-trindade). The street page's original HTML confirms both EPorto and STCP addresses; a reader-generated `.md` variant returned an error and was not used as evidence.

### Draft A — Município / EPorto: street sessions and citywide coordination

**Para:** dados@cm-porto.pt  
**Cc:** eporto@eporto.pt; estacionamento@stcpservicos.pt  
**Assunto:** Pedido de dados anonimizados de estacionamento na via pública — histórico, cobertura e condições de reutilização

Exmos. Senhores,

Estou a desenvolver um mapa de informação de estacionamento no Município do Porto, com base nos dados geográficos públicos. Pretendo avaliar se é possível acrescentar indicadores temporais de procura paga, sem os apresentar indevidamente como ocupação física ou disponibilidade em tempo real.

O catálogo público disponibiliza eixos tarifados, zonas e lugares, mas não identifiquei um histórico público de sessões de estacionamento automóvel. Agradeço a indicação do serviço responsável e a possibilidade de disponibilização dos seguintes elementos, ou o encaminhamento deste pedido para as entidades competentes:

1. **Histórico de pelo menos 90 dias consecutivos:** sessões pagas anonimizadas, com início e fim ou duração paga e identificador estável do parquímetro, troço/arruamento e zona. Como alternativa preferencial quando necessário à proteção de dados, agregados horários por troço ou zona, com número de sessões e minutos de estacionamento pago, definição das métricas e intervalos. Solicito as datas de início/fim do histórico e um mapa das lacunas, falhas, supressões e revisões; ausência de registo não deverá ser confundida com procura zero.
2. **Correspondência geográfica e oferta:** tabela dos identificadores para geometria/coordenadas e zonas oficiais, capacidade efetivamente utilizável por categoria, horários de cobrança/fiscalização, exceções, encerramentos e alterações ao longo do tempo. Solicito datas de vigência dos identificadores, capacidades e regras, bem como confirmação do fuso horário e do tratamento da mudança de hora em Europe/Lisbon.
3. **Cobertura e semântica:** canais incluídos e excluídos — numerário/cartão nos parquímetros, aplicações e restantes meios — por entidade, área e período. Solicito o tratamento de cancelamentos, reembolsos, prolongamentos, duplicados e sobreposições, assim como as limitações relativas a residentes, avenças e isenções. Não é necessário nem pretendido identificar utilizadores para deduplicar os dados; essa operação poderá ser efetuada na origem.
4. **Ligação aos dados de parques:** caso o Município ou os parceiros disponham das observações que alimentam os painéis de ocupação anunciados com STCP Serviços, SABA e Porto Digital, solicito indicação do responsável por acesso autorizado a contagens de ocupados/livres com data/hora da observação, identificadores de parque, capacidade, encerramentos e histórico. Na ausência de arquivo, agradeço informação sobre acesso continuado e autorização expressa de recolha e retenção de observações futuras.
5. **Licença e funcionamento:** licença de reutilização ou autorização escrita para recolha automática, conservação, análise e publicação de mapas/indicadores derivados; obrigações de atribuição e limites de redistribuição; formato/API e documentação, limites de pedidos, frequência de atualização, retenção disponível e garantias ou limitações de completude e atualidade. Agradeço uma pequena amostra anonimizada e o dicionário de dados para verificar a integração.

Não solicito matrículas, nem mesmo cifradas ou pseudonimizadas, identificadores de cliente/conta/dispositivo, dados bancários, credenciais de pagamento ou trajetos individuais. São suficientes agregados anónimos; aceito regras de agregação ou supressão de células pequenas que preservem a privacidade, desde que documentadas.

Para a integração, preciso de identificadores geográficos estáveis, datas/horas com fuso explícito, capacidade e encerramentos com vigência, cobertura de canais e lacunas históricas conhecidas, e direitos de recolha/reutilização claros. As sessões pagas serão distinguidas de ocupação medida; dados parciais não serão apresentados como cobertura integral da cidade.

Agradeço que indiquem se estes elementos já estão publicados, se podem ser facultados por exportação ou API, ou qual a entidade e o procedimento adequado para obter acesso autorizado.

Com os melhores cumprimentos.

### Draft B — STCP Serviços: garage observations and panel upstream

**Para:** parques@stcpservicos.pt  
**Cc:** dados@cm-porto.pt  
**Assunto:** Pedido de acesso autorizado a dados de ocupação dos parques — histórico e sistema de painéis

Exmos. Senhores,

Estou a desenvolver um mapa de informação de estacionamento no Município do Porto e pretendo avaliar uma integração de disponibilidade dos parques baseada em dados autorizados, atuais e corretamente identificados.

A notícia sobre os painéis de mensagem variável refere a integração da ocupação de parques da STCP Serviços e da SABA, com suporte de comunicações da Porto Digital. Solicito informação sobre o serviço responsável pelo fornecimento desses dados e sobre as condições para acesso e reutilização. Em particular:

1. **Observações e histórico dos parques:** contagens de lugares ocupados e/ou livres, identificador estável do parque, data/hora efetiva da observação, capacidade aplicável, estado de qualidade e encerramentos totais/parciais. Pretendo, se disponível, pelo menos 90 dias consecutivos de histórico, com resolução horária ou mais fina, datas de cobertura, lacunas, falhas e correções documentadas. Se não existir histórico disponibilizável, solicito acesso autorizado ao fluxo atual e permissão expressa para recolher e conservar observações futuras; isso será distinguido de um arquivo já existente.
2. **Geografia, capacidade e horários:** correspondência entre identificadores, coordenadas/geometria e nomes dos parques, categorias de lugares e datas de vigência; horários de funcionamento e restrições, obras/encerramentos e alterações de lotação. Solicito confirmação de qual a capacidade que serve de denominador às contagens e de como são tratados lugares reservados, avenças, mobilidade condicionada, carregamento elétrico e reservas. As datas/horas deverão ter fuso explícito, com regras de Europe/Lisbon e mudança de hora documentadas.
3. **Cobertura de utilização e canais:** parques/operadores abrangidos pelo sistema e períodos de funcionamento; método de medição e tratamento de rotação, avenças, pré-pagos, reservas e Via Verde/outros meios. Solicito a distinção entre capacidade livre medida e disponibilidade comercial para reserva, e as regras aplicáveis a cancelamentos, prolongamentos, sobreposições, duplicados e correções. Não pretendo inferir ocupação física a partir de pagamentos sem essa validação.
4. **Sessões na via pública, se também disponíveis na STCP Serviços:** solicito encaminhamento para estacionamento@stcpservicos.pt de um pedido de pelo menos 90 dias de sessões pagas anonimizadas, com início/fim ou duração paga e IDs estáveis de parquímetro/troço/zona; em alternativa, agregados horários de procura paga por troço/zona. Seriam necessários o mapeamento geográfico, capacidade e horários com alterações históricas, cobertura de todos os canais e regras de cancelamento/prolongamento/sobreposição. Não se pretende misturar este universo com as observações dos parques.
5. **Autorização, licença e condições técnicas:** licença ou autorização escrita que permita recolha automática, retenção de histórico, análise e publicação de informação/indicadores derivados, indicando atribuição e limites de redistribuição. Solicito o endpoint/formato suportado, documentação e pequena amostra, autenticação autorizada se necessária, limites de pedidos, cadência, idade máxima esperada da observação, retenção e garantias/limitações de completude e atualidade. Se os direitos dos parques SABA ou de outros parceiros tiverem de ser autorizados separadamente, agradeço o encaminhamento para o respetivo responsável.

Não solicito matrículas, incluindo hashes, dados de clientes, identificadores pessoais ou de dispositivos, credenciais ou detalhes de pagamento. As contagens por parque e instante e os agregados anónimos de procura são suficientes; aceito a supressão documentada de células pequenas por razões de privacidade.

A integração só apresentará disponibilidade como atual quando existir uma data/hora de observação válida e dentro do limite de atualidade acordado. Capacidade, encerramento e ausência de dados serão estados distintos. Não serão usados valores antigos como disponibilidade presente, nem dados de parques como estimativa de estacionamento na rua.

Agradeço a indicação do interlocutor técnico e das condições para obter estes elementos, incluindo eventual acesso ao fluxo já utilizado pelos painéis, em vez de recolha automática das páginas públicas.

Com os melhores cumprimentos.

### Addenda (2026-09-29) — NOT SENT

These additions leave Drafts A and B unchanged. They can be appended to the matching draft or sent as separate requests. Like the drafts, they contain no invented sender identity.

**Addendum A1 — EPorto: monitoring-platform history (append to Draft A).**  
Source: the concession tender file <https://mobilidade.cm-porto.pt/files/uploads/cms/1614600090-HTRAU2FobH.pdf> (procedure CLPQI/1/2014/DMC) quotes Art. 7.º, n.º 2 of Anexo II (Código de Exploração): the concessionaire maintains a meter-centralisation system and an internet platform giving the municipality real-time access to, at minimum, data including “receita momentânea” (b) and “taxa ou índice de ocupação financeira” (g). **Caveat:** the wording appears inside a bidder's clarification request from the 2014 procedure. The final contract text, whether the two requirements were dispensed, whether the current platform provides these items, and whether it retains history are **not verified**.

> Adicionalmente, o artigo 7.º, n.º 2 do Anexo II (Código de Exploração) da concessão de estacionamento pago na via pública prevê uma plataforma de monitorização acessível ao Município. Solicito informação sobre os dados que essa plataforma efetivamente disponibiliza (incluindo receita e taxa ou índice de ocupação financeira), o seu nível de agregação (parquímetro, troço, zona; intervalo horário ou outro), o histórico conservado e respetivas datas de início/fim, e se é possível facultar uma exportação anonimizada e agregada desse histórico, com dicionário de dados e as condições de reutilização. Solicito ainda a indicação da entidade responsável por essa plataforma e do contrato ou aditamento vigente.

**Addendum C — Porto Digital / Município: QuantumLeap history export.**  
**Para:** dados@cm-porto.pt (the recipient at Porto Digital is not verified here; the sender should ask the municipal open-data team to forward the request or identify the contact).  
**Evidence:** the public broker `https://broker.fiware.urbanplatform.portodigital.pt/v2/subscriptions` lists a subscription with id starting `63ac28ec`, described “OffStreetParking for QuantumLeap prod”, with 93,872 notifications, last on 2026-04-01. [INFERENCE] This indicates a QuantumLeap time-series store fed with garage entities; its content, retention, access route and rights are unknown, and only the anonymous subscription listing was read.  
**Assunto:** Pedido de exportação do histórico de estacionamento em parques (QuantumLeap) e condições de reutilização

> Exmos. Senhores,
>
> A lista pública de subscrições da plataforma urbana (`/v2/subscriptions`) mostra uma subscrição “OffStreetParking for QuantumLeap prod”, com 93 872 notificações, a última em 2026-04-01. Pergunto se existe um histórico de entidades `OffStreetParking` armazenado, e solicito, se possível, uma exportação do mesmo, com: identificador estável do parque, data/hora da observação e da ingestão com fuso explícito, contagens de lugares ocupados/livres, capacidade aplicável, estado de qualidade ou encerramento, e datas de início/fim com lacunas conhecidas. Solicito também a indicação da origem das observações (parque e operador), o dicionário de dados, a política de retenção e a licença ou autorização escrita para análise e publicação de indicadores derivados. Não são necessários dados pessoais. Se a exportação não for possível, agradeço a indicação da entidade competente ou o procedimento adequado, incluindo pedido formal ao abrigo da Lei n.º 26/2016.
>
> Com os melhores cumprimentos.

**Playbook — formal access and reuse requests under Lei 26/2016 (LADA).** Use when an informal request (Drafts A, B, C) is unanswered, refused or partly answered. Deadlines below are as summarised in the 2026-09-29 investigation; the sender should confirm the current statute text before relying on them.

1. **Access request.** Send a written request to each entity (municipality, EPorto, STCP Serviços) naming the documents/data wanted (for example the monitoring-platform export or occupancy statistics that operators must report under the municipal code article D-3/58.º), stating that no personal data is requested, and quoting Lei 26/2016.
2. **Reply time.** The entity should reply within **10 days**. The period can be extended by up to **2 months**; expect a notice explaining the extension.
3. **Escalation.** If the request is ignored, refused or only partly met, a complaint to **CADA** (Comissão de Acesso aos Documentos Administrativos) can be filed within **20 days**; confirm in the statute from which event that period runs. Keep the request, the acknowledgement and any reply.
4. **Reuse is separate from access.** Obtaining a document does not license republication of derived maps. Request a **reuse licence** under **arts. 21–23** of Lei 26/2016, specifying purpose (analysis and publication of aggregated indicators), attribution and any conditions.
5. **Record.** Log dates sent/received, references, entity and outcome in the repository; do not commit personal data or third-party documents without a licence.

Timing lead: the **PMUS public consultation** runs until **2026-11-04**; a comment asking for publication of parking-demand and occupancy data would be on the public record.

## 6. Bounded outcome and handoff

- **Observed and accessible:** 69-package CKAN catalog; two static parking DATEX publications; public broker garage/street entities; STCP panel announcement; two SABA pages with automobile free-space displays.
- **Timestamped automobile observation found:** exactly one in the inspected broker garage snapshot, dated **2020-08-07**. Its historical authenticity/completeness and reuse rights remain unverified; it fails current-availability and profile requirements.
- **Not established:** usable hourly/daily automobile history, current citywide street sessions, an authorized/licensed current automobile observation stream, documented panel feed endpoint, observation freshness of SABA/taxi displays, or collection/retention rights for those displays.
- **Rights established only for the relevant catalogued open-data resources:** CC0 inventory and the explicitly two-wheel sharing dataset. Do not extend those rights to other feeds by hostname or schema similarity.
- **Next access action:** the real sender can send Draft A and Draft B and evaluate the response against section 4. Neither draft has been sent. SABA general contact is available for a rights/referral request, but no separate message was sent or invented. Added 2026-09-29 (also unsent): Addendum A1 (EPorto monitoring-platform history), Addendum C (QuantumLeap export) and the Lei 26/2016 playbook; the 2025 STCP Serviços report (2,974 street spaces, 652,210 street transactions) gives annual totals only and cannot meet section 4.

Verification here consisted of the actual public GET responses, response schemas/counts, full street-entity pagination, source-page HTML and the linked SABA legal PDF. No application builds, tests, lint, formatting or ingestion were run for this research deliverable. The findings do not cover private feeds, contractual datasets, every operator in Porto, every possible broker tenant, or unlinked historical services.
