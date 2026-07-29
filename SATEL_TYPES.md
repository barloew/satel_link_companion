# Satel object types — reference

A reference of the Satel Integra **zone functions**, **wiring types** and **output functions**, with Dutch and English names, as used by Satel Link Companion. It is generated from the same table the integration itself uses (`custom_components/satel_link_companion/satel_functions.json`).

> **Sources.** SATEL INTEGRA Programming Manual EN v1.21 (integra_p_en 11/22) - official EN names; SATEL INTEGRA Programming Manual NL v1.18 (output functions 5.2, zone functions).

> **Polarity (POL.+)** and **wiring type** are DLOADX parameters that are *not* exposed over the integration protocol, so Satel Link Companion cannot read them back — it verifies polarity passively and asks you to set the wiring type to *Follow output*.

## Zone wiring types (aansluittypen)

The zone's electrical wiring type. For a **link**, the zone must use type **8 (Follow output)** — the zone then has no physical detector and simply follows the selected (possibly virtual) output.

| # | English | Nederlands | Notes |
|---|---|---|---|
| 0 | No detector | Geen detector |  |
| 1 | NC | NC |  |
| 2 | NO | NO |  |
| 3 | EOL | EOL |  |
| 4 | 2EOL/NC | 2EOL/NC |  |
| 5 | 2EOL/NO | 2EOL/NO |  |
| 6 | Roller | Rolluik |  |
| 7 | Vibration | Trilling |  |
| 8 | Follow output | Volg uitgang | **Required for a link.** The zone supports no detector; its status depends solely on the selected output. Physical violations and tampers of the zone are ignored. THE OUTPUT MAY BE VIRTUAL. |

## Zone functions (zonefuncties)

The zone's reaction type. For a Satel Link Companion **link**, use a **24-hour** function (marked ✅ below) so the zone can alarm at any time — the *when to alarm* gate lives in Home Assistant, not in the Satel partition. **88 (24H Burglary)** is the usual choice for motion / door / window zones; the 24-hour fire / gas / water functions suit hazard sensors.

| # | English | Nederlands | 24-hour | Group |
|---|---|---|---|---|
| 0 | Entry/Exit | In/Uit |  | delayed |
| 1 | Entry | Ingang |  | delayed |
| 2 | Delayed | Vertraagd |  | delayed |
| 3 | Interior Delayed | Volgzone |  | delayed |
| 4 | Perimeter | Omtrek |  | burglary |
| 5 | Instant | Inbraak |  | burglary |
| 6 | Exit | Uitgang |  | delayed |
| 7 | Day/Night | Dag/Nacht |  | burglary |
| 8 | Exterior | Extern |  | burglary |
| 9 | 24H Tamper | 24u Sabotage | ✅ | monitored_24h |
| 10 | 24H Vibration | 24u Tril | ✅ | monitored_24h |
| 11 | 24H Cash Machine | 24u Geldautomaat | ✅ | monitored_24h |
| 12 | Panic - Audible | Paniek alarm - luid | ✅ | monitored_24h |
| 13 | Panic - Silent | Overval alarm - stil | ✅ | monitored_24h |
| 14 | Medical - Button | Medisch alarm - knop | ✅ | monitored_24h |
| 15 | Personal Emergency | Persoonlijk medisch alarm | ✅ | monitored_24h |
| 16-31 | Counting C1...16 | Teller C1-C16 |  | counter |
| 32 | 24H Fire | 24u Brand | ✅ | monitored_24h |
| 33 | 24H Fire - Smoke | 24u Brand - Rook | ✅ | monitored_24h |
| 34 | 24H Fire - Combustion | 24u Brand - Verbranding | ✅ | monitored_24h |
| 35 | 24H Fire - Water Flow (Fire) | 24u Brand - Sprinkler | ✅ | monitored_24h |
| 36 | 24H Fire - Heat | 24u Brand - Hitte | ✅ | monitored_24h |
| 37 | 24H Fire - Pull Station | 24u Brand - Oven | ✅ | monitored_24h |
| 38 | 24H Fire - Duct | 24u Brand - Buis | ✅ | monitored_24h |
| 39 | 24H Fire - Flame | 24u Brand - Vlam | ✅ | monitored_24h |
| 40 | 24H Fire Supervisory | 24u Brand storing | ✅ | technical |
| 41 | 24H Low Water Pressure | 24u Lage waterdruk | ✅ | monitored_24h |
| 42 | 24H Low CO2 | 24u Lage CO2 | ✅ | monitored_24h |
| 43 | 24H Water Valve Detector | 24u Waterklep sensor | ✅ | monitored_24h |
| 44 | 24H Low Water Level | 24u Laag waterniveau | ✅ | monitored_24h |
| 45 | 24H Pump Activated | 24u Pomp geactiveerd | ✅ | monitored_24h |
| 46 | 24H Pump Failure | 24u Pomp storing | ✅ | monitored_24h |
| 47 | No Alarm Action | Geen alarm actie | ✅ | technical |
| 48 | 24H Auxiliary - Protection Loop | 24u Grond detectie | ✅ | monitored_24h |
| 49 | 24H Auxiliary - Gas Detector | 24u Gas detector | ✅ | monitored_24h |
| 50 | 24H Auxiliary - Refrigeration | 24u Koeling | ✅ | monitored_24h |
| 51 | 24H Auxiliary - Loss Of Heat | 24u Wegvallen warmte | ✅ | monitored_24h |
| 52 | 24H Auxiliary - Water Leakage | 24u Water lekkage | ✅ | monitored_24h |
| 53 | 24H Auxiliary - Foil Break | 24u Folie breuk | ✅ | monitored_24h |
| 54 | 24H Auxiliary - Low Bottled Gas Level | 24u Laag gasfles niveau | ✅ | monitored_24h |
| 55 | 24H Auxiliary - High Temperature | 24u Hoge temperatuur | ✅ | monitored_24h |
| 56 | 24H Auxiliary - Low Temperature | 24u Lage temperatuur | ✅ | monitored_24h |
| 57 | Technical - Door Open | Technisch - deur is geopend |  | technical |
| 58 | Technical - Door Button | Technisch - deur schakelaar |  | technical |
| 59 | Technical - AC Loss | Technisch - AC uitval |  | technical |
| 60 | Technical - Battery Low | Technisch - accu laag |  | technical |
| 61 | Technical - GSM Link Trouble | Technisch - GSM signaal storing |  | technical |
| 62 | Technical - Overload | Technisch - overbelasting |  | technical |
| 63 | Trouble | Storing (lokaal) |  | technical |
| 64-79 | Bypassing - Group 1-16 | Overbrug - groep 1-16 |  | control |
| 80 | Arming | Inschakelen |  | control |
| 81 | Disarming | Uitschakelen |  | control |
| 82 | Arm/Disarm | In/Uitschakelen |  | control |
| 83 | Clearing Alarm | Alarm herstellen |  | control |
| 84 | Guard | Bewaker |  | control |
| 85 | Entry/Exit - Conditional | In/Uit - conditioneel |  | delayed |
| 86 | Entry/Exit - Final | In/Uit - laatste |  | delayed |
| 87 | Exit - Final | Uitgang - laatste |  | delayed |
| 88 | 24H Burglary | 24u Inbraak | ✅ | monitored_24h |
| 89 | Finishing Exit Delay | Stop uitgangsvertraging |  | control |
| 90 | Disabling Verification | Stop verificatie |  | control |
| 91 | Detector Mask | Anti-mask | ✅ | monitored_24h |
| 92 | Outputs Group Off | Uitgangengroep uit |  | control |
| 93 | Outputs Group On | Uitgangengroep aan |  | control |
| 94 | Entry/Exit Interior | In/Uit mode 2/3 |  | delayed |
| 95 | Entry Interior | Ingang mode 2/3 |  | delayed |
| 96 | Fire Monitoring | Brand stil | ✅ | monitored_24h |
| 97 | Fire Panel Fault Monitoring | 24u Brand storing | ✅ | technical |

## Output functions (uitgangfuncties)

The output's function. Only **switchable** outputs can be driven from Home Assistant. For a **link** you need a **24 (MONO)** or **25 (BI)** switch; a **roller-shutter cover** uses the **105/106** pair; **remote switches (64–79, 98)** can be exposed as plain switches. Everything else is read-only status that the base integration surfaces as a `binary_sensor`.

| # | English | Nederlands | Home Assistant use | Group |
|---|---|---|---|---|
| 0 | Not Used | Niet in gebruik | read-only | unused |
| 1 | Burglary | Inbraak | read-only | alarm |
| 2 | Fire/Burglary | Brand / Inbraak | read-only | alarm |
| 3 | Fire Alarm | Brandalarm | read-only | alarm |
| 4 | Keypad Alarm | Bediendeel alarm | read-only | alarm |
| 5 | Fire (From Keypad) | Brand (van bediendeel) | read-only | alarm |
| 6 | Panic (From Keypad) | Paniek (van bediendeel) | read-only | alarm |
| 7 | Medical Alarm (From Keypad) | Medisch alarm (van bediendeel) | read-only | alarm |
| 8 | Tamper Alarm | Sabotage alarm | read-only | alarm |
| 9 | Day Alarm | Dag alarm | read-only | alarm |
| 10 | Duress Alarm | Overval alarm | read-only | alarm |
| 11 | Chime | Bel | read-only | signaling |
| 12 | Silent Alarm | Stil alarm | read-only | alarm |
| 13 | Technical Alarm | Technisch alarm | read-only | alarm |
| 14 | Zone Violation | Zone open | read-only | status |
| 15 | Video On Disarmed | Video aan bij uit | read-only | status |
| 16 | Video On Armed | Video aan bij in | read-only | status |
| 17 | Ready Status | Klaar status | read-only | status |
| 18 | Bypass Status | Overbrug status | read-only | status |
| 19 | Exit Delay Status | Uitgangsvertraging status | read-only | status |
| 20 | Entry Delay Status | Ingangsvertraging status | read-only | status |
| 21 | Armed Status | In status | read-only | status |
| 22 | Full Armed Status | Volledige in status | read-only | status |
| 23 | Arm/Disarm Beep | Inschakel/uitschakel geluiden | read-only | signaling |
| 24 | Mono Switch | Puls (MONO schakelaar) | Link + switch | switchable |
| 25 | Bi Switch | Maak/breek (BI schakelaar) | Link + switch | switchable |
| 26 | Timer | Schema | read-only | control |
| 27 | Trouble Status | Storingen | read-only | trouble |
| 28 | Ac Loss (Mainboard) | Geen AC (hoofdprint) - direct | read-only | trouble |
| 29 | Ac Loss (Technical Zone) | Geen AC (technische zone) | read-only | trouble |
| 30 | Ac Loss (Expansion Module) | Geen AC (uitbreidingsmodule) | read-only | trouble |
| 31 | Battery Trouble (Mainboard) | Accu storing (hoofdprint) | read-only | trouble |
| 32 | Battery Trouble (Technical Zone) | Accu storing (technische zone) | read-only | trouble |
| 33 | Battery Trouble (Expansion Module) | Accu storing (uitbreidingsmodule) | read-only | trouble |
| 34 | Detector Trouble | Detector storing | read-only | trouble |
| 35 | Telephone Line In Use Status | Telefoonlijn in gebruik status | read-only | status |
| 36 | Ground Start | Ground start | read-only | control |
| 37 | Reporting Acknowledgement | Meldkamer bevestiging | read-only | status |
| 38 | Service Mode Status | Service mode status | read-only | status |
| 39 | Test Vibration Detectors | Test trildetectoren | read-only | control |
| 40 | Cash Machine Bypass Status | Geldautomaat overbrug status | read-only | status |
| 41 | Power Supply | Voeding | read-only | power |
| 42 | Power Supply On Armed | Voeding bij in | read-only | power |
| 43 | Resetable Power Supply | Reset voeding | read-only | power |
| 44 | Fire Detectors Power Supply | Brand detectoren voeding | read-only | power |
| 45 | Partition Block Status | Blok geblokkeerd status | read-only | status |
| 46 | Outputs Logical And | Link EN | read-only | logical |
| 47 | Outputs Logical Or | Link OF | read-only | logical |
| 48-63 | Voice Message 0...15 | Spraakbericht 1-16 | read-only | control |
| 64-79 | Remote Switch 1...16 | Afstandsbediening 1-16 (REMOTE SWITCH) | Switch | switchable |
| 80 | No Guard Tour | Geen bewakingsronde | read-only | status |
| 81 | Ac Loss (Mainboard) - Long | Geen AC (hoofdprint) - lang | read-only | trouble |
| 82 | Ac Loss (Expansion Module) - Long | Geen AC (uitbreidingsmodule) - lang | read-only | trouble |
| 83 | Outputs Off | Uitgangen uit | read-only | status |
| 84 | Access Code Entering | Code gebruikt & * / # | read-only | status |
| 85 | Use Of Access Code | Code gebruikt & in/uit | read-only | status |
| 86 | Door Open Indicator | Deur is geopend | read-only | access_control |
| 87 | Door Too Long Opened Indicator | Deur is te lang open | read-only | access_control |
| 88 | Burglary Alarm (No Fire And Tamper) | Inbraakalarm (geen brand en sabotage) | read-only | alarm |
| 89 | Event Log 50% Full | 50% van logboek gevuld | read-only | status |
| 90 | Event Log 90% Full | 90% van logboek gevuld | read-only | status |
| 91 | Auto-Arm Delay Start | Start auto-in vertraging | read-only | status |
| 92 | Auto-Arm Delay Status | Auto-in vertraging status | read-only | status |
| 93 | Unauthorized Access | Ongeautoriseerde toegang | read-only | access_control |
| 94 | Alarm | Alarm - ongeautoriseerde toegang | read-only | alarm |
| 95 | Ip Reporting Trouble | IP rapportage storing | read-only | trouble |
| 96 | Telephone Line Trouble | Telefoonlijn storing (INTEGRA 128-WRL: GSM storingen) | read-only | trouble |
| 97 | Voice Message | Spraakbericht | read-only | control |
| 98 | Remote Switch | Afstandsbediening (REMOTE SWITCH) | Switch | switchable |
| 99 | Access Card Read | Kaart gelezen van | read-only | access_control |
| 100 | Card Hold | Kaart lang voorhouden | read-only | access_control |
| 101 | Card Read | Kaart lezen - uitbreiding | read-only | access_control |
| 102 | Link Trouble | Link storing - draadloze zone | read-only | trouble |
| 103 | Link Trouble | Link storing - draadloze uitgang | read-only | trouble |
| 104 | Wireless Device | Lage batterij - draadloos apparaat | read-only | trouble |
| 105 | Shutter Up | Rolluik op | Cover (up) | switchable |
| 106 | Shutter Down | Rolluik neer | Cover (down) | switchable |
| 107 | Card On Reader A | Kaart op lezer A | read-only | access_control |
| 108 | Card On Reader B | Kaart op lezer B | read-only | access_control |
| 109 | Zones Logical And | Zones link EN | read-only | logical |
| 110 | Alarm | Alarm - geen verificatie | read-only | alarm |
| 111 | Alarm | Alarm - geverifieerd | read-only | alarm |
| 112 | Verified | Geverifieerd - geen alarm | read-only | status |
| 113 | Verification Disabled Status | Verificatie uitgeschakeld status | read-only | status |
| 114 | Zone Test Status | Zone test status | read-only | status |
| 115 | Arming Type Status | In type status | read-only | status |
| 116 | Internal Siren | Sirene | read-only | alarm |
| 117 | Tampering Status | Sabotage status | read-only | status |
| 118 | Keyfob Battery Low | Lage batterij handzender | read-only | trouble |
| 119 | Wireless System Jamming | Storing draadloos systeem | read-only | trouble |
| 120 | Thermostat | Thermostaat | read-only | control |

## Arming modes (inschakelmodi)

The Satel arming mode for a partition. A master panel's **Home** uses the mode you set as `arm_home_mode` in the base integration; **Away** and **Night** map to the base arm services.

| # | English | Nederlands | Notes |
|---|---|---|---|
| 0 | Full arming | Volledig inschakelen |  |
| 1 | Full arming + bypasses | Volledig inschakelen + overbruggingen | zones met 'Overbrugd bij blijven' worden overbrugd |
| 2 | Arming without interior | Inschakelen zonder interieur | zones met functie 3 (Volgzone) worden NIET ingeschakeld; functie 8 (Extern) geeft stil alarm, overige luid |
| 3 | Arming without interior and without entry delay | Inschakelen zonder interieur en zonder ingangsvertraging | als 2, maar vertraagde zones reageren als inbraakzone |

