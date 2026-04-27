"""
registry/management/commands/seed_data.py
=========================================
Idempotent seed data command for Silicon Registry.
Uses get_or_create for all objects — running twice never creates duplicates.

Usage: python manage.py seed_data
"""

from django.core.management.base import BaseCommand
from registry.models import (
    User, Machine, MachineSpec, Distro, Component, ComponentSpec,
    Report, CompStatus, Comment, DriverFix
)


class Command(BaseCommand):
    help = 'Seed the database with realistic sample data for Silicon Registry'

    def handle(self, *args, **options):
        self.stdout.write('Seeding Silicon Registry database...\n')

        users = self._seed_users()
        distros = self._seed_distros()
        machines = self._seed_machines()
        components = self._seed_components()
        reports = self._seed_reports(users, distros, machines, components)
        self._seed_driver_fixes(users, components)

        self.stdout.write(self.style.SUCCESS(
            f'\nSeeding complete!\n'
            f'  Users: {len(users)}\n'
            f'  Distros: {len(distros)}\n'
            f'  Machines: {len(machines)}\n'
            f'  Components: {len(components)}\n'
            f'  Reports: {len(reports)}\n'
        ))

    def _seed_users(self):
        self.stdout.write('  Creating users...')
        user_data = [
            {'username': 'tuxlover', 'email': 'tux@example.com', 'role_type': 'CONTRIBUTOR', 'positive_score': 45},
            {'username': 'kernelhacker', 'email': 'kernel@example.com', 'role_type': 'MAINTAINER', 'positive_score': 120},
            {'username': 'archmaster', 'email': 'arch@example.com', 'role_type': 'CONTRIBUTOR', 'positive_score': 80},
            {'username': 'newbie99', 'email': 'newbie@example.com', 'role_type': 'CONTRIBUTOR', 'positive_score': 5},
        ]
        users = {}
        for ud in user_data:
            user, created = User.objects.get_or_create(
                username=ud['username'],
                defaults={
                    'email': ud['email'],
                    'role_type': ud['role_type'],
                    'positive_score': ud['positive_score'],
                }
            )
            # Always reset password so test credentials work
            user.set_password('testpass123')
            if not created:
                user.role_type = ud['role_type']
                user.positive_score = ud['positive_score']
            user.save()
            users[ud['username']] = user
        return users

    def _seed_distros(self):
        self.stdout.write('  Creating distros...')
        distro_data = [
            {'name': 'Ubuntu', 'version': '24.04', 'kernel_default': '6.8.0-45', 'is_lts': True, 'based_on': 'Debian', 'desktop_default': 'GNOME'},
            {'name': 'Ubuntu', 'version': '22.04', 'kernel_default': '5.15.0-91', 'is_lts': True, 'based_on': 'Debian', 'desktop_default': 'GNOME'},
            {'name': 'Fedora', 'version': '40', 'kernel_default': '6.8.9', 'based_on': 'RPM', 'desktop_default': 'GNOME'},
            {'name': 'Fedora', 'version': '41', 'kernel_default': '6.11.0', 'based_on': 'RPM', 'desktop_default': 'GNOME'},
            {'name': 'Arch Linux', 'version': 'Rolling', 'kernel_default': '6.10.0', 'is_rolling': True, 'desktop_default': 'varies'},
            {'name': 'Debian', 'version': '12 Bookworm', 'kernel_default': '6.1.0', 'is_lts': True, 'desktop_default': 'GNOME'},
            {'name': 'openSUSE Tumbleweed', 'version': 'Rolling', 'kernel_default': '6.9.0', 'is_rolling': True, 'desktop_default': 'KDE'},
            {'name': 'Pop!_OS', 'version': '22.04', 'kernel_default': '6.6.10', 'is_lts': True, 'based_on': 'Ubuntu', 'desktop_default': 'COSMIC'},
            {'name': 'Linux Mint', 'version': '21.3 Virginia', 'kernel_default': '5.15.0', 'is_lts': True, 'based_on': 'Ubuntu', 'desktop_default': 'Cinnamon'},
            {'name': 'NixOS', 'version': '24.05', 'kernel_default': '6.6.0', 'based_on': 'Nix', 'desktop_default': 'varies'},
        ]
        distros = {}
        for dd in distro_data:
            distro, _ = Distro.objects.get_or_create(
                name=dd['name'], version=dd['version'],
                defaults={
                    'kernel_default': dd.get('kernel_default', ''),
                    'is_lts': dd.get('is_lts', False),
                    'is_rolling': dd.get('is_rolling', False),
                    'based_on': dd.get('based_on', ''),
                    'desktop_default': dd.get('desktop_default', ''),
                }
            )
            distros[f"{dd['name']} {dd['version']}"] = distro
        return distros

    def _seed_machines(self):
        self.stdout.write('  Creating machines...')
        machine_data = [
            {
                'vendor': 'Lenovo', 'series': 'ThinkPad', 'model_name': 'X1 Carbon Gen 11', 'cpu_family': 'Intel 13th Gen', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Core i7-1365U', 'cpu_manufacturer': 'INTEL', 'cpu_generation': '13th Gen', 'cpu_series_tier': 'U',
                         'gpu_name': 'Intel Iris Xe', 'gpu_manufacturer': 'INTEL', 'gpu_type': 'INTEGRATED',
                         'ram_type': 'LPDDR5', 'ram_speed_mhz': 5200, 'ram_base_gb': 16, 'ram_max_gb': 32,
                         'storage_type': 'NVME', 'storage_base_gb': 512, 'storage_max_gb': 2000,
                         'display_size_inches': 14.0, 'display_resolution': '1920x1200', 'display_panel_type': 'IPS',
                         'battery_wh': 57.0}
            },
            {
                'vendor': 'Lenovo', 'series': 'ThinkPad', 'model_name': 'T14s Gen 4 AMD', 'cpu_family': 'AMD Zen 4', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Ryzen 7 Pro 7840U', 'cpu_manufacturer': 'AMD', 'cpu_generation': 'Zen 4', 'cpu_series_tier': 'U',
                         'gpu_name': 'Radeon 780M', 'gpu_manufacturer': 'AMD', 'gpu_type': 'INTEGRATED',
                         'ram_type': 'LPDDR5X', 'ram_speed_mhz': 6400, 'ram_base_gb': 16, 'ram_max_gb': 64,
                         'display_size_inches': 14.0, 'display_resolution': '1920x1200', 'display_panel_type': 'IPS',
                         'battery_wh': 57.0}
            },
            {
                'vendor': 'Dell', 'series': 'XPS', 'model_name': '15 9530', 'cpu_family': 'Intel 13th Gen', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Core i9-13900H', 'cpu_manufacturer': 'INTEL', 'cpu_generation': '13th Gen', 'cpu_series_tier': 'H',
                         'gpu_name': 'RTX 4060', 'gpu_manufacturer': 'NVIDIA', 'gpu_generation': 'Ada Lovelace', 'gpu_type': 'DEDICATED',
                         'ram_type': 'DDR5', 'ram_speed_mhz': 4800, 'ram_base_gb': 16, 'ram_max_gb': 64,
                         'storage_type': 'NVME', 'storage_base_gb': 512,
                         'display_size_inches': 15.6, 'display_resolution': '1920x1200', 'display_panel_type': 'OLED',
                         'battery_wh': 86.0}
            },
            {
                'vendor': 'Framework', 'series': 'Laptop', 'model_name': '13 AMD', 'cpu_family': 'AMD Zen 4', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Ryzen 7 7840U', 'cpu_manufacturer': 'AMD', 'cpu_generation': 'Zen 4', 'cpu_series_tier': 'U',
                         'gpu_name': 'Radeon 780M', 'gpu_manufacturer': 'AMD', 'gpu_type': 'INTEGRATED',
                         'ram_type': 'DDR5', 'ram_speed_mhz': 5600, 'ram_base_gb': 16, 'ram_max_gb': 64,
                         'display_size_inches': 13.5, 'display_resolution': '2256x1504', 'display_panel_type': 'IPS',
                         'battery_wh': 61.0}
            },
            {
                'vendor': 'Framework', 'series': 'Laptop', 'model_name': '16', 'cpu_family': 'AMD Zen 4', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Ryzen 7 7745HX', 'cpu_manufacturer': 'AMD', 'cpu_generation': 'Zen 4', 'cpu_series_tier': 'HX',
                         'gpu_name': 'RX 7700S', 'gpu_manufacturer': 'AMD', 'gpu_generation': 'RDNA3', 'gpu_type': 'DEDICATED',
                         'ram_type': 'DDR5', 'ram_speed_mhz': 5600, 'ram_base_gb': 32, 'ram_max_gb': 64,
                         'display_size_inches': 16.0, 'display_resolution': '2560x1600', 'display_panel_type': 'IPS',
                         'battery_wh': 85.0}
            },
            {
                'vendor': 'ASUS', 'series': 'ROG', 'model_name': 'Zephyrus G14 2024', 'cpu_family': 'AMD Zen 4', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Ryzen 9 8945HS', 'cpu_manufacturer': 'AMD', 'cpu_generation': 'Zen 4', 'cpu_series_tier': 'H',
                         'gpu_name': 'RX 7600S', 'gpu_manufacturer': 'AMD', 'gpu_generation': 'RDNA3', 'gpu_type': 'DEDICATED',
                         'ram_type': 'LPDDR5X', 'ram_speed_mhz': 7500, 'ram_base_gb': 32, 'ram_max_gb': 32,
                         'display_size_inches': 14.0, 'display_resolution': '2560x1600', 'display_panel_type': 'OLED',
                         'battery_wh': 73.0}
            },
            {
                'vendor': 'HP', 'series': 'Dev One', 'model_name': 'Dev One', 'cpu_family': 'AMD Zen 3+', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Ryzen 7 Pro 6850U', 'cpu_manufacturer': 'AMD', 'cpu_generation': 'Zen 3+', 'cpu_series_tier': 'U',
                         'gpu_name': 'Radeon 680M', 'gpu_manufacturer': 'AMD', 'gpu_type': 'INTEGRATED',
                         'ram_type': 'LPDDR5', 'ram_speed_mhz': 6400, 'ram_base_gb': 16, 'ram_max_gb': 16,
                         'display_size_inches': 14.0, 'display_resolution': '1920x1200', 'display_panel_type': 'IPS',
                         'battery_wh': 83.0}
            },
            {
                'vendor': 'System76', 'series': 'Lemur Pro', 'model_name': 'Lemur Pro', 'cpu_family': 'Intel 12th Gen', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Core i7-1260P', 'cpu_manufacturer': 'INTEL', 'cpu_generation': '12th Gen', 'cpu_series_tier': 'P',
                         'gpu_name': 'Intel Iris Xe', 'gpu_manufacturer': 'INTEL', 'gpu_type': 'INTEGRATED',
                         'ram_type': 'LPDDR5', 'ram_speed_mhz': 4800, 'ram_base_gb': 16, 'ram_max_gb': 48,
                         'display_size_inches': 14.0, 'display_resolution': '1920x1080', 'display_panel_type': 'IPS',
                         'battery_wh': 73.0}
            },
            {
                'vendor': 'Apple', 'series': 'MacBook Pro', 'model_name': 'M3 Pro 14', 'cpu_family': 'Apple M3', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Apple M3 Pro', 'cpu_manufacturer': 'APPLE', 'cpu_generation': 'M3', 'cpu_series_tier': 'STANDARD',
                         'gpu_name': 'Apple GPU', 'gpu_manufacturer': 'APPLE', 'gpu_type': 'INTEGRATED',
                         'ram_type': 'LPDDR5', 'ram_speed_mhz': 6400, 'ram_base_gb': 18, 'ram_max_gb': 36,
                         'display_size_inches': 14.2, 'display_resolution': '3024x1964', 'display_panel_type': 'MINI_LED',
                         'battery_wh': 70.0}
            },
            {
                'vendor': 'Lenovo', 'series': 'IdeaPad', 'model_name': 'Slim 5 Gen 8', 'cpu_family': 'AMD Zen 3', 'form_factor': 'LAPTOP',
                'spec': {'cpu_name': 'Ryzen 5 7530U', 'cpu_manufacturer': 'AMD', 'cpu_generation': 'Zen 3', 'cpu_series_tier': 'U',
                         'gpu_name': 'Radeon Graphics', 'gpu_manufacturer': 'AMD', 'gpu_type': 'INTEGRATED',
                         'ram_type': 'DDR4', 'ram_speed_mhz': 3200, 'ram_base_gb': 8, 'ram_max_gb': 16,
                         'display_size_inches': 16.0, 'display_resolution': '1920x1200', 'display_panel_type': 'IPS',
                         'battery_wh': 56.0}
            },
            {
                'vendor': 'Beelink', 'series': 'SER', 'model_name': 'SER6 Pro', 'cpu_family': 'AMD Zen 3+', 'form_factor': 'MINI_PC',
                'spec': {'cpu_name': 'Ryzen 7 6800H', 'cpu_manufacturer': 'AMD', 'cpu_generation': 'Zen 3+', 'cpu_series_tier': 'H',
                         'gpu_name': 'Radeon 680M', 'gpu_manufacturer': 'AMD', 'gpu_type': 'INTEGRATED',
                         'ram_type': 'DDR5', 'ram_base_gb': 16, 'ram_max_gb': 64}
            },
            {
                'vendor': 'Custom', 'series': 'Desktop', 'model_name': 'AMD Build', 'cpu_family': 'AMD Zen 4', 'form_factor': 'DESKTOP',
                'spec': {'cpu_name': 'Ryzen 9 7950X', 'cpu_manufacturer': 'AMD', 'cpu_generation': 'Zen 4', 'cpu_series_tier': 'STANDARD',
                         'gpu_name': 'RX 7900 XTX', 'gpu_manufacturer': 'AMD', 'gpu_generation': 'RDNA3', 'gpu_type': 'DEDICATED'}
            },
        ]
        machines = {}
        for md in machine_data:
            spec_data = md.pop('spec')
            machine, _ = Machine.objects.get_or_create(
                vendor=md['vendor'], series=md['series'], model_name=md['model_name'],
                defaults={'cpu_family': md['cpu_family'], 'form_factor': md['form_factor']}
            )
            MachineSpec.objects.get_or_create(machine=machine, defaults=spec_data)
            machines[f"{md['vendor']} {md['model_name']}"] = machine
        return machines

    def _seed_components(self):
        self.stdout.write('  Creating components...')
        comp_data = [
            {'type': 'GPU', 'name': 'NVIDIA RTX 4060', 'spec': {'gpu_vram_gb': 8, 'gpu_architecture': 'ADA_LOVELACE', 'gpu_tdp_watts': 115, 'gpu_memory_type': 'GDDR6', 'gpu_generation': 'RTX 40xx', 'gpu_cuda_cores': 3072}},
            {'type': 'GPU', 'name': 'AMD Radeon RX 7600S', 'spec': {'gpu_vram_gb': 8, 'gpu_architecture': 'RDNA3', 'gpu_tdp_watts': 75, 'gpu_memory_type': 'GDDR6', 'gpu_generation': 'RX 7xxx'}},
            {'type': 'GPU', 'name': 'Intel Arc A770', 'spec': {'gpu_vram_gb': 16, 'gpu_architecture': 'INTEL_XE', 'gpu_tdp_watts': 225, 'gpu_memory_type': 'GDDR6'}},
            {'type': 'GPU', 'name': 'AMD Radeon 780M', 'spec': {'gpu_vram_gb': 0, 'gpu_architecture': 'RDNA3', 'gpu_memory_type': 'SHARED', 'gpu_generation': 'Integrated RDNA 3'}},
            {'type': 'WIFI', 'name': 'Intel AX211', 'driver': 'iwlwifi', 'spec': {'wifi_standard': 'WIFI6E', 'wifi_max_speed_mbps': 2400, 'wifi_bands': '2.4GHz, 5GHz, 6GHz', 'wifi_bluetooth_ver': '5.3'}},
            {'type': 'WIFI', 'name': 'MediaTek MT7922', 'driver': 'mt7921e', 'spec': {'wifi_standard': 'WIFI6E', 'wifi_max_speed_mbps': 2400, 'wifi_bands': '2.4GHz, 5GHz, 6GHz', 'wifi_bluetooth_ver': '5.3'}},
            {'type': 'WIFI', 'name': 'Qualcomm WCN785x', 'driver': 'ath12k', 'spec': {'wifi_standard': 'WIFI7', 'wifi_max_speed_mbps': 5765, 'wifi_bands': '2.4GHz, 5GHz, 6GHz', 'wifi_bluetooth_ver': '5.4'}},
            {'type': 'AUDIO', 'name': 'Realtek ALC289', 'driver': 'snd_hda_intel', 'spec': {'audio_codec': 'ALC289', 'audio_jack_detection': True, 'audio_hdmi_output': True, 'audio_microphone': True, 'audio_speakers': True}},
            {'type': 'AUDIO', 'name': 'Realtek ALC295', 'driver': 'snd_hda_intel', 'spec': {'audio_codec': 'ALC295', 'audio_jack_detection': True, 'audio_microphone': True}},
            {'type': 'STORAGE', 'name': 'Samsung PM9A1 NVMe', 'spec': {'storage_interface': 'NVME_GEN4', 'storage_form_factor': 'M.2 2280', 'storage_capacity_gb': 512, 'storage_read_mbps': 7000, 'storage_write_mbps': 5000}},
            {'type': 'STORAGE', 'name': 'WD Black SN850X', 'spec': {'storage_interface': 'NVME_GEN4', 'storage_form_factor': 'M.2 2280', 'storage_capacity_gb': 1000, 'storage_read_mbps': 7300, 'storage_write_mbps': 6600}},
            {'type': 'DISPLAY', 'name': 'BOE NE160QDM-NX1', 'spec': {'display_size_inches': 16.0, 'display_resolution': '2560x1600', 'display_refresh_hz': 165, 'display_tech': 'IPS', 'display_touch': False, 'display_hdr': False, 'display_brightness': 400}},
            {'type': 'FINGERPRINT', 'name': 'Goodix Fingerprint USB', 'driver': 'goodix'},
            {'type': 'BLUETOOTH', 'name': 'Intel Bluetooth AX211', 'driver': 'btusb'},
            {'type': 'ETHERNET', 'name': 'Intel I219-V', 'driver': 'e1000e', 'spec': {'ethernet_speed_mbps': 1000, 'ethernet_chip': 'Intel I219-V'}},
            {'type': 'THUNDERBOLT', 'name': 'Intel Thunderbolt 4', 'driver': 'thunderbolt', 'spec': {'tb_version': '4', 'tb_power_delivery': True, 'tb_display_output': True, 'tb_data_speed_gbps': 40}},
        ]
        components = {}
        for cd in comp_data:
            spec_data = cd.pop('spec', None)
            component, _ = Component.objects.get_or_create(
                type=cd['type'], name=cd['name'],
                defaults={'driver': cd.get('driver', '')}
            )
            if spec_data:
                ComponentSpec.objects.get_or_create(component=component, defaults=spec_data)
            components[cd['name']] = component
        return components

    def _seed_reports(self, users, distros, machines, components):
        self.stdout.write('  Creating reports...')
        report_data = [
            {
                'title': 'ThinkPad X1 Carbon Gen 11 on Ubuntu 24.04 — Almost Perfect',
                'description': 'Installed Ubuntu 24.04 LTS on the ThinkPad X1 Carbon Gen 11. Everything worked out of the box including WiFi (iwlwifi), audio, fingerprint reader, and suspend/resume. Trackpoint and touchpad work perfectly with libinput. The only minor issue was the IR camera for Windows Hello not being supported, but the regular webcam works fine. Battery life averages around 8-10 hours with TLP installed. Highly recommended for Linux users.',
                'machine': 'Lenovo X1 Carbon Gen 11', 'distro': 'Ubuntu 24.04',
                'boot_status': 'GOLD', 'kernel_version': '6.8.0-45', 'user': 'tuxlover',
                'comp_statuses': [('Intel AX211', 'WORKING', 'WiFi 6E works perfectly out of the box'), ('Realtek ALC289', 'WORKING', 'All audio outputs work including HDMI'), ('Goodix Fingerprint USB', 'WORKING', 'Works with fprintd after enabling')],
                'comments': [('kernelhacker', 'Can confirm, runs great on my X1C Gen 11 too. TLP is essential for battery life.'), ('archmaster', 'Does the IR camera work with howdy?')],
            },
            {
                'title': 'Dell XPS 15 9530 on Fedora 40 — NVIDIA needs setup',
                'description': 'Fresh install of Fedora 40 on XPS 15 9530. The Intel integrated GPU works immediately, but the NVIDIA RTX 4060 needs the proprietary driver installed via RPM Fusion. After installing akmod-nvidia, GPU switching with prime-run works well. Suspend/resume occasionally hangs on the NVIDIA GPU — switching to integrated before suspend fixes this. WiFi (AX211) works flawlessly. Display scaling at 125% looks great on the OLED panel.',
                'machine': 'Dell 15 9530', 'distro': 'Fedora 40',
                'boot_status': 'SILVER', 'kernel_version': '6.8.9', 'user': 'kernelhacker',
                'comp_statuses': [('NVIDIA RTX 4060', 'ISSUES', 'Needs akmod-nvidia from RPM Fusion. Suspend may hang with dGPU active.'), ('Intel AX211', 'WORKING', 'No issues at all')],
                'comments': [('tuxlover', 'Try adding nvidia.NVreg_PreserveVideoMemoryAllocations=1 to kernel params for better suspend.')],
            },
            {
                'title': 'Framework 13 AMD on Arch Linux — Gold after patch',
                'description': 'Running Arch Linux on the Framework Laptop 13 AMD (Ryzen 7 7840U). Initial install required linux-firmware update for the MediaTek WiFi card. After updating to the latest firmware, WiFi is stable. The fingerprint reader works with fprintd. Audio works perfectly with PipeWire. The modular design means all ports are hot-swappable. Battery life is excellent at around 10 hours. This is the best Linux laptop I have ever used.',
                'machine': 'Framework 13 AMD', 'distro': 'Arch Linux Rolling',
                'boot_status': 'GOLD', 'kernel_version': '6.10.0', 'user': 'archmaster',
                'comp_statuses': [('AMD Radeon 780M', 'WORKING', 'AMDGPU driver works perfectly'), ('MediaTek MT7922', 'WORKING', 'Stable after firmware update'), ('Realtek ALC295', 'WORKING', 'PipeWire handles everything')],
                'comments': [('kernelhacker', 'Framework laptops are the gold standard for Linux compatibility.')],
            },
            {
                'title': 'ASUS ROG Zephyrus G14 2024 on Ubuntu 24.04 — GPU issues',
                'description': 'The ROG Zephyrus G14 2024 with RX 7600S on Ubuntu 24.04. The AMD GPU has intermittent issues with the amdgpu driver — occasional screen flickering during GPU-intensive tasks. The Qualcomm WiFi 7 card (WCN785x) works well with ath12k. Audio is fine. The keyboard RGB can be controlled with asusctl. Suspend works but resume takes about 5 seconds. Gaming performance in Steam Proton is decent once GPU issues are worked around.',
                'machine': 'ASUS Zephyrus G14 2024', 'distro': 'Ubuntu 24.04',
                'boot_status': 'SILVER', 'kernel_version': '6.8.0-45', 'user': 'tuxlover',
                'comp_statuses': [('AMD Radeon RX 7600S', 'ISSUES', 'Screen flickering under heavy GPU load. May need amdgpu.ppfeaturemask=0xffffffff'), ('Qualcomm WCN785x', 'WORKING', 'WiFi 7 works well via ath12k')],
                'comments': [('archmaster', 'The flickering is a known RDNA3 issue. Try kernel 6.10+ for the fix.')],
            },
            {
                'title': 'Framework 16 on Fedora 40 — Excellent Linux laptop',
                'description': 'Framework Laptop 16 with RX 7700S discrete GPU module running Fedora 40. Everything works out of the box with the latest kernel. The dGPU module can be hot-swapped which is incredible. GPU performance in games via Steam Proton is excellent. WiFi (AX211) is rock solid. The 16-inch 2560x1600 display looks great. Battery life is around 6-7 hours without the dGPU module, 4 hours with it.',
                'machine': 'Framework 16', 'distro': 'Fedora 40',
                'boot_status': 'GOLD', 'kernel_version': '6.8.9', 'user': 'kernelhacker',
                'comp_statuses': [('AMD Radeon RX 7600S', 'WORKING', 'AMDGPU works perfectly for the RX 7700S module'), ('Intel AX211', 'WORKING', 'Solid WiFi performance')],
                'comments': [('tuxlover', 'How is the fan noise under load?'), ('kernelhacker', 'Fans are audible but not excessive. Much better than my XPS.')],
            },
            {
                'title': 'HP Dev One on Pop!_OS 22.04 — Made for Linux',
                'description': 'The HP Dev One was literally designed for Linux developers with Pop!_OS pre-installed. Everything works perfectly — WiFi, audio, touchpad, suspend, fingerprint reader. The AMD Ryzen 7 Pro 6850U is fast and efficient. Battery life is exceptional at 10-12 hours. The matte 14-inch IPS display is easy on the eyes. This is what every Linux laptop should aspire to be.',
                'machine': 'HP Dev One', 'distro': 'Pop!_OS 22.04',
                'boot_status': 'GOLD', 'kernel_version': '6.6.10', 'user': 'archmaster',
                'comp_statuses': [('Intel AX211', 'WORKING', 'Perfect WiFi since day one'), ('Realtek ALC289', 'WORKING', 'All audio paths work'), ('Goodix Fingerprint USB', 'WORKING', 'Works with fprintd out of the box')],
                'comments': [('newbie99', 'Is this still available to buy? Looks perfect for my first Linux laptop.')],
            },
            {
                'title': 'System76 Lemur Pro on Ubuntu 22.04 — Solid workhorse',
                'description': 'Running Ubuntu 22.04 LTS on the System76 Lemur Pro. As expected from System76, everything works out of the box with their firmware updates. The battery life is the standout feature — consistently getting 12+ hours. The Intel Iris Xe handles daily tasks well. WiFi is stable. The keyboard is decent for a thin laptop. Only downside is the 1080p display could be sharper.',
                'machine': 'System76 Lemur Pro', 'distro': 'Ubuntu 22.04',
                'boot_status': 'GOLD', 'kernel_version': '5.15.0-91', 'user': 'tuxlover',
                'comp_statuses': [('Intel AX211', 'WORKING', 'Rock solid'), ('Realtek ALC295', 'WORKING', 'Audio works well')],
                'comments': [('kernelhacker', 'System76 always delivers. Their firmware updates through LVFS are great.')],
            },
            {
                'title': 'ThinkPad T14s Gen 4 AMD on Fedora 41 — Near perfect',
                'description': 'Fedora 41 on the ThinkPad T14s Gen 4 AMD. The Ryzen 7 Pro 7840U is a beast — fast compilation times and excellent battery life. WiFi works, audio works, trackpoint works. The fingerprint reader needed a firmware update via fwupd but works after that. Display is crisp at 1920x1200. Thunderbolt docking works for external monitors. One minor issue: the IR camera does not work for facial recognition under Linux.',
                'machine': 'Lenovo T14s Gen 4 AMD', 'distro': 'Fedora 41',
                'boot_status': 'GOLD', 'kernel_version': '6.11.0', 'user': 'kernelhacker',
                'comp_statuses': [('MediaTek MT7922', 'WORKING', 'WiFi 6E stable'), ('Realtek ALC295', 'WORKING', 'All audio outputs OK'), ('Intel Thunderbolt 4', 'WORKING', 'Docking station works perfectly')],
                'comments': [('archmaster', 'The T14s is my daily driver too. Absolutely love it.')],
            },
            {
                'title': 'MacBook Pro M3 Pro on Fedora 41 via Asahi — Brave new world',
                'description': 'Running Fedora 41 via Asahi Linux on the MacBook Pro M3 Pro. The Apple GPU support is improving rapidly. Display works at native resolution. WiFi works. Audio works through speakers. Thunderbolt works for external displays. Battery life is around 8 hours which is good but not as good as macOS. The main limitation is GPU acceleration — no Vulkan yet, but OpenGL works for basic tasks. This is a technology preview more than a daily driver.',
                'machine': 'Apple M3 Pro 14', 'distro': 'Fedora 41',
                'boot_status': 'BRONZE', 'kernel_version': '6.11.0', 'user': 'archmaster',
                'comp_statuses': [('AMD Radeon 780M', 'ISSUES', 'Apple GPU: OpenGL works, no Vulkan yet'), ('Intel AX211', 'WORKING', 'Broadcom WiFi works via Asahi patches')],
                'comments': [('kernelhacker', 'Asahi Linux is doing incredible work. Vulkan support is coming.')],
            },
            {
                'title': 'IdeaPad Slim 5 Gen 8 on Linux Mint 21.3 — Budget champion',
                'description': 'Linux Mint 21.3 Virginia on the Lenovo IdeaPad Slim 5 Gen 8. This budget laptop runs Linux beautifully. The Ryzen 5 7530U handles daily tasks, web browsing, and light development well. WiFi works out of the box. Audio is fine. The 16-inch 1920x1200 display is nice for the price. Battery life is about 7 hours. The DDR4 RAM is the only downside — DDR5 would be preferred. Great value for money.',
                'machine': 'Lenovo Slim 5 Gen 8', 'distro': 'Linux Mint 21.3 Virginia',
                'boot_status': 'GOLD', 'kernel_version': '5.15.0', 'user': 'newbie99',
                'comp_statuses': [('Intel AX211', 'WORKING', 'WiFi stable'), ('Realtek ALC295', 'WORKING', 'Sound works fine'), ('BOE NE160QDM-NX1', 'WORKING', 'Display looks great')],
                'comments': [('tuxlover', 'Great choice for a first Linux laptop! Mint makes everything easy.')],
            },
            {
                'title': 'Beelink SER6 Pro on Debian 12 — Perfect home server',
                'description': 'Running Debian 12 Bookworm on the Beelink SER6 Pro mini PC as a home server. The Ryzen 7 6800H is overkill for server duties but handles Docker containers, Plex, and Home Assistant effortlessly. Installed headless with SSH. Ethernet works with the Realtek driver. WiFi works but using wired connection for stability. Power consumption is around 15W idle. Fantastic mini PC for Linux.',
                'machine': 'Beelink SER6 Pro', 'distro': 'Debian 12 Bookworm',
                'boot_status': 'GOLD', 'kernel_version': '6.1.0', 'user': 'kernelhacker',
                'comp_statuses': [('Intel I219-V', 'WORKING', 'Ethernet rock solid for server use'), ('Intel AX211', 'WORKING', 'WiFi works but using wired')],
                'comments': [('archmaster', 'What Docker containers are you running on it?')],
            },
            {
                'title': 'Custom AMD Build on Arch Linux — Desktop powerhouse',
                'description': 'Full custom desktop with Ryzen 9 7950X and RX 7900 XTX running Arch Linux. The AMDGPU driver handles the 7900 XTX well for both gaming and compute workloads. Running Wayland with Hyprland compositor. Steam Proton gaming performance is excellent — most AAA titles run at native-like performance. The NVMe Gen 4 SSD benchmarks at 7GB/s read. Audio via USB DAC works perfectly with PipeWire.',
                'machine': 'Custom AMD Build', 'distro': 'Arch Linux Rolling',
                'boot_status': 'GOLD', 'kernel_version': '6.10.0', 'user': 'archmaster',
                'comp_statuses': [('AMD Radeon RX 7600S', 'WORKING', 'RX 7900 XTX: AMDGPU works perfectly for gaming and compute'), ('WD Black SN850X', 'WORKING', 'Full speed NVMe performance'), ('Samsung PM9A1 NVMe', 'WORKING', 'Secondary drive, works great')],
                'comments': [('tuxlover', 'What FPS are you getting in Cyberpunk with Proton?'), ('archmaster', 'Around 80-100fps at 1440p with FSR enabled.')],
            },
            {
                'title': 'Dell XPS 15 9530 on openSUSE Tumbleweed — Rolling with NVIDIA',
                'description': 'openSUSE Tumbleweed on the XPS 15 with NVIDIA RTX 4060. NVIDIA drivers available via the official openSUSE repo. Hybrid graphics work with prime-run. The rolling nature of Tumbleweed means always having the latest drivers. KDE Plasma 6 looks stunning on the OLED display. WiFi and audio work. The only annoyance is occasional breakage after big updates, but snapper rollback saves the day.',
                'machine': 'Dell 15 9530', 'distro': 'openSUSE Tumbleweed Rolling',
                'boot_status': 'SILVER', 'kernel_version': '6.9.0', 'user': 'tuxlover',
                'comp_statuses': [('NVIDIA RTX 4060', 'ISSUES', 'Works but needs manual driver setup after kernel updates'), ('Intel AX211', 'WORKING', 'No issues'), ('Realtek ALC289', 'WORKING', 'Audio works well via PipeWire')],
                'comments': [('kernelhacker', 'Tumbleweed + snapper is an underrated combo for NVIDIA users.')],
            },
            {
                'title': 'Framework 13 AMD on NixOS 24.05 — Declarative hardware',
                'description': 'NixOS 24.05 on the Framework 13 AMD. The declarative configuration makes hardware setup reproducible. WiFi module (MT7922) is configured in hardware-configuration.nix. All hardware works with the right kernel modules declared. The beauty of NixOS is rolling back if something breaks. Fingerprint reader works after adding fprintd to services. Battery optimization via TLP configured declaratively.',
                'machine': 'Framework 13 AMD', 'distro': 'NixOS 24.05',
                'boot_status': 'GOLD', 'kernel_version': '6.6.0', 'user': 'kernelhacker',
                'comp_statuses': [('MediaTek MT7922', 'WORKING', 'Declared in hardware-configuration.nix'), ('AMD Radeon 780M', 'WORKING', 'AMDGPU works declaratively'), ('Realtek ALC295', 'WORKING', 'PipeWire configured in NixOS')],
                'comments': [('archmaster', 'NixOS on Framework is chef\'s kiss. Reproducible hardware config is the future.')],
            },
            {
                'title': 'ASUS ROG G14 2024 on Fedora 41 — Better with newer kernel',
                'description': 'Updated to Fedora 41 on the ROG G14 2024 and the experience improved significantly over Ubuntu. The newer kernel (6.11) has better RDNA3 support. Screen flickering is gone. The RX 7600S now works well for gaming with Proton. asusctl for keyboard LEDs and power profiles works out of the box on Fedora. Suspend/resume is fast and reliable. Battery life improved to 7 hours with power-profiles-daemon.',
                'machine': 'ASUS Zephyrus G14 2024', 'distro': 'Fedora 41',
                'boot_status': 'GOLD', 'kernel_version': '6.11.0', 'user': 'archmaster',
                'comp_statuses': [('AMD Radeon RX 7600S', 'WORKING', 'Kernel 6.11 fixed the flickering'), ('Qualcomm WCN785x', 'WORKING', 'WiFi 7 solid'), ('Realtek ALC289', 'WORKING', 'Audio works perfectly')],
                'comments': [('tuxlover', 'Glad to hear the flickering is fixed! Updating my G14 now.')],
            },
        ]

        reports = []
        for rd in report_data:
            # Find machine
            machine = None
            for key, m in machines.items():
                parts = rd['machine'].split(' ', 1)
                if len(parts) >= 2 and parts[0] in key and parts[1] in key:
                    machine = m
                    break
            if not machine:
                for key, m in machines.items():
                    if any(p in key for p in rd['machine'].split()):
                        machine = m
                        break

            # Find distro
            distro = distros.get(rd['distro'])

            if not machine or not distro:
                self.stdout.write(self.style.WARNING(f"    Skipping report: {rd['title']} (machine={machine}, distro={distro})"))
                continue

            user = users[rd['user']]
            report, created = Report.objects.get_or_create(
                title=rd['title'],
                defaults={
                    'user': user, 'machine': machine, 'distro': distro,
                    'report_type': 'MACHINE_DISTRO', 'description': rd['description'],
                    'boot_status': rd['boot_status'], 'kernel_version': rd['kernel_version'],
                    'status': 'APPROVED',
                }
            )
            reports.append(report)

            if created:
                # Create comp statuses
                for comp_name, status, notes in rd.get('comp_statuses', []):
                    comp = components.get(comp_name)
                    if comp:
                        CompStatus.objects.get_or_create(
                            report=report, component=comp,
                            defaults={'status': status, 'notes': notes}
                        )

                # Create comments
                for commenter_name, content in rd.get('comments', []):
                    commenter = users.get(commenter_name)
                    if commenter:
                        Comment.objects.get_or_create(
                            user=commenter, report=report,
                            defaults={'content': content}
                        )

        return reports

    def _seed_driver_fixes(self, users, components):
        self.stdout.write('  Creating driver fixes...')
        fix_data = [
            {
                'component': 'NVIDIA RTX 4060',
                'title': 'NVIDIA proprietary driver on Fedora',
                'body': 'Run: sudo dnf install akmod-nvidia\nReboot after install completes.\nFor CUDA support: sudo dnf install xorg-x11-drv-nvidia-cuda',
                'external_url': 'https://rpmfusion.org/Howto/NVIDIA',
                'user': 'kernelhacker',
            },
            {
                'component': 'MediaTek MT7922',
                'title': 'Fix random disconnects on MT7922',
                'body': 'Add to /etc/modprobe.d/mt7921.conf:\noptions mt7921e disable_clc=1\nThen: sudo modprobe -r mt7921e && sudo modprobe mt7921e',
                'user': 'archmaster',
            },
            {
                'component': 'AMD Radeon RX 7600S',
                'title': 'AMD GPU power management on laptops',
                'body': 'Add kernel parameter: amdgpu.ppfeaturemask=0xffffffff\nEdit /etc/default/grub and run grub-update.\nThis enables full power management control for better battery life.',
                'user': 'kernelhacker',
            },
        ]
        for fd in fix_data:
            comp = components.get(fd['component'])
            user = users.get(fd['user'])
            if comp and user:
                DriverFix.objects.get_or_create(
                    component=comp, title=fd['title'],
                    defaults={
                        'submitted_by': user,
                        'body': fd['body'],
                        'external_url': fd.get('external_url'),
                        'status': 'ACCEPTED',
                    }
                )
