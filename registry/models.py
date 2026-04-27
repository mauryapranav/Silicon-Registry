"""
registry/models.py — Silicon Registry
======================================

ARCHITECTURE DECISIONS (read before modifying):

Decision 1 — Single Flexible Report Table:
    The Report model uses a report_type field + nullable FKs instead of separate
    MachineReport, ComponentReport, DistroReport tables. This keeps Vote, Flag,
    Comment, Benchmark, and Attachment tables linked to ONE table instead of five,
    avoiding severe join complexity. Only 3 nullable FK columns exist (machine,
    distro, component). A clean() method enforces valid FK combinations per
    report_type at model level.

Decision 2 — Trust Score Storage:
    User trust uses two IntegerField columns: positive_score and negative_score.
    trust_ratio is a computed @property. A TrustEvent table logs every change
    with full audit trail. Mod-rejection penalties require mod_penalty_approved=True
    on TrustEvent before points deduct — this prevents unfair score drops from
    rejections due to incomplete info rather than malicious intent.
    Users with trust_ratio < 30% have new reports auto-defaulted to PENDING.

Decision 3 — Generic Voting and Flagging via ContentTypes:
    Vote and Flag use Django GenericForeignKey so they work across both Report
    and Comment without duplicating tables. django.contrib.contenttypes must
    be in INSTALLED_APPS.

Decision 4 — Compatibility Score Field:
    compatibility_score is a stubbed FloatField on Report. It is null=True,
    blank=True and MUST NOT be filled by users or any write serializer.
    Reserved exclusively for a future AI integration phase.
"""

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


# =============================================================================
# Model 1 — User
# =============================================================================

class User(AbstractUser):
    """
    Custom user model extending AbstractUser.

    Must be set as AUTH_USER_MODEL in settings.py BEFORE any migration is run.
    trust_ratio and needs_moderation are computed properties — never stored.
    github_username is populated by django-allauth on OAuth login.
    """

    class RoleType(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        MAINTAINER = 'MAINTAINER', 'Maintainer'
        CONTRIBUTOR = 'CONTRIBUTOR', 'Contributor'

    role_type = models.CharField(
        max_length=20,
        choices=RoleType.choices,
        default=RoleType.CONTRIBUTOR,
    )
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    positive_score = models.IntegerField(default=0)
    negative_score = models.IntegerField(default=0)
    is_verified = models.BooleanField(
        default=False,
        help_text="User account credibility badge awarded by maintainers.",
    )
    github_username = models.CharField(max_length=100, blank=True)

    @property
    def trust_ratio(self):
        """Returns trust as a percentage: positive / (positive + negative) * 100."""
        return round(
            self.positive_score / max(self.positive_score + self.negative_score, 1) * 100,
            1,
        )

    @property
    def needs_moderation(self):
        """True when trust_ratio < 30 — new reports from this user go to PENDING."""
        return self.trust_ratio < 30

    def __str__(self):
        return self.username

    class Meta:
        ordering = ['username']
        verbose_name_plural = 'Users'


# =============================================================================
# Model 2 — Machine
# =============================================================================

class Machine(models.Model):
    """
    Represents a specific laptop/desktop hardware model.
    unique_together on (vendor, series, model_name) prevents duplicates while
    allowing the same model_name to exist under a different vendor or series.
    """

    class FormFactor(models.TextChoices):
        LAPTOP    = 'LAPTOP',    'Laptop'
        DESKTOP   = 'DESKTOP',   'Desktop'
        MINI_PC   = 'MINI_PC',   'Mini PC'
        HANDHELD  = 'HANDHELD',  'Handheld'
        ALL_IN_ONE = 'ALL_IN_ONE', 'All-in-One'

    vendor = models.CharField(max_length=100)
    series = models.CharField(max_length=100)
    model_name = models.CharField(max_length=200)
    cpu_family = models.CharField(max_length=100)
    form_factor = models.CharField(
        max_length=20,
        choices=FormFactor.choices,
        null=True,
        blank=True
    )
    slug = models.SlugField(max_length=300, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.vendor}-{self.series}-{self.model_name}")
            slug = base_slug
            counter = 2
            while Machine.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.vendor} {self.series} {self.model_name}"

    class Meta:
        ordering = ['vendor', 'series', 'model_name']
        unique_together = [['vendor', 'series', 'model_name']]
        verbose_name_plural = 'Machines'
        indexes = [
            models.Index(fields=['vendor']),
            models.Index(fields=['form_factor']),
        ]


# =============================================================================
# Model 3 — Distro
# =============================================================================

class Distro(models.Model):
    """
    A Linux distribution + version combination.
    kernel_default represents the kernel shipped by default with this release.
    Reports may override this via Report.kernel_version when users run custom kernels.
    """

    name = models.CharField(max_length=100)
    version = models.CharField(max_length=50)
    kernel_default = models.CharField(max_length=100, blank=True, null=True)
    release_date = models.DateField(null=True, blank=True)
    eol_date = models.DateField(null=True, blank=True, help_text='End of life date')
    is_rolling = models.BooleanField(default=False, help_text='Rolling release e.g. Arch')
    is_lts = models.BooleanField(default=False, help_text='Long-term support release')
    based_on = models.CharField(max_length=50, null=True, blank=True, help_text='e.g. Debian, Arch')
    desktop_default = models.CharField(max_length=50, null=True, blank=True, help_text='Default DE e.g. GNOME')
    website_url = models.URLField(null=True, blank=True)
    slug = models.SlugField(max_length=150, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.name}-{self.version}")
            slug = base_slug
            counter = 2
            while Distro.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} {self.version}"

    class Meta:
        ordering = ['name', 'version']
        unique_together = [['name', 'version']]
        verbose_name_plural = 'Distros'


# =============================================================================
# Model 4 — Component
# =============================================================================

class Component(models.Model):
    """
    A hardware component category + specific product name.
    unique_together on (type, name) prevents duplicate entries for the same
    component variant (e.g. two entries for "Wi-Fi 6E AX210" under WIFI).
    """

    class ComponentType(models.TextChoices):
        WIFI        = 'WIFI',        'WiFi'
        AUDIO       = 'AUDIO',       'Audio'
        GPU         = 'GPU',         'GPU'
        BLUETOOTH   = 'BLUETOOTH',   'Bluetooth'
        INPUT       = 'INPUT',       'Input device'
        STORAGE     = 'STORAGE',     'Storage (SSD/HDD/NVMe)'
        DISPLAY     = 'DISPLAY',     'Display / Screen'
        FINGERPRINT = 'FINGERPRINT', 'Fingerprint reader'
        WEBCAM      = 'WEBCAM',      'Webcam / Camera'
        THUNDERBOLT = 'THUNDERBOLT', 'Thunderbolt / USB4'
        ETHERNET    = 'ETHERNET',    'Ethernet / LAN'
        CELLULAR    = 'CELLULAR',    'Cellular / WWAN / 5G'
        USB_C       = 'USB_C',       'USB-C / Power delivery'

    type = models.CharField(max_length=20, choices=ComponentType.choices)
    name = models.CharField(max_length=200)
    driver = models.CharField(max_length=200, blank=True, null=True)
    slug = models.SlugField(max_length=300, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.get_type_display()}-{self.name}")
            slug = base_slug
            counter = 2
            while Component.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_type_display()} — {self.name}"

    class Meta:
        ordering = ['type', 'name']
        unique_together = [['type', 'name']]
        verbose_name_plural = 'Components'
        indexes = [
            models.Index(fields=['type']),
        ]


# =============================================================================
# Model 5 — Report  (Central flexible entity)
# =============================================================================

class Report(models.Model):
    """
    Central entity for all hardware compatibility reports.

    See Decision 1 at the top of this file for why this is a single flexible
    table rather than separate MachineReport / ComponentReport / DistroReport.

    FK rules enforced by clean():
        MACHINE_DISTRO    → machine + distro required
        MACHINE_COMPONENT → machine + component required
        COMPONENT_DISTRO  → component + distro required
        COMPONENT_ONLY    → component only; machine + distro must be null
        MACHINE_ONLY      → machine only; distro + component must be null

    save() forces status=PENDING when the submitting user has needs_moderation=True.

    compatibility_score is RESERVED for AI integration — never expose in write
    serializers or user-facing forms (see Decision 4).
    """

    class ReportType(models.TextChoices):
        MACHINE_DISTRO = 'MACHINE_DISTRO', 'Machine + Distro'
        MACHINE_COMPONENT = 'MACHINE_COMPONENT', 'Machine + Component'
        COMPONENT_DISTRO = 'COMPONENT_DISTRO', 'Component + Distro'
        COMPONENT_ONLY = 'COMPONENT_ONLY', 'Component Only'
        MACHINE_ONLY = 'MACHINE_ONLY', 'Machine Only'

    class BootStatus(models.TextChoices):
        GOLD = 'GOLD', 'Gold — Everything works out of the box'
        SILVER = 'SILVER', 'Silver — Most things work, minor issues'
        BRONZE = 'BRONZE', 'Bronze — Usable with significant workarounds'
        BROKEN = 'BROKEN', 'Broken — Does not boot or unusable'

    class ModerationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports',
        help_text="SET_NULL so community reports survive account deletion.",
    )
    machine = models.ForeignKey(
        'Machine',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports',
    )
    distro = models.ForeignKey(
        'Distro',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports',
    )
    component = models.ForeignKey(
        'Component',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports',
    )
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField()
    boot_status = models.CharField(
        max_length=10,
        choices=BootStatus.choices,
        null=True,
        blank=True,
        help_text="Only applicable for MACHINE_DISTRO and MACHINE_ONLY report types.",
    )
    kernel_version = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="e.g. 6.8.0-45 — override if user ran a non-default kernel.",
    )
    status = models.CharField(
        max_length=10,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
    )
    compatibility_score = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "RESERVED: Do not populate manually. "
            "This field is reserved for future AI-powered compatibility assessment."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Generic relations for voting and flagging
    votes = GenericRelation('Vote', related_query_name='report')
    flags = GenericRelation('Flag', related_query_name='report')

    def clean(self):
        rt = self.report_type
        has_machine = self.machine is not None
        has_distro = self.distro is not None
        has_component = self.component is not None

        if rt == self.ReportType.MACHINE_DISTRO:
            if not has_machine or not has_distro:
                raise ValidationError(
                    "MACHINE_DISTRO reports require both machine and distro."
                )
        elif rt == self.ReportType.MACHINE_COMPONENT:
            if not has_machine or not has_component:
                raise ValidationError(
                    "MACHINE_COMPONENT reports require both machine and component."
                )
        elif rt == self.ReportType.COMPONENT_DISTRO:
            if not has_component or not has_distro:
                raise ValidationError(
                    "COMPONENT_DISTRO reports require both component and distro."
                )
        elif rt == self.ReportType.COMPONENT_ONLY:
            if not has_component:
                raise ValidationError(
                    "COMPONENT_ONLY reports require a component."
                )
            if has_machine or has_distro:
                raise ValidationError(
                    "COMPONENT_ONLY reports must not have a machine or distro."
                )
        elif rt == self.ReportType.MACHINE_ONLY:
            if not has_machine:
                raise ValidationError(
                    "MACHINE_ONLY reports require a machine."
                )
            if has_distro or has_component:
                raise ValidationError(
                    "MACHINE_ONLY reports must not have a distro or component."
                )

    def save(self, *args, **kwargs):
        # Decision 2: Low-trust users always get PENDING status regardless of input.
        if self.user and self.user.needs_moderation:
            self.status = self.ModerationStatus.PENDING
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.report_type}] {self.title} by {self.user}"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Reports'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['boot_status']),
            models.Index(fields=['report_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'boot_status']),
            models.Index(fields=['user', 'status']),
        ]


# =============================================================================
# Model 6 — CompStatus
# =============================================================================

class CompStatus(models.Model):
    """
    Per-component working status within a single Report.
    Allows a machine report to list multiple components (GPU, Wi-Fi, Audio, etc.)
    each with its own status, rather than requiring separate reports per component.
    unique_together prevents duplicate component entries per report.
    """

    class ComponentStatus(models.TextChoices):
        WORKING = 'WORKING', 'Working'
        ISSUES = 'ISSUES', 'Has Issues'
        BROKEN = 'BROKEN', 'Broken'

    report = models.ForeignKey(
        'Report',
        on_delete=models.CASCADE,
        related_name='comp_statuses',
    )
    component = models.ForeignKey(
        'Component',
        on_delete=models.CASCADE,
        related_name='comp_statuses',
    )
    status = models.CharField(max_length=10, choices=ComponentStatus.choices)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.component.name} on Report #{self.report.id} — {self.status}"

    class Meta:
        ordering = ['component__type', 'component__name']
        unique_together = [['report', 'component']]
        verbose_name_plural = 'Component Statuses'
        indexes = [
            models.Index(fields=['component', 'status']),
            models.Index(fields=['report', 'component']),
        ]


# =============================================================================
# Model 7 — Comment
# =============================================================================

class Comment(models.Model):
    """
    Community comments attached to a Report.
    user is SET_NULL so comments survive account deletion (community content).
    is_verified can be set by maintainers to highlight accurate/helpful comments.
    Supports generic votes via the Vote model (Decision 3).
    """

    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='comments',
    )
    report = models.ForeignKey(
        'Report',
        on_delete=models.CASCADE,
        related_name='comments',
    )
    content = models.TextField()
    is_verified = models.BooleanField(
        default=False,
        help_text="Maintainer-verified accuracy badge.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Generic relations for voting and flagging
    votes = GenericRelation('Vote', related_query_name='comment')
    flags = GenericRelation('Flag', related_query_name='comment')

    def __str__(self):
        return f"Comment by {self.user} on Report #{self.report.id}"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Comments'


# =============================================================================
# Model 8 — Vote  (Generic — works on Report and Comment)
# =============================================================================

class Vote(models.Model):
    """
    Generic vote attached to any model via ContentTypes (Decision 3).
    unique_together on (user, content_type, object_id) enforces one vote per
    user per object — this works correctly across both Report and Comment.

    To vote on a Report:
        Vote.objects.create(
            user=request.user,
            content_object=report_instance,
            vote_type=Vote.VoteType.UPVOTE,
        )
    """

    class VoteType(models.TextChoices):
        UPVOTE = 'UPVOTE', 'Upvote'
        DOWNVOTE = 'DOWNVOTE', 'Downvote'
        HELPFUL = 'HELPFUL', 'Helpful'
        NOT_HELPFUL = 'NOT_HELPFUL', 'Not Helpful'

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='votes',
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    vote_type = models.CharField(max_length=15, choices=VoteType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.vote_type}"

    class Meta:
        ordering = ['-created_at']
        unique_together = [['user', 'content_type', 'object_id']]
        verbose_name_plural = 'Votes'


# =============================================================================
# Model 9 — Flag  (Generic — works on Report and Comment)
# =============================================================================

class Flag(models.Model):
    """
    Generic flag for community moderation (Decision 3).
    user is SET_NULL so flags survive account deletion — mod review history
    must not be lost because a user deleted their account.
    reviewed_by tracks which moderator acted on the flag.
    mod_notes captures reasoning for the moderation decision.
    """

    class FlagReason(models.TextChoices):
        SPAM = 'SPAM', 'Spam'
        INCORRECT = 'INCORRECT', 'Incorrect Information'
        MISLEADING = 'MISLEADING', 'Misleading'
        DUPLICATE = 'DUPLICATE', 'Duplicate'
        OTHER = 'OTHER', 'Other'

    class FlagStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        REVIEWED = 'REVIEWED', 'Reviewed'
        DISMISSED = 'DISMISSED', 'Dismissed'

    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='flags',
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    reason = models.CharField(max_length=15, choices=FlagReason.choices)
    details = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=10,
        choices=FlagStatus.choices,
        default=FlagStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_flags',
    )
    mod_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Flag [{self.reason}] by {self.user} — {self.status}"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Flags'


# =============================================================================
# Model 10 — Benchmark
# =============================================================================

class Benchmark(models.Model):
    """
    Optional performance metrics attached to a Report.
    All measurement fields are nullable — contributors provide what they can.
    suspend_resume_pass is a boolean test result (did it work at all?).
    suspend_resume_seconds measures resume latency when it does work.
    """

    report = models.ForeignKey(
        'Report',
        on_delete=models.CASCADE,
        related_name='benchmarks',
    )
    battery_life_hours = models.FloatField(null=True, blank=True)
    power_draw_watts = models.FloatField(null=True, blank=True)
    cpu_score = models.IntegerField(null=True, blank=True)
    gpu_score = models.IntegerField(null=True, blank=True)
    suspend_resume_pass = models.BooleanField(null=True, blank=True)
    suspend_resume_seconds = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Benchmark for Report #{self.report.id}"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Benchmarks'


# =============================================================================
# Model 11 — DriverFix
# =============================================================================

class DriverFix(models.Model):
    """
    Community-submitted driver fix or workaround for a Component.
    submitted_by is SET_NULL so fixes survive contributor account deletion.
    reviewed_by is SET_NULL for the same reason.
    status tracks the moderation lifecycle: PENDING → ACCEPTED or REJECTED.
    Accepted fixes can be linked to HelpGroups via HelpGroup.driver_fixes M2M.
    """

    class FixStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'

    component = models.ForeignKey(
        'Component',
        on_delete=models.CASCADE,
        related_name='driver_fixes',
    )
    submitted_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='driver_fixes',
    )
    title = models.CharField(max_length=200)
    body = models.TextField(
        help_text="Fix commands, terminal instructions, workarounds.",
    )
    external_url = models.URLField(blank=True, null=True)
    status = models.CharField(
        max_length=10,
        choices=FixStatus.choices,
        default=FixStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_fixes',
    )
    mod_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Fix for {self.component.name} — {self.title} [{self.status}]"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Driver Fixes'


# =============================================================================
# Model 12 — TrustEvent
# =============================================================================

class TrustEvent(models.Model):
    """
    Immutable audit log for every trust score change (Decision 2).

    IMPORTANT — mod_penalty_approved flag:
        Any event_type containing PENALTY must have mod_penalty_approved=True
        before the corresponding User.negative_score is incremented.
        A Django signal should listen for mod_penalty_approved transitioning
        to True and then update User.negative_score += abs(points_delta).
        This prevents unfair score drops from rejections due to incomplete
        information rather than malicious intent.

    points_delta should be positive for beneficial events, negative for penalties.
    CASCADE on user intentionally — if a user is deleted, their audit trail
    loses meaning. Admin should soft-delete or deactivate users instead.
    """

    class EventType(models.TextChoices):
        REPORT_UPVOTED = 'REPORT_UPVOTED', 'Report Upvoted'
        REPORT_DOWNVOTED = 'REPORT_DOWNVOTED', 'Report Downvoted'
        REPORT_APPROVED = 'REPORT_APPROVED', 'Report Approved'
        REPORT_REJECTED_PENALTY = 'REPORT_REJECTED_PENALTY', 'Report Rejected (Penalty)'
        COMMENT_VERIFIED = 'COMMENT_VERIFIED', 'Comment Verified'
        COMMENT_DOWNVOTED = 'COMMENT_DOWNVOTED', 'Comment Downvoted'
        COMMENT_FLAGGED_CONFIRMED = 'COMMENT_FLAGGED_CONFIRMED', 'Comment Flag Confirmed'
        DRIVER_FIX_ACCEPTED = 'DRIVER_FIX_ACCEPTED', 'Driver Fix Accepted'
        DRIVER_FIX_REJECTED_PENALTY = 'DRIVER_FIX_REJECTED_PENALTY', 'Driver Fix Rejected (Penalty)'

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='trust_events',
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    points_delta = models.IntegerField(
        help_text="Positive for gains, negative for penalties.",
    )
    mod_penalty_approved = models.BooleanField(
        default=False,
        help_text=(
            "Must be True for any PENALTY event before negative_score is updated. "
            "A signal listens for this transitioning to True and applies the deduction."
        ),
    )
    approved_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_trust_events',
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TrustEvent: {self.event_type} for {self.user} ({self.points_delta:+d})"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Trust Events'
        indexes = [
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['mod_penalty_approved']),
        ]


# =============================================================================
# Model 13 — ReportAttachment
# =============================================================================

class ReportAttachment(models.Model):
    """
    Files attached to a Report — screenshots, dmesg logs, config files.
    Files are stored under MEDIA_ROOT/report_attachments/YYYY/MM/.
    original_filename preserves the uploader's filename for display purposes
    (Django may rename files on disk to avoid collisions).
    """

    class FileType(models.TextChoices):
        IMAGE = 'IMAGE', 'Image'
        LOG = 'LOG', 'Log File'
        CONFIG = 'CONFIG', 'Config File'

    report = models.ForeignKey(
        'Report',
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='report_attachments/%Y/%m/')
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.file_type}] Attachment for Report #{self.report.id}"

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name_plural = 'Report Attachments'


# =============================================================================
# Model 14 — HelpGroup
# =============================================================================

class HelpGroup(models.Model):
    """
    A moderated support thread for a broken component+distro combination.
    Suggested automatically when many users share the same problem;
    a maintainer approves to promote it to OPEN.
    driver_fixes is a M2M to link accepted workarounds into the group.
    created_by is SET_NULL so groups survive account deletion.
    """

    class GroupStatus(models.TextChoices):
        SUGGESTED = 'SUGGESTED', 'Suggested'
        OPEN = 'OPEN', 'Open'
        RESOLVED = 'RESOLVED', 'Resolved'

    title = models.CharField(max_length=200)
    description = models.TextField()
    component = models.ForeignKey(
        'Component',
        on_delete=models.CASCADE,
        related_name='help_groups',
    )
    distro = models.ForeignKey(
        'Distro',
        on_delete=models.CASCADE,
        related_name='help_groups',
    )
    status = models.CharField(
        max_length=10,
        choices=GroupStatus.choices,
        default=GroupStatus.SUGGESTED,
    )
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_help_groups',
    )
    driver_fixes = models.ManyToManyField(
        'DriverFix',
        blank=True,
        related_name='help_groups',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"HelpGroup: {self.title} [{self.status}]"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Help Groups'


# =============================================================================
# Model 15 — HelpGroupMembership
# =============================================================================

class HelpGroupMembership(models.Model):
    """
    Tracks which users are members of a HelpGroup and how they joined.
    CASCADE on both FKs — membership records have no meaning without
    both the group and the user.
    unique_together prevents duplicate memberships.
    """

    class InviteStatus(models.TextChoices):
        INVITED = 'INVITED', 'Invited'
        REQUESTED = 'REQUESTED', 'Requested'
        ACCEPTED = 'ACCEPTED', 'Accepted'

    group = models.ForeignKey(
        'HelpGroup',
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='help_group_memberships',
    )
    invite_status = models.CharField(max_length=10, choices=InviteStatus.choices)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} in '{self.group.title}' — {self.invite_status}"

    class Meta:
        ordering = ['-joined_at']
        unique_together = [['group', 'user']]
        verbose_name_plural = 'Help Group Memberships'


# =============================================================================
# Model 16 — HelpGroupMessage
# =============================================================================

class HelpGroupMessage(models.Model):
    """
    Chat-style messages inside a HelpGroup thread.
    Ordered oldest-first (ascending created_at) to read like a conversation.
    user is SET_NULL so message history survives account deletion.
    """

    group = models.ForeignKey(
        'HelpGroup',
        on_delete=models.CASCADE,
        related_name='messages',
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='help_group_messages',
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message by {self.user} in '{self.group.title}'"

    class Meta:
        ordering = ['created_at']
        verbose_name_plural = 'Help Group Messages'


# =============================================================================
# Model 17 — UserMachine  (User's owned hardware)
# =============================================================================

class UserMachine(models.Model):
    """
    Links a User to Machine(s) they personally own.
    CASCADE on both FKs — the ownership record is meaningless without
    both the user and the machine.
    unique_together prevents a user adding the same machine twice.
    """

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='user_machines',
    )
    machine = models.ForeignKey(
        'Machine',
        on_delete=models.CASCADE,
        related_name='user_machines',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} owns {self.machine}"

    class Meta:
        ordering = ['-added_at']
        unique_together = [['user', 'machine']]
        verbose_name_plural = 'User Machines'


# =============================================================================
# Model 18 — MachineSpec
# =============================================================================

class MachineSpec(models.Model):

    machine = models.OneToOneField(
        'Machine', on_delete=models.CASCADE, related_name='spec'
    )

    # CPU
    class CPUManufacturer(models.TextChoices):
        INTEL    = 'INTEL',    'Intel'
        AMD      = 'AMD',      'AMD'
        APPLE    = 'APPLE',    'Apple'
        QUALCOMM = 'QUALCOMM', 'Qualcomm'

    class CPUSeriesTier(models.TextChoices):
        U        = 'U',        'U Series (ultra-low power)'
        P        = 'P',        'P Series (performance)'
        H        = 'H',        'H Series (high performance)'
        HX       = 'HX',       'HX Series (extreme)'
        X        = 'X',        'X Series (workstation)'
        STANDARD = 'STANDARD', 'Standard (desktop / no tier)'

    cpu_name         = models.CharField(max_length=100, null=True, blank=True, help_text="e.g. Core i7-1365U")
    cpu_manufacturer = models.CharField(max_length=20, choices=CPUManufacturer.choices, null=True, blank=True)
    cpu_generation   = models.CharField(max_length=50, null=True, blank=True, help_text="e.g. 13th Gen, Zen 4")
    cpu_series_tier  = models.CharField(max_length=10, choices=CPUSeriesTier.choices, null=True, blank=True)

    # GPU
    class GPUManufacturer(models.TextChoices):
        NVIDIA = 'NVIDIA', 'NVIDIA'
        AMD    = 'AMD',    'AMD'
        INTEL  = 'INTEL',  'Intel'
        APPLE  = 'APPLE',  'Apple'

    class GPUType(models.TextChoices):
        DEDICATED  = 'DEDICATED',  'Dedicated'
        INTEGRATED = 'INTEGRATED', 'Integrated'

    gpu_name         = models.CharField(max_length=100, null=True, blank=True, help_text="e.g. RTX 4060, Radeon 780M")
    gpu_manufacturer = models.CharField(max_length=10, choices=GPUManufacturer.choices, null=True, blank=True)
    gpu_generation   = models.CharField(max_length=50, null=True, blank=True, help_text="e.g. Ada Lovelace, RDNA 3")
    gpu_type         = models.CharField(max_length=15, choices=GPUType.choices, null=True, blank=True)

    # RAM
    class RAMType(models.TextChoices):
        DDR4    = 'DDR4',    'DDR4'
        DDR5    = 'DDR5',    'DDR5'
        LPDDR4  = 'LPDDR4',  'LPDDR4'
        LPDDR4X = 'LPDDR4X', 'LPDDR4X'
        LPDDR5  = 'LPDDR5',  'LPDDR5'
        LPDDR5X = 'LPDDR5X', 'LPDDR5X'

    ram_type     = models.CharField(max_length=10, choices=RAMType.choices, null=True, blank=True)
    ram_speed_mhz = models.IntegerField(null=True, blank=True, help_text="e.g. 4800, 5600")
    ram_base_gb  = models.IntegerField(null=True, blank=True, help_text="RAM as shipped in base config")
    ram_max_gb   = models.IntegerField(null=True, blank=True, help_text="Maximum supported RAM")

    # Storage
    class StorageType(models.TextChoices):
        NVME = 'NVME', 'NVMe SSD'
        SATA = 'SATA', 'SATA SSD'
        EMMC = 'EMMC', 'eMMC'

    storage_type    = models.CharField(max_length=10, choices=StorageType.choices, null=True, blank=True)
    storage_base_gb = models.IntegerField(null=True, blank=True, help_text="Storage as shipped in base config")
    storage_max_gb  = models.IntegerField(null=True, blank=True, help_text="Max storage (null if soldered/non-upgradeable)")

    # Display
    class PanelType(models.TextChoices):
        IPS      = 'IPS',      'IPS'
        OLED     = 'OLED',     'OLED'
        AMOLED   = 'AMOLED',   'AMOLED'
        TN       = 'TN',       'TN'
        VA       = 'VA',       'VA'
        MINI_LED = 'MINI_LED', 'Mini-LED'

    display_size_inches  = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="e.g. 14.0, 15.6")
    display_resolution   = models.CharField(max_length=20, null=True, blank=True, help_text="e.g. 1920x1200")
    display_panel_type   = models.CharField(max_length=10, choices=PanelType.choices, null=True, blank=True)

    # Battery
    battery_wh = models.FloatField(null=True, blank=True, help_text="Battery capacity in Wh. Null for desktops.")

    # Verification
    is_verified  = models.BooleanField(default=False)
    verified_by  = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_specs'
    )
    verified_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Machine spec'
        verbose_name_plural = 'Machine specs'

    def __str__(self):
        return f"Spec for {self.machine}"


# =============================================================================
# Model 19 — SpecSuggestion
# =============================================================================

class SpecSuggestion(models.Model):

    class Status(models.TextChoices):
        PENDING  = 'PENDING',  'Pending'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'

    machine        = models.ForeignKey('Machine', on_delete=models.CASCADE, related_name='spec_suggestions')
    suggested_by   = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='spec_suggestions')
    field_name     = models.CharField(max_length=50, help_text="The MachineSpec field this suggestion is for, e.g. cpu_name")
    suggested_value = models.CharField(max_length=200, help_text="The suggested value as a string")
    source_url     = models.URLField(null=True, blank=True, help_text="Link to proof — manufacturer page, Notebookcheck, GSMArena etc.")
    status         = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by    = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_suggestions')
    mod_notes      = models.TextField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-created_at']
        verbose_name        = 'Spec suggestion'
        verbose_name_plural = 'Spec suggestions'

    def __str__(self):
        return f"Suggestion: {self.field_name} = {self.suggested_value} for {self.machine}"


# =============================================================================
# Model 20 — ComponentSpec (NEW — 1:1 with Component)
# =============================================================================

class ComponentSpec(models.Model):

    component = models.OneToOneField(
        'Component', on_delete=models.CASCADE, related_name='spec'
    )

    # GPU
    class GPUArchitecture(models.TextChoices):
        ADA_LOVELACE  = 'ADA_LOVELACE',  'Ada Lovelace (RTX 40xx)'
        AMPERE        = 'AMPERE',        'Ampere (RTX 30xx)'
        TURING        = 'TURING',        'Turing (RTX 20xx)'
        RDNA4         = 'RDNA4',         'RDNA 4 (RX 9xxx)'
        RDNA3         = 'RDNA3',         'RDNA 3 (RX 7xxx)'
        RDNA2         = 'RDNA2',         'RDNA 2 (RX 6xxx)'
        INTEL_XE2     = 'INTEL_XE2',     'Intel Xe2 (Arc Battlemage)'
        INTEL_XE      = 'INTEL_XE',      'Intel Xe (Arc Alchemist)'
        APPLE_GPU     = 'APPLE_GPU',     'Apple GPU'
        INTEGRATED    = 'INTEGRATED',    'Integrated (no dedicated)'

    class GPUMemoryType(models.TextChoices):
        GDDR7   = 'GDDR7',   'GDDR7'
        GDDR6X  = 'GDDR6X',  'GDDR6X'
        GDDR6   = 'GDDR6',   'GDDR6'
        LPDDR5  = 'LPDDR5',  'LPDDR5 (integrated)'
        SHARED  = 'SHARED',  'Shared system RAM'

    gpu_vram_gb       = models.IntegerField(null=True, blank=True, help_text='VRAM in GB')
    gpu_architecture  = models.CharField(max_length=20, choices=GPUArchitecture.choices, null=True, blank=True)
    gpu_tdp_watts     = models.IntegerField(null=True, blank=True, help_text='TDP in watts')
    gpu_memory_type   = models.CharField(max_length=10, choices=GPUMemoryType.choices, null=True, blank=True)
    gpu_generation    = models.CharField(max_length=50, null=True, blank=True, help_text='e.g. RTX 40xx, RX 7xxx')
    gpu_cuda_cores    = models.IntegerField(null=True, blank=True, help_text='CUDA / Stream processors')

    # WiFi
    class WiFiStandard(models.TextChoices):
        WIFI7   = 'WIFI7',   'WiFi 7 (802.11be)'
        WIFI6E  = 'WIFI6E',  'WiFi 6E (802.11ax 6GHz)'
        WIFI6   = 'WIFI6',   'WiFi 6 (802.11ax)'
        WIFI5   = 'WIFI5',   'WiFi 5 (802.11ac)'
        WIFI4   = 'WIFI4',   'WiFi 4 (802.11n)'

    wifi_standard        = models.CharField(max_length=10, choices=WiFiStandard.choices, null=True, blank=True)
    wifi_max_speed_mbps  = models.IntegerField(null=True, blank=True, help_text='Max theoretical speed Mbps')
    wifi_bands           = models.CharField(max_length=40, null=True, blank=True, help_text='e.g. 2.4GHz, 5GHz, 6GHz')
    wifi_bluetooth_ver   = models.CharField(max_length=10, null=True, blank=True, help_text='Bluetooth version e.g. 5.3')

    # Audio
    audio_codec          = models.CharField(max_length=50, null=True, blank=True, help_text='e.g. Realtek ALC289')
    audio_jack_detection = models.BooleanField(null=True, blank=True)
    audio_hdmi_output    = models.BooleanField(null=True, blank=True)
    audio_microphone     = models.BooleanField(null=True, blank=True)
    audio_speakers       = models.BooleanField(null=True, blank=True)

    # Storage
    class StorageInterface(models.TextChoices):
        NVME_GEN5 = 'NVME_GEN5', 'NVMe PCIe Gen 5'
        NVME_GEN4 = 'NVME_GEN4', 'NVMe PCIe Gen 4'
        NVME_GEN3 = 'NVME_GEN3', 'NVMe PCIe Gen 3'
        SATA      = 'SATA',      'SATA SSD'
        EMMC      = 'EMMC',      'eMMC'
        UFS       = 'UFS',       'UFS'

    storage_interface    = models.CharField(max_length=15, choices=StorageInterface.choices, null=True, blank=True)
    storage_form_factor  = models.CharField(max_length=20, null=True, blank=True, help_text='e.g. M.2 2280, M.2 2242')
    storage_capacity_gb  = models.IntegerField(null=True, blank=True)
    storage_read_mbps    = models.IntegerField(null=True, blank=True, help_text='Sequential read MB/s')
    storage_write_mbps   = models.IntegerField(null=True, blank=True, help_text='Sequential write MB/s')

    # Display
    class DisplayTech(models.TextChoices):
        IPS      = 'IPS',      'IPS'
        OLED     = 'OLED',     'OLED'
        AMOLED   = 'AMOLED',   'AMOLED'
        MINI_LED = 'MINI_LED', 'Mini-LED'
        TN       = 'TN',       'TN'
        VA       = 'VA',       'VA'

    display_size_inches  = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    display_resolution   = models.CharField(max_length=20, null=True, blank=True, help_text='e.g. 1920x1200')
    display_refresh_hz   = models.IntegerField(null=True, blank=True)
    display_tech         = models.CharField(max_length=10, choices=DisplayTech.choices, null=True, blank=True)
    display_touch        = models.BooleanField(null=True, blank=True)
    display_hdr          = models.BooleanField(null=True, blank=True)
    display_brightness   = models.IntegerField(null=True, blank=True, help_text='Max brightness in nits')

    # Ethernet
    ethernet_speed_mbps  = models.IntegerField(null=True, blank=True, help_text='e.g. 1000, 2500, 5000')
    ethernet_chip        = models.CharField(max_length=50, null=True, blank=True, help_text='e.g. Intel I219-V')

    # Thunderbolt / USB-C
    tb_version           = models.CharField(max_length=5, null=True, blank=True, help_text='e.g. 4, 5, USB4')
    tb_power_delivery    = models.BooleanField(null=True, blank=True)
    tb_display_output    = models.BooleanField(null=True, blank=True)
    tb_data_speed_gbps   = models.IntegerField(null=True, blank=True)

    # Verification
    is_verified  = models.BooleanField(default=False)
    verified_by  = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_component_specs'
    )
    verified_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Component spec'
        verbose_name_plural = 'Component specs'

    def __str__(self):
        return f'Spec for {self.component}'
