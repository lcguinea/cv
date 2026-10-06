# CV_MASTER.md · Luis Guinea

> Single source of truth for every CV, portfolio page and application.
> The website, the printable CV and any tailored version are built FROM this file.
> Nothing may appear on the site that is not here. Anything marked `TODO` or `VERIFY` must not be published until resolved.
> Design and voice rules live in BRAND.md. This file only holds content.

---

## How to use this file

Each entry has:

- **facets**: one or more of `music`, `data`, `business`, `creative`, `projects`, `writing` (BRAND.md section 6, plus `writing` for research and journalism).
- **visibility**: `web` (index.html), `print` (cv.html / PDF), `private` (never published; kept for tailored applications only).
- **status**: `verified` (confirmed by Luis), `VERIFY` (claim exists in older CVs but needs confirmation before publishing), `TODO` (missing information).

Rules for any agent using this file:

1. Do not invent, round up or combine metrics.
2. Do not publish `private` fields.
3. Do not publish anything with status `VERIFY` or `TODO`; render a clearly marked placeholder instead, or omit it.
4. Proper names, article titles and project names are never translated.
5. No em dashes in published copy.

---

## 1. Identity

| Field | Value | Visibility |
|---|---|---|
| Display name | LUIS GUINEA | web, print |
| Full name | Luis Carlos Guinea Moctezuma | web, print |
| Descriptor | Creative × Analytical × Entrepreneurial | web |
| Base | Valencia, Spain | web, print |
| Background | Mexican and Spanish | web (optional) |
| Email | lguinea@berklee.edu | web, print |
| Phone | +34 629 85 84 91 | print only |
| Medium | https://medium.com/@soyluisguinea | web, print |
| LinkedIn | TODO | web, print |
| Spotify / artist links | TODO | web |
| Photo | `profile_pic.png` is Luis's real profile photo used on social media; publication authorised. `cover.png` is a real photograph of Jazztone Studios taken by Luis; publication authorised. Check both against BRAND.md section 13 before use; optimise derivatives (WebP/AVIF, under 300 KB) without overwriting originals. | web |

---

## 2. Profile

### Long (web, EN)

I work where creative and analytical thinking meet. For 10+ years I have been inside the music business as a label founder, A&R and producer; in parallel I build data systems and automations that turn messy information into decisions. Lately I write about how artists actually grow, using data to test the stories the music industry tells itself. I work in English and Spanish, from Valencia.

### Short (print, EN)

Music producer, A&R and technology and automation developer with 10+ years in the Latin music industry. I combine production and artist development with Python, SQL and Chartmetric analysis, and publish data-driven music research in English and Spanish.

### Tailored one-liners (for applications, not the site)

- **Journalism:** I write about how artists actually grow, using data to test what the industry assumes.
- **A&R:** I hear songs as a producer and read the numbers as an analyst.
- **Data:** I turn operational and streaming data into automated reporting and clear decisions.
- **Teaching:** Berklee graduate, pianist since childhood, with classroom experience in piano and music production.

Spanish versions: translate naturally when building the ES site. Do not translate literally.

---

## 3. Key metrics (for visual callouts)

Only use these. Each one must stay attached to its context.

| Metric | Context | Status |
|---|---|---|
| 50+ artists | Launched and marketed through Moctezuma Music Group, Mexican market, 2015–2023 | verified |
| 10M+ streams | Total across Moctezuma Music Group artists | verified |
| 20 releases | Overseen as A&R Manager at Tipazo Music Group, with Sony Music's A&R team | verified |
| 10+ years | In the music industry (2015 to present) | verified |
| 5 published studies | Data-driven music research on Medium, EN / ES | verified |
| 18 months | Longest tracking study (AI-generated catalogue) | verified |
| 19 artists | Cohort in the artist growth study | verified |
| 11-piece ensemble | Directed as Music Director, Mandala Love Music | verified |
| Team of 15 | Led as Sales Director, Melaleuca | verified |
| 500+ customers | Acquired as Sales Director, Melaleuca | verified |
| 30%+ monthly growth | Social and Meta Ads, family hospitality venture | VERIFY (period and base) |
| 100+ weekly customers retained | CRM and automated promotions, family hospitality venture | VERIFY |
| Positive ROI in under 3 months | Launch strategy, family hospitality venture | VERIFY (see note in section 5) |

---

## 4. Writing & Research

facets: `writing`, `data`, `music` · visibility: web, print · status: verified

Published on Medium. Tools across all pieces: Chartmetric (including API), Python, correlation analysis, public platform data.

### 4.1 I Tracked a Phantom AI Artist for 18 Months. The Problem Isn't Technological, It's Economic

- Language: EN / ES (ES title: "Llevo 18 meses espiando un catálogo generado por IA...")
- Published: June 2026
- URL: https://medium.com/@soyluisguinea/i-tracked-a-likely-ai-generated-artist-for-18-months-the-problem-is-bigger-than-i-thought-a9bbb92d93bc
- Question: What happens to the streaming economy when a likely AI-generated catalogue competes for the same royalty pool as human artists?
- Method: Tracked the Spotify profile "Poderosas Palabras", January 2025 to August 2026. Sources: Chartmetric, Spotify, TikTok, Shazam, YouTube.
- Data points:
  - Jan 2025: 170 tracks, 31,000 monthly listeners, 460,000 streams
  - Jul 2025: 273 tracks, 92,000 monthly listeners, 4.4M streams
  - Aug 2026: 340 tracks, 85,587 monthly listeners, about 13M streams
  - One new release every 1.97 days for 18 months
  - 21,628 Spotify followers, 13,000+ Shazams, 2,173 playlists, 37,000+ TikTok videos
- Finding: Platforms pay for attention, not effort. Volume-driven catalogues gain a structural advantage.
- Key metric for callout: 1 release every 1.97 days
- Chart candidate: tracks and streams across the three observation points.

### 4.2 Are We Measuring Artist Growth Wrong?

- Language: EN
- Published: June 2026
- URL: https://medium.com/@soyluisguinea/are-we-measuring-artist-growth-wrong-522c3d6a9280
- Question: Which Spotify metric predicts sustained artist growth?
- Method: 19 emerging and developing Spanish artists, Chartmetric API history, two periods (days 0–180 and 180–360), Pearson correlation.
- Findings:
  - Follower growth persistence: r = 0.77, p = 0.0001
  - Listener growth persistence: r = −0.17, p = 0.49 (no predictive power)
  - Listener to follower crossover: r = 0.55, p = 0.015
- Finding: Monthly listener spikes decay; follower growth compounds.
- Key metric for callout: r = 0.77
- Wording rule: say "strongly predicted", never "perfectly" or "almost perfectly".

### 4.3 Seven Days to Turn a Viral Moment into a Career

- Language: EN / ES (ES title: "Siete días para convertir un viral en una carrera")
- Published: June 2026
- URL: https://medium.com/@soyluisguinea/seven-days-to-turn-a-viral-moment-into-a-career-2f53d1cb7179
- Subject: Macario Martínez
- Method: Chartmetric data, January 2024 to June 2026, daily follower evolution across Spotify, TikTok and Instagram; full catalogue of 91.3M plays.
- Findings:
  - Spotify followers grew from 559 to 332,882
  - Monthly listeners peaked at 2,883,463 (March 2025) and fell 63.6% by mid-2026
  - Seven-day funnel: TikTok, then Instagram (25,283 in 48 hours), then Spotify followers (49,888 by day four), then monthly listeners on day seven
  - Viral song = 36.88% of streams; top ten songs = 86.44%
- Key metric for callout: 559 → 332K followers

### 4.4 How RATA Turned an Explosion of Listeners into a Real Fan Base

- Language: EN / ES (ES title: "Cómo RATA convirtió una explosión de oyentes en una base real de fans")
- Published: June 2026
- URL: https://medium.com/@soyluisguinea/how-rata-turned-an-explosion-of-listeners-into-a-real-fan-base-560dbabd2242
- Method: Chartmetric API, mid-2025 to mid-2026, plus qualitative review of releases.
- Findings: monthly listeners +1,128%, followers +711%, from about 10,000 to 150,000+ monthly listeners after a collaboration with Hens.
- Finding: "Listeners are a metric of reach. Followers are a metric of intent."
- Key metric for callout: +1,128% monthly listeners

### 4.5 ¿Las polémicas de Aleks Syntek son marketing?

- Language: ES
- Published: September 2026 (Part 1 of a series)
- URL: https://medium.com/@soyluisguinea/las-pol%C3%A9micas-de-aleks-syntek-son-marketing-50cd7a723318
- Method: Chartmetric API across Spotify, YouTube, Instagram and TikTok, September 2025 to September 2026, set against the public media timeline.
- Findings: Instagram daily follower gains rose from +535 to +16,550 before the "Masepum" release; Spotify monthly listeners +25.57% year over year (5.47M to 6.87M); "Duele el Amor" gained about 1.38M incremental streams in the window; no simple causality between controversy and growth.
- Key metric for callout: 12 months of data
- Status note: Part 2 pending. Update this entry when published.

### Also on Medium (personal writing, not research)

- "Ya estoy aquí" (two pieces, ES, July 2026). visibility: private by default. Luis to decide.

---

## 5. Experience

Ordered newest first. `dates` use the format shown on the site.

### Music Producer · Jazztone Studios, Valencia
- dates: Jan 2026 – Present
- facets: `music`
- visibility: web, print · status: verified
- Produce and arrange for independent artists across Latin jazz and pop.
- Compose music for film projects in Mexico and for advertising.

### Brand & Digital Growth · Santo Chilaquil, Valencia
- dates: Feb 2025 – Present
- facets: `business`, `creative`, `data`
- visibility: web, print · status: verified for role, venture name and responsibilities; metrics below remain VERIFY
- Public naming authorised by Luis: use Santo Chilaquil.
- Developed the branding and launch strategy.
- Social content and Meta Ads campaigns. Claimed 30%+ monthly growth (VERIFY period and base).
- CRM and automated promotional workflows. Claimed 100+ weekly customers retained (VERIFY).
- Local activations: flyers, collaborations, giveaways.
- Built LedgerApp to run its finances (see section 6).
- VERIFY note: an older CV claims "positive ROI in under three months". Keep it only if it refers to marketing spend, not to business profitability, and say so explicitly.

### A&R / Admin Intern · Peermusic Spain
- dates: Jul 2024 – Dec 2025
- facets: `music`, `data`
- visibility: web, print · status: verified
- Managed approvals for derivative work licensing with administration and legal teams.
- Organised and maintained the catalogue in DISCO.
- Optimised databases and ran data analysis in Python and SQL.

### Information Technology & Automation Developer · Grupo Botanas
- dates: Jan 2024 – Present
- start date confirmed by Luis on 2026-10-05 (Spanish: enero de 2024 – actualidad)
- facets: `data`, `projects`, `business`
- visibility: web, print · status: verified
- Develops information technology and automation systems for Grupo Botanas.
- Created LedgerApp.
- Created the Digital Signage system.
- Built the POS and QR-based digital menu system.
- Implemented social-media workflows and NFC-based review systems.
- Additional systems and results must only be added when documented and verified.

### Singer-Songwriter & Producer · Independent
- dates: Jan 2022 – Present
- facets: `music`, `creative`
- visibility: web, print · status: verified
- Released original singles with editorial playlist placements on Spotify and Deezer, most recently "El Beso".
- Composed for films distributed by major platforms. TODO: film titles.
- Negotiated a sync deal for an advertising campaign. TODO: brand or campaign if public.
- Performed live and managed concert production. TODO: venues.
- Released 12 original songs as an independent artist.
- Produced 23 singles for other artists. These are production credits, not Luis's own artist releases.

### A&R Manager · Tipazo Music Group
- dates: Oct 2022 – May 2023
- facets: `music`, `business`
- visibility: web, print · status: verified
- Oversaw 20 song releases, coordinating promotion and distribution with Sony Music's A&R team.
- Built artist relationships and targeted marketing campaigns per release.
- Handled royalty processing, copyright registration and label operations.

### Piano Teacher · MAP College of Music, Audio and Production
- dates: Mar 2023 – Jun 2023
- facets: `music`
- visibility: web, print · status: verified
- Designed tailored lessons developing performance skills and integrating piano with music production.

### Music Director & Keyboardist · Mandala Love Music
- dates: Jul 2021 – Jun 2023
- facets: `music`, `creative`
- visibility: web, print · status: verified
- Transcription, arrangement, demo production and live performance with an 11-piece ensemble.
- Live-recorded medleys.

### Founder & Label Director · Moctezuma Music Group
- dates: Oct 2015 – Aug 2023
- facets: `music`, `business`, `creative`
- visibility: web, print · status: verified
- Launched and marketed more than 50 artists in the Mexican market, reaching over 10 million streams.
- Ran release campaigns and tours end to end.
- Sync placements in film and advertising. TODO: examples.
- After Aug 2023, Moctezuma Music ceased operating as an active record label but remains active as a consultancy for independent artists and as a production company.

### Key Account Brand Manager · Parvin Music
- dates: Jun 2021 – Jul 2022
- facets: `business`, `creative`
- visibility: web, print · status: verified
- Lead contact with production agency Landia for the "La Villita" TV commercial: pre-production, contracts, recording sessions and contract compliance.

### Academic Assistant · VoxGarten + MusicLab
- dates: Jul 2021 – Jul 2022
- facets: `music`
- visibility: print (optional) · status: verified
- Music education, recording studio activity and rehearsal room management.

### Marketing Director · Sell It
- dates: Dec 2016 – Aug 2017
- facets: `business`, `creative`
- visibility: print (optional) · status: verified
- Led the marketing team and shaped the brand identity; data-driven funnel optimisation and partnerships.

### Sales Director · Melaleuca
- dates: Nov 2014 – Nov 2016
- facets: `business`
- visibility: web, print · status: verified
- Led a team of 15 sales professionals and acquired more than 500 recurring customers, with a focus on retention.

### Data Curator · Trade Marketing Solutions
- dates: Jun 2012 – Aug 2014
- facets: `data`
- visibility: print (optional) · status: verified
- Maintained and optimised the company's data infrastructure across its lifecycle; database administration supporting marketing and promotions.

### Voice work
- dates: TODO
- facets: `music`, `creative`
- visibility: web · status: TODO
- Dubbing, voiceover and podcast hosting in Spanish and English. TODO: clients, shows, samples.

---

## 6. Projects & Systems

### LedgerApp
- facets: `projects`, `data`, `business`
- visibility: web · status: verified as a project created by Luis for Grupo Botanas; case study content remains TODO
- What it is: financial and operational management system for restaurants.
- Stack: Next.js, Supabase, Last.app POS integration, Google Calendar, MCP servers.
- Authorship/context: created by Luis for Grupo Botanas.
- Case study TODO (BRAND.md section 21): problem, process, solution, result, metrics, screenshots.
- Privacy: do not show real revenue or customer data. Use anonymised or demo data.

### Digital Signage
- facets: `projects`, `data`, `business`
- visibility: web · status: verified as a project created by Luis for Grupo Botanas; case study content remains TODO
- What it is: a digital signage system created for Grupo Botanas.
- Authorship/context: created by Luis for Grupo Botanas.
- Case study TODO (BRAND.md section 21): architecture, problem, process, solution, result, metrics, screenshots.

### MCP integrations for restaurant data
- facets: `projects`, `data`
- visibility: web · status: TODO
- MCP servers connecting Last.app and LedgerApp data to AI assistants. TODO: confirm scope and authorship, add description.

### Music projects and aliases
- facets: `music`, `creative`, `projects`
- visibility: web · status: TODO (links and samples)
- Mocte: rap / hip-hop
- Lukas Eisenhart: solo piano
- ilovepancakes: lo-fi
- Joy Between Breaths: meditation music
- TODO: one track, cover and link per alias.

### Other experiments
- macOS focus blocker (free, no paid dependencies). status: TODO; publish only if there is a repo or demo.

---

## 7. Education

| Degree | Institution | Dates | Visibility |
|---|---|---|---|
| MA, Global Entertainment and Music Business | Berklee College of Music, Valencia | Jun 2023 – Jul 2024 | web, print |
| Bachelor's Degree, Music Production | REC Música, Music Studies Center | Aug 2017 – Jun 2021 | web, print |
| Bachelor's Degree, Communication and Digital Media | Tec de Monterrey | Aug 2011 – Aug 2015 | web, print |

Also: pianist since age four (web, profile detail).

---

## 8. Skills

Plain grouped lists. No bars, percentages or logos (BRAND.md section 30).

- **Research & writing:** long-form and data journalism in English and Spanish, case studies, source and timeline verification.
- **Data & technology:** Python, SQL, Chartmetric (including API), AWS (EC2), ETL and data pipelines, automation, Power BI, Tableau, Excel, Google Analytics, Next.js, Supabase, MCP servers.
- **Music:** production, composition, arrangement, music direction, piano and keys, Pro Tools, Logic Pro, Ableton Live.
- **Industry:** A&R, artist development, release planning, catalogue and licensing (DISCO), royalties, copyright registration, sync.
- **Business:** brand strategy, digital marketing (Meta Ads, organic social), CRM, sales and team leadership, project and budget management, contracts.
- **Visual:** Final Cut Pro, Photoshop, Illustrator.
- **Languages:** Spanish (native), English (fluent), French (B2).

Excluded on purpose (outdated or off-brand): blockchain and NFTs, Decentraland / OnCyber, generic soft skills.

---

## 9. Fusion record

This canonical file incorporates the validated content from `CV_MASTER_UPDATED.md` while retaining the factual information that was already present in this file. The merge adds or clarifies:

- publication authorisation and provenance for `profile_pic.png` and `cover.png`, while preserving the requirement to use optimised derivatives without overwriting originals;
- the 10+ years wording in the profile and the technology and automation focus in the short profile;
- the verified January 2026 start at Jazztone Studios and the authorised public naming and verified role context for Santo Chilaquil, while keeping its metrics as `VERIFY`;
- the current Grupo Botanas role and its documented systems, including LedgerApp, Digital Signage, POS/QR menu and social/NFC workflows;
- the distinction between 12 original songs by Luis and 23 production credits for other artists;
- the post-August 2023 status of Moctezuma Music as consultancy and production company;
- LedgerApp authorship/context and the new Digital Signage project, both with case-study details still marked `TODO`;
- the resulting, shorter open-items list.

No information exclusive to the previous `CV_MASTER.md` was removed; unresolved claims remain marked `TODO` or `VERIFY` and therefore are not publishable as facts.

## 10. Open items for Luis

1. Hospitality venture metrics: confirm 30%+ growth, 100+ weekly customers, and what "positive ROI" measured.
2. Film titles, sync brand, venues and voice work clients.
3. LinkedIn URL and Spotify links.
4. LedgerApp and Digital Signage case study content, results, metrics and demo screenshots.
5. Whether "Ya estoy aquí" pieces appear on the site.

Resolved on 2026-10-05: the start date of the current Grupo Botanas role is January 2024, confirmed by Luis (former open item 6).
