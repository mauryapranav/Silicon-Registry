# Silicon Registry

**Crowdsourced Linux hardware compatibility database**

Silicon Registry is a community-driven platform for tracking, reporting, and improving Linux hardware compatibility across laptops, desktops, mini PCs, and individual components. Our goal is to provide a reliable, transparent, and up-to-date registry that helps users find the best hardware for their Linux experience.

---

## 🚀 Key Features

- **Hardware Compatibility Reports**: Detailed community reports with tiered boot status (Gold, Silver, Bronze, Broken).
- **Machine Registry**: A growing database of hardware models, including laptops, desktops, and handhelds.
- **Detailed Technical Specs**: Comprehensive machine specifications, from CPU/GPU details to battery capacity and panel types.
- **Component-Level Tracking**: Per-component status tracking for Wi-Fi, Audio, GPU, Bluetooth, and Input devices.
- **Community Driver Fixes**: A central place for users to share and find workarounds, kernel parameters, and driver installation guides.
- **Reputation-based Trust System**: A moderation layer powered by user contributions, ensuring high-quality, verified data.
- **Spec Suggestions**: Crowdsourced updates to hardware specifications with proof-based verification.
- **Interactive HTMX UI**: A modern, fast, and responsive user interface powered by HTMX partials.
- **REST API**: Read-only JSON API for accessing machine, report, component, and distro data.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12+, [Django](https://www.djangoproject.com/), [Django REST Framework](https://www.django-rest-framework.org/)
- **Frontend**: HTML5, [Vanilla CSS](https://developer.mozilla.org/en-US/docs/Web/CSS), [HTMX](https://htmx.org/)
- **Database**: [MySQL](https://www.mysql.com/) (with utf8mb4 support)
- **Auth**: [django-allauth](https://django-allauth.readthedocs.io/en/latest/) (GitHub OAuth support)
- **Styling**: [Bootstrap 5](https://getbootstrap.com/) (base) + Custom Silicon CSS

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.12 or higher
- MySQL Server
- `virtualenv` or `venv`

### Getting Started

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/silicon-registry.git
   cd silicon-registry
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install django django-allauth djangorestframework mysqlclient pillow requests
   ```
   *(Note: Ensure you have the necessary MySQL development headers installed on your system for `mysqlclient`.)*

4. **Configure Database**:
   Create a MySQL database named `silicon_registry` and update the `DATABASES` setting in `silicon_registry/settings.py` with your credentials.

5. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Create a Superuser**:
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the Development Server**:
   ```bash
   python manage.py runserver
   ```

8. **Access the Registry**:
   Visit `http://127.0.0.1:8000/` in your browser.

---

## 🏗️ Architecture Decisions

The project follows several key architectural decisions to ensure scalability and maintainability:

1. **Single Flexible Report Table**: Instead of separate tables for different report types (Machine, Component, Distro), a single unified `Report` model is used with nullable foreign keys. This reduces join complexity and keeps community interactions (votes, comments) centralized.
2. **Audit-trailed Trust System**: Every trust score change is logged in a `TrustEvent` table, ensuring transparency. Penalties for rejected reports require explicit moderator approval before affecting a user's score.
3. **Generic Interactions**: Voting and flagging systems utilize Django's `GenericForeignKey` (ContentTypes), allowing them to work seamlessly across reports, comments, and other future entities.

---

## 🤝 Contributing

We welcome contributions of all kinds! Whether you're reporting a bug, suggesting a feature, or submitting a driver fix, your help makes the registry better for everyone.

- **Submit Reports**: Share your hardware experience by submitting compatibility reports.
- **Verify Specs**: Suggest updates to machine specifications to keep the database accurate.
- **Code Contributions**: Pull requests are welcome for new features, bug fixes, or UI improvements.

---

## ⚖️ License

This project is currently licensed under the [MIT License](LICENSE) (or your preferred license).

---

*“Helping you find the silicon that speaks Linux.”*
