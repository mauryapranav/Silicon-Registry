# Silicon Registry

**Crowdsourced Linux hardware compatibility database**

Silicon Registry is a community-driven platform for tracking, reporting, and improving Linux hardware compatibility across laptops, desktops, mini PCs, and individual components. The goal is a reliable, transparent, and up-to-date registry that helps users find the best hardware for their Linux experience.

> 🌐 **Live at** [[silicon-registry-production.up.railway.app](https://silicon-registry.up.railway.app)](https://silicon-registry-production.up.railway.app/)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Compatibility Reports** | Tiered boot status — Gold, Silver, Bronze, Broken |
| **Machine Registry** | Growing database of laptops, desktops, mini PCs |
| **Hardware Specs** | CPU, GPU, RAM, storage, display, battery per device |
| **Component Tracking** | Per-component status: Wi-Fi, Audio, GPU, Bluetooth |
| **Driver Fix Library** | Community workarounds, kernel params, driver guides |
| **Trust System** | Reputation-based moderation with audit-trailed scoring |
| **Spec Suggestions** | Crowdsourced spec updates with proof-based verification |
| **Fuzzy Search** | Typo-tolerant search with "did you mean" suggestions |
| **HTMX UI** | Fast, partial-reload interface without a JS framework |
| **REST API** | Read-only JSON API for machines, reports, components, distros |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, Django 5, Django REST Framework |
| Frontend | HTML5, Tailwind CSS (CDN), HTMX, Lucide Icons |
| Database | MySQL (utf8mb4) |
| Auth | django-allauth (GitHub OAuth) |
| Deployment | Railway / PaaS |

---

## 🏗️ Architecture

### Data Model
- **Single unified `Report` model** with nullable FKs across machines, components, and distros — keeps votes/comments centralized and reduces join complexity.
- **`TrustEvent` audit log** — every trust score change is explicitly recorded; penalties require moderator approval before affecting a user's score.
- **Generic interactions** — voting and flagging use Django's `ContentTypes` framework, making them work across any future entity.

### Pages & Routing
```
/                     → Homepage — hero, stats, top hardware
/machines/            → Browse all machines with filters
/machines/<slug>/     → Machine detail — specs, component matrix, reports
/components/<slug>/   → Component detail — driver info, compatibility arc
/reports/<id>/        → Report detail — component results, comments, votes
/search/              → Fuzzy search across machines, components, reports
/leaderboard/         → Contributors ranked by trust score
/profile/<username>/  → User profile — stats, reports, fixes
/mod/                 → Moderator dashboard — pending queue management
/api/                 → REST API (read-only)
```

---

## 🤝 Contributing

Community contributions keep the registry accurate and growing:

- **Submit Reports** — share your hardware + Linux distro experience
- **Verify Specs** — suggest spec updates with manufacturer sources
- **Driver Fixes** — post kernel parameters, modprobe configs, workarounds
- **Code** — PRs welcome for new features, bug fixes, or design improvements

---

## 📊 Rating System

| Rating | Meaning |
|--------|---------|
| 🥇 **Gold** | Everything works out of the box |
| 🥈 **Silver** | Most things work, minor issues only |
| 🥉 **Bronze** | Usable with significant workarounds |
| 💔 **Broken** | Does not boot or is entirely unusable |
---

*"Helping you find the silicon that speaks Linux."*
