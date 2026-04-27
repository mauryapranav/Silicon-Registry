"""
registry/admin.py — Silicon Registry
======================================

All models registered with @admin.register decorators.
Key behaviours:
  - ReportAdmin:         bulk approve action, FK traversal search
  - TrustEventAdmin:     pending penalty rows highlighted in red
  - FlagAdmin:           bulk reviewed / dismissed actions
  - HelpGroupAdmin:      inline membership + message tabs
  - UserAdmin:           trust_ratio read-only, score columns in list
  - ComponentAdmin:      ComponentSpec inline, has_spec indicator
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import (
    Benchmark,
    Comment,
    CompStatus,
    Component,
    ComponentSpec,
    DriverFix,
    Distro,
    Flag,
    HelpGroup,
    HelpGroupMembership,
    HelpGroupMessage,
    Machine,
    MachineSpec,
    Report,
    ReportAttachment,
    SpecSuggestion,
    TrustEvent,
    User,
    UserMachine,
    Vote,
)


# =============================================================================
# Bulk Actions
# =============================================================================

@admin.action(description='Approve selected reports')
def approve_reports(modeladmin, request, queryset):
    queryset.update(status=Report.ModerationStatus.APPROVED)


@admin.action(description='Mark selected flags as Reviewed')
def mark_reviewed(modeladmin, request, queryset):
    queryset.update(status=Flag.FlagStatus.REVIEWED)


@admin.action(description='Mark selected flags as Dismissed')
def mark_dismissed(modeladmin, request, queryset):
    queryset.update(status=Flag.FlagStatus.DISMISSED)


@admin.action(description='Accept selected suggestions')
def accept_suggestions(modeladmin, request, queryset):
    for suggestion in queryset:
        spec, created = MachineSpec.objects.get_or_create(machine=suggestion.machine)
        setattr(spec, suggestion.field_name, suggestion.suggested_value)
        spec.save()
        suggestion.status = SpecSuggestion.Status.ACCEPTED
        suggestion.save()


@admin.action(description='Generate slugs for selected items')
def bulk_generate_slugs(modeladmin, request, queryset):
    for obj in queryset:
        obj.slug = None
        obj.save()


# =============================================================================
# User
# =============================================================================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'email', 'role_type', 'is_verified',
        'positive_score', 'negative_score', 'display_trust_ratio',
        'is_active', 'is_staff',
    )
    list_filter = (
        'role_type', 'is_verified', 'is_active', 'is_staff', 'is_superuser',
    )
    search_fields = ('username', 'email', 'github_username')
    readonly_fields = ('display_trust_ratio',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Silicon Registry', {
            'fields': (
                'role_type', 'bio', 'avatar', 'github_username',
                'is_verified', 'positive_score', 'negative_score',
                'display_trust_ratio',
            ),
        }),
    )

    @admin.display(description='Trust Ratio (%)')
    def display_trust_ratio(self, obj):
        return f"{obj.trust_ratio}%"


# =============================================================================
# Machine
# =============================================================================

class MachineSpecInline(admin.StackedInline):
    model = MachineSpec
    extra = 0


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'series', 'model_name', 'cpu_family', 'form_factor', 'slug')
    list_filter = ('vendor', 'cpu_family', 'form_factor')
    search_fields = ('vendor', 'series', 'model_name', 'cpu_family')
    inlines = [MachineSpecInline]
    actions = [bulk_generate_slugs]
    prepopulated_fields = {'slug': ('vendor', 'series', 'model_name')}


# =============================================================================
# Distro
# =============================================================================

@admin.register(Distro)
class DistroAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'kernel_default', 'is_lts', 'is_rolling', 'slug')
    list_filter = ('name', 'is_lts', 'is_rolling')
    search_fields = ('name', 'version', 'kernel_default')
    actions = [bulk_generate_slugs]


# =============================================================================
# Component
# =============================================================================

class ComponentSpecInline(admin.StackedInline):
    model = ComponentSpec
    extra = 0


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'driver', 'has_spec', 'slug')
    list_filter = ('type',)
    search_fields = ('name', 'driver')
    inlines = [ComponentSpecInline]
    actions = [bulk_generate_slugs]

    @admin.display(description='Has Spec', boolean=True)
    def has_spec(self, obj):
        return hasattr(obj, 'spec')


# =============================================================================
# ComponentSpec
# =============================================================================

@admin.register(ComponentSpec)
class ComponentSpecAdmin(admin.ModelAdmin):
    list_display = ('component', 'gpu_vram_gb', 'gpu_architecture', 'wifi_standard',
                    'storage_interface', 'is_verified')
    list_filter = ('gpu_architecture', 'wifi_standard', 'storage_interface',
                   'display_tech', 'is_verified')
    search_fields = ('component__name',)


# =============================================================================
# Report
# =============================================================================

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'report_type', 'status', 'boot_status',
        'user', 'machine', 'distro', 'component', 'created_at',
    )
    list_filter = ('report_type', 'status', 'boot_status')
    search_fields = (
        'title',
        'user__username',
        'machine__model_name',
        'machine__vendor',
        'distro__name',
        'component__name',
    )
    readonly_fields = ('compatibility_score', 'created_at', 'updated_at')
    actions = [approve_reports]
    date_hierarchy = 'created_at'


# =============================================================================
# CompStatus
# =============================================================================

@admin.register(CompStatus)
class CompStatusAdmin(admin.ModelAdmin):
    list_display = ('component', 'report', 'status')
    list_filter = ('status',)
    search_fields = ('component__name', 'report__title')


# =============================================================================
# Comment
# =============================================================================

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'report', 'is_verified', 'created_at')
    list_filter = ('is_verified',)
    search_fields = ('user__username', 'report__title', 'content')


# =============================================================================
# Vote
# =============================================================================

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'vote_type', 'content_type', 'object_id', 'created_at')
    list_filter = ('vote_type', 'content_type')
    search_fields = ('user__username',)


# =============================================================================
# Flag
# =============================================================================

@admin.register(Flag)
class FlagAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'reason', 'status', 'content_type',
        'object_id', 'reviewed_by', 'created_at',
    )
    list_filter = ('reason', 'status', 'content_type')
    search_fields = ('user__username', 'reviewed_by__username', 'details')
    actions = [mark_reviewed, mark_dismissed]


# =============================================================================
# Benchmark
# =============================================================================

@admin.register(Benchmark)
class BenchmarkAdmin(admin.ModelAdmin):
    list_display = (
        'report', 'battery_life_hours', 'power_draw_watts',
        'cpu_score', 'gpu_score', 'suspend_resume_pass', 'created_at',
    )
    list_filter = ('suspend_resume_pass',)
    search_fields = ('report__title',)


# =============================================================================
# DriverFix
# =============================================================================

@admin.register(DriverFix)
class DriverFixAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'component', 'status', 'submitted_by',
        'reviewed_by', 'created_at',
    )
    list_filter = ('status',)
    search_fields = (
        'title', 'component__name',
        'submitted_by__username', 'reviewed_by__username',
    )


# =============================================================================
# TrustEvent
# =============================================================================

@admin.register(TrustEvent)
class TrustEventAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'event_type', 'points_delta',
        'display_penalty_approved', 'display_status_indicator',
        'approved_by', 'created_at',
    )
    list_filter = ('event_type', 'mod_penalty_approved')
    search_fields = ('user__username', 'approved_by__username', 'notes')
    readonly_fields = ('created_at',)

    @admin.display(description='Penalty Approved', boolean=True)
    def display_penalty_approved(self, obj):
        return obj.mod_penalty_approved

    @admin.display(description='Status')
    def display_status_indicator(self, obj):
        if 'PENALTY' in obj.event_type and not obj.mod_penalty_approved:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Pending Approval</span>'
            )
        return format_html('<span style="color: green;">✓ OK</span>')


# =============================================================================
# ReportAttachment
# =============================================================================

@admin.register(ReportAttachment)
class ReportAttachmentAdmin(admin.ModelAdmin):
    list_display = ('report', 'file_type', 'original_filename', 'uploaded_at')
    list_filter = ('file_type',)
    search_fields = ('original_filename', 'report__title')


# =============================================================================
# HelpGroup  (with inline Membership and Messages)
# =============================================================================

class HelpGroupMembershipInline(admin.TabularInline):
    model = HelpGroupMembership
    extra = 0
    fields = ('user', 'invite_status', 'joined_at')
    readonly_fields = ('joined_at',)


class HelpGroupMessageInline(admin.TabularInline):
    model = HelpGroupMessage
    extra = 0
    fields = ('user', 'content', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(HelpGroup)
class HelpGroupAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'component', 'distro', 'status', 'created_by', 'created_at',
    )
    list_filter = ('status',)
    search_fields = (
        'title', 'component__name', 'distro__name', 'created_by__username',
    )
    inlines = [HelpGroupMembershipInline, HelpGroupMessageInline]
    filter_horizontal = ('driver_fixes',)


@admin.register(HelpGroupMembership)
class HelpGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'invite_status', 'joined_at')
    list_filter = ('invite_status',)
    search_fields = ('user__username', 'group__title')


@admin.register(HelpGroupMessage)
class HelpGroupMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'created_at')
    list_filter = ()
    search_fields = ('user__username', 'group__title', 'content')


# =============================================================================
# UserMachine
# =============================================================================

@admin.register(UserMachine)
class UserMachineAdmin(admin.ModelAdmin):
    list_display = ('user', 'machine', 'added_at')
    list_filter = ()
    search_fields = ('user__username', 'machine__vendor', 'machine__model_name')


# =============================================================================
# MachineSpec
# =============================================================================

@admin.register(MachineSpec)
class MachineSpecAdmin(admin.ModelAdmin):
    list_display = ('machine', 'cpu_name', 'cpu_series_tier', 'ram_type', 'ram_base_gb', 'is_verified')
    list_filter = ('cpu_manufacturer', 'cpu_series_tier', 'gpu_type', 'ram_type', 'storage_type', 'display_panel_type', 'is_verified')
    search_fields = ('machine__model_name', 'machine__vendor', 'cpu_name', 'gpu_name')


# =============================================================================
# SpecSuggestion
# =============================================================================

@admin.register(SpecSuggestion)
class SpecSuggestionAdmin(admin.ModelAdmin):
    list_display = ('machine', 'field_name', 'suggested_value', 'suggested_by', 'status', 'created_at')
    list_filter = ('status', 'field_name')
    search_fields = ('machine__model_name', 'suggested_by__username', 'field_name')
    actions = [accept_suggestions]
