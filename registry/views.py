from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django import forms
from functools import wraps
from .models import *

try:
    from thefuzz import fuzz as _fuzz
    FUZZY_ENABLED = True
except ImportError:
    _fuzz = None
    FUZZY_ENABLED = False



# =============================================================================
# Forms
# =============================================================================

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['bio', 'avatar', 'github_username']
        widgets = {'bio': forms.Textarea(attrs={'rows': 4})}


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['machine', 'distro', 'component', 'report_type', 'title',
                  'description', 'boot_status', 'kernel_version']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'silicon-input'})


# =============================================================================
# Decorators
# =============================================================================

def mod_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role_type not in ['MAINTAINER', 'ADMIN']:
            messages.error(request, 'Access denied.')
            return redirect('registry:homepage')
        return view_func(request, *args, **kwargs)
    return wrapper


# =============================================================================
# Core Pages
# =============================================================================

def homepage(request):
    stats = cache.get('homepage_stats')
    if not stats:
        stats = {
            'total_machines': Machine.objects.count(),
            'total_reports':  Report.objects.filter(status='APPROVED').count(),
            'total_users':    User.objects.count(),
            'total_distros':  Distro.objects.count(),
        }
        cache.set('homepage_stats', stats, 300)

    top_machines = Machine.objects.select_related('spec').annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    ).filter(report_count__gt=0).order_by('-report_count')[:6]

    featured_distros = Distro.objects.annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    ).filter(report_count__gt=0).order_by('-report_count')[:4]

    context = {
        **stats,
        'top_machines': top_machines,
        'featured_distros': featured_distros,
    }
    return render(request, 'registry/homepage.html', context)


def about(request):
    return render(request, 'registry/about.html', {})


def search(request):
    FUZZY_THRESHOLD = 60  # minimum score (0-100) to include a fuzzy result

    q = request.GET.get('q', '').strip()
    results = {'machines': [], 'reports': [], 'components': [], 'distros': []}
    did_you_mean = None
    total = 0

    if q:
        q_lower = q.lower()

        # ── Exact (icontains) matches ────────────────────────────────────────
        exact_machines = list(Machine.objects.filter(
            Q(vendor__icontains=q) |
            Q(model_name__icontains=q) |
            Q(series__icontains=q) |
            Q(spec__cpu_name__icontains=q) |
            Q(spec__gpu_name__icontains=q)
        ).select_related('spec').distinct().annotate(report_count=Count('reports'))[:12])

        exact_reports = list(Report.objects.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(comp_statuses__notes__icontains=q) |
            Q(machine__model_name__icontains=q),
            status='APPROVED'
        ).distinct().select_related('user', 'machine', 'distro')[:15])

        exact_components = list(Component.objects.filter(
            Q(name__icontains=q) |
            Q(driver__icontains=q) |
            Q(type__icontains=q)
        ).distinct()[:10])

        exact_distros = list(Distro.objects.filter(
            Q(name__icontains=q) |
            Q(version__icontains=q)
        ).distinct()[:6])

        # Mark exact matches (no badge)
        for obj in exact_machines + exact_reports + exact_components + exact_distros:
            obj.fuzzy_match = False

        fuzzy_machines    = []
        fuzzy_reports     = []
        fuzzy_components  = []
        best_fuzzy_report = None
        best_fuzzy_score  = 0

        # ── Fuzzy candidates (only when library is available) ────────────────
        if FUZZY_ENABLED:
            exact_machine_pks = {m.pk for m in exact_machines}
            exact_report_pks  = {r.pk for r in exact_reports}
            exact_comp_pks    = {c.pk for c in exact_components}

            # Fuzzy machines
            for machine in Machine.objects.select_related('spec').annotate(report_count=Count('reports')):
                if machine.pk in exact_machine_pks:
                    continue
                candidate = f"{machine.vendor or ''} {machine.model_name or ''} {machine.series or ''}"
                score = _fuzz.token_set_ratio(q_lower, candidate.lower())
                if score >= FUZZY_THRESHOLD:
                    machine.fuzzy_match = True
                    machine._fuzzy_score = score
                    fuzzy_machines.append(machine)
            fuzzy_machines.sort(key=lambda m: m._fuzzy_score, reverse=True)
            fuzzy_machines = fuzzy_machines[:8]

            # Fuzzy reports
            for report in Report.objects.filter(status='APPROVED').select_related('user', 'machine', 'distro'):
                if report.pk in exact_report_pks:
                    continue
                machine_name = report.machine.model_name if report.machine else ''
                candidate = f"{report.title or ''} {(report.description or '')[:200]} {machine_name}"
                score = _fuzz.token_set_ratio(q_lower, candidate.lower())
                if score >= FUZZY_THRESHOLD:
                    report.fuzzy_match = True
                    report._fuzzy_score = score
                    fuzzy_reports.append(report)
                    if score > best_fuzzy_score:
                        best_fuzzy_score  = score
                        best_fuzzy_report = report
            fuzzy_reports.sort(key=lambda r: r._fuzzy_score, reverse=True)
            fuzzy_reports = fuzzy_reports[:10]

            # Fuzzy components
            for comp in Component.objects.all():
                if comp.pk in exact_comp_pks:
                    continue
                candidate = f"{comp.name or ''} {comp.driver or ''} {comp.type or ''}"
                score = _fuzz.token_set_ratio(q_lower, candidate.lower())
                if score >= FUZZY_THRESHOLD:
                    comp.fuzzy_match = True
                    comp._fuzzy_score = score
                    fuzzy_components.append(comp)
            fuzzy_components.sort(key=lambda c: c._fuzzy_score, reverse=True)
            fuzzy_components = fuzzy_components[:6]

        # ── Merge ────────────────────────────────────────────────────────────
        results['machines']   = exact_machines   + fuzzy_machines
        results['reports']    = exact_reports    + fuzzy_reports
        results['components'] = exact_components + fuzzy_components
        results['distros']    = exact_distros

        total = sum(len(v) for v in results.values())

        # "Did you mean?" – show best fuzzy report title when there are zero exact hits
        if not exact_reports and best_fuzzy_report and best_fuzzy_score >= 70:
            did_you_mean = best_fuzzy_report.title

    return render(request, 'registry/search.html', {
        'q': q,
        'results': results,
        'total': total,
        'did_you_mean': did_you_mean,
    })


# =============================================================================
# Machine Views
# =============================================================================

def machine_list(request):
    qs = Machine.objects.select_related('spec').annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED')),
        gold_count=Count('reports', filter=Q(reports__status='APPROVED', reports__boot_status='GOLD')),
    )
    q           = request.GET.get('q', '')
    form_factor = request.GET.get('form_factor', '')
    cpu_mfr     = request.GET.get('cpu_manufacturer', '')
    cpu_tier    = request.GET.get('cpu_series_tier', '')
    distro_id   = request.GET.get('distro', '')
    sort        = request.GET.get('sort', '-report_count')

    if q:
        qs = qs.filter(Q(vendor__icontains=q) | Q(model_name__icontains=q) | Q(series__icontains=q))
    if form_factor:
        qs = qs.filter(form_factor=form_factor)
    if cpu_mfr:
        qs = qs.filter(spec__cpu_manufacturer=cpu_mfr)
    if cpu_tier:
        qs = qs.filter(spec__cpu_series_tier=cpu_tier)
    if distro_id:
        qs = qs.filter(reports__distro_id=distro_id, reports__status='APPROVED').distinct()

    valid_sorts = ['-report_count', '-gold_count', 'vendor', 'model_name']
    if sort in valid_sorts:
        qs = qs.order_by(sort)
    else:
        qs = qs.order_by('-report_count')

    paginator = Paginator(qs, 18)
    page = request.GET.get('page', 1)
    machines = paginator.get_page(page)

    is_htmx = request.headers.get('HX-Request')
    context = {
        'machines': machines,
        'total_count': paginator.count,
        'distros': Distro.objects.all().order_by('name'),
        'form_factors': Machine.FormFactor.choices,
        'cpu_tiers': MachineSpec.CPUSeriesTier.choices if hasattr(MachineSpec, 'CPUSeriesTier') else [],
        'q': q, 'form_factor': form_factor,
        'cpu_mfr': cpu_mfr, 'cpu_tier': cpu_tier,
        'distro_id': distro_id, 'sort': sort,
    }
    if is_htmx:
        return render(request, 'registry/partials/machine_cards.html', context)
    return render(request, 'registry/machine_list.html', context)


def machine_add(request):
    return render(request, 'registry/machine_add.html', {})


def machine_detail(request, slug):
    machine = get_object_or_404(Machine, slug=slug)
    spec = getattr(machine, 'spec', None)
    reports = Report.objects.filter(
        machine=machine, status='APPROVED'
    ).select_related('user', 'distro', 'component').prefetch_related(
        'comp_statuses__component'
    ).order_by('-created_at')

    # Component status summary across all reports
    from collections import defaultdict
    comp_summary = defaultdict(lambda: {'working': 0, 'issues': 0, 'broken': 0, 'name': '', 'type': '', 'slug': ''})
    for report in reports:
        for cs in report.comp_statuses.all():
            key = cs.component_id
            comp_summary[key]['name'] = cs.component.name
            comp_summary[key]['type'] = cs.component.type
            comp_summary[key]['slug'] = cs.component.slug
            if cs.status == 'WORKING':
                comp_summary[key]['working'] += 1
            elif cs.status == 'ISSUES':
                comp_summary[key]['issues'] += 1
            elif cs.status == 'BROKEN':
                comp_summary[key]['broken'] += 1

    # Overall compat badge
    total = reports.count()
    gold = reports.filter(boot_status='GOLD').count()
    if total == 0:
        compat = 'none'
    elif gold == total:
        compat = 'gold'
    elif gold > total / 2:
        compat = 'mostly_gold'
    elif reports.filter(boot_status='BROKEN').count() > total / 2:
        compat = 'broken'
    else:
        compat = 'mixed'

    driver_fixes = DriverFix.objects.filter(
        component__in=[cs.component_id for r in reports for cs in r.comp_statuses.all()],
        status='ACCEPTED'
    ).select_related('component', 'submitted_by').distinct()[:10]

    related = Machine.objects.filter(
        vendor=machine.vendor, series=machine.series
    ).exclude(pk=machine.pk).annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    )[:4]

    context = {
        'machine': machine, 'spec': spec, 'reports': reports,
        'report_count': total, 'compat': compat,
        'comp_summary': dict(comp_summary),
        'driver_fixes': driver_fixes, 'related': related,
    }
    return render(request, 'registry/machine_detail.html', context)


def machine_detail_by_pk(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    if not machine.slug:
        machine.save()
    return redirect('registry:machine_detail', slug=machine.slug, permanent=True)


# =============================================================================
# Component Detail
# =============================================================================

def component_detail(request, slug):
    component = get_object_or_404(Component, slug=slug)
    spec = getattr(component, 'spec', None)

    reports = Report.objects.filter(
        comp_statuses__component=component, status='APPROVED'
    ).select_related('user', 'machine', 'distro').distinct().order_by('-created_at')

    status_counts = {
        'working': CompStatus.objects.filter(component=component, status='WORKING').count(),
        'issues':  CompStatus.objects.filter(component=component, status='ISSUES').count(),
        'broken':  CompStatus.objects.filter(component=component, status='BROKEN').count(),
    }
    total_status = sum(status_counts.values())
    working_pct = round(status_counts['working'] * 100 / max(total_status, 1))

    driver_fixes = DriverFix.objects.filter(
        component=component, status='ACCEPTED'
    ).select_related('submitted_by').order_by('-created_at')

    help_groups = HelpGroup.objects.filter(
        component=component
    ).order_by('-created_at')[:5]

    context = {
        'component': component,
        'spec': spec,
        'reports': reports,
        'report_count': reports.count(),
        'status_counts': status_counts,
        'working_pct': working_pct,
        'driver_fixes': driver_fixes,
        'help_groups': help_groups,
        'total_status': total_status,
    }
    return render(request, 'registry/component_detail.html', context)


def component_detail_by_pk(request, pk):
    component = get_object_or_404(Component, pk=pk)
    if not component.slug:
        component.save()
    return redirect('registry:component_detail', slug=component.slug, permanent=True)


# =============================================================================
# Distro Detail
# =============================================================================

def distro_detail(request, slug):
    distro = get_object_or_404(Distro, slug=slug)
    reports = Report.objects.filter(
        distro=distro, status='APPROVED'
    ).select_related('user', 'machine', 'component').order_by('-created_at')

    report_count = reports.count()
    boot_counts = {
        'gold':   reports.filter(boot_status='GOLD').count(),
        'silver': reports.filter(boot_status='SILVER').count(),
        'bronze': reports.filter(boot_status='BRONZE').count(),
        'broken': reports.filter(boot_status='BROKEN').count(),
    }

    top_machines = Machine.objects.filter(
        reports__distro=distro, reports__status='APPROVED'
    ).annotate(
        report_count=Count('reports', filter=Q(
            reports__distro=distro, reports__status='APPROVED'
        )),
        gold_count=Count('reports', filter=Q(
            reports__distro=distro, reports__status='APPROVED',
            reports__boot_status='GOLD'
        ))
    ).order_by('-gold_count', '-report_count')[:8]

    kernel_versions = reports.exclude(
        kernel_version=None
    ).exclude(kernel_version='').values(
        'kernel_version'
    ).annotate(count=Count('id')).order_by('-count')[:10]

    context = {
        'distro': distro,
        'reports': reports[:20],
        'report_count': report_count,
        'boot_counts': boot_counts,
        'top_machines': top_machines,
        'kernel_versions': kernel_versions,
    }
    return render(request, 'registry/distro_detail.html', context)


def distro_detail_by_pk(request, pk):
    distro = get_object_or_404(Distro, pk=pk)
    if not distro.slug:
        distro.save()
    return redirect('registry:distro_detail', slug=distro.slug, permanent=True)


# =============================================================================
# Report Views
# =============================================================================

def report_detail(request, pk):
    report = get_object_or_404(
        Report.objects.select_related('user', 'machine', 'distro', 'component'),
        pk=pk, status='APPROVED'
    )
    comp_statuses = report.comp_statuses.select_related('component').all()
    comments = report.comments.select_related('user').order_by('created_at')
    attachments = report.attachments.all()
    benchmarks = report.benchmarks.all()

    # Vote data
    ct = ContentType.objects.get_for_model(Report)
    upvotes = Vote.objects.filter(content_type=ct, object_id=report.pk, vote_type='UPVOTE').count()
    downvotes = Vote.objects.filter(content_type=ct, object_id=report.pk, vote_type='DOWNVOTE').count()
    user_vote = None
    if request.user.is_authenticated:
        user_vote = Vote.objects.filter(
            user=request.user, content_type=ct, object_id=report.pk
        ).first()

    context = {
        'report': report, 'comp_statuses': comp_statuses,
        'comments': comments, 'attachments': attachments,
        'benchmarks': benchmarks,
        'comment_count': comments.count(),
        'upvotes': upvotes, 'downvotes': downvotes,
        'user_vote': user_vote,
    }
    return render(request, 'registry/report_detail.html', context)


@login_required
def report_submit(request):
    if request.method == 'POST':
        form = ReportForm(request.POST)
        # Server-side validation
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()

        if len(title) < 10:
            messages.error(request, 'Title too short (min 10 characters).')
            return render(request, 'registry/report_submit.html', {'form': form})

        if len(description) < 30:
            messages.error(request, 'Description too short (min 30 characters).')
            return render(request, 'registry/report_submit.html', {'form': form})

        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.status = 'PENDING'

            # Duplicate detection
            existing = Report.objects.filter(
                user=request.user,
                machine=report.machine,
                distro=report.distro,
                component=report.component,
                report_type=report.report_type,
                status__in=['PENDING', 'APPROVED']
            ).first()

            if existing and not request.POST.get('confirm_duplicate'):
                messages.warning(
                    request,
                    f'You already have a report for this combination (#{existing.pk}). '
                    f'Submit again with the checkbox to confirm.'
                )
                context = {'form': form, 'duplicate_warning': True, 'existing_report': existing}
                return render(request, 'registry/report_submit.html', context)

            report.save()
            messages.success(request, 'Report submitted! It will appear once approved by a maintainer.')
            return redirect('registry:homepage')
    else:
        form = ReportForm()

    return render(request, 'registry/report_submit.html', {'form': form})


# =============================================================================
# Voting
# =============================================================================

@login_required
def cast_vote(request, model, pk, vote_type):
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)

    if model == 'report':
        obj = get_object_or_404(Report, pk=pk)
    elif model == 'comment':
        obj = get_object_or_404(Comment, pk=pk)
    else:
        return HttpResponse('Invalid', status=400)

    ct = ContentType.objects.get_for_model(obj)
    existing = Vote.objects.filter(
        user=request.user, content_type=ct, object_id=pk
    ).first()

    if existing:
        if existing.vote_type == vote_type:
            existing.delete()
        else:
            existing.vote_type = vote_type
            existing.save()
    else:
        Vote.objects.create(
            user=request.user, content_type=ct,
            object_id=pk, vote_type=vote_type
        )

    upvotes = Vote.objects.filter(content_type=ct, object_id=pk, vote_type='UPVOTE').count()
    downvotes = Vote.objects.filter(content_type=ct, object_id=pk, vote_type='DOWNVOTE').count()
    user_vote = Vote.objects.filter(
        user=request.user, content_type=ct, object_id=pk
    ).first()

    if request.headers.get('HX-Request'):
        return render(request, 'registry/partials/vote_buttons.html', {
            'model': model, 'pk': pk,
            'upvotes': upvotes, 'downvotes': downvotes,
            'user_vote': user_vote,
        })
    return redirect(request.META.get('HTTP_REFERER', '/'))


# =============================================================================
# Leaderboard
# =============================================================================

def leaderboard(request):
    users = User.objects.annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED')),
        comment_count=Count('comments'),
        fix_count=Count('driver_fixes', filter=Q(driver_fixes__status='ACCEPTED')),
    ).filter(
        Q(report_count__gt=0) | Q(fix_count__gt=0)
    ).order_by('-positive_score')[:50]
    return render(request, 'registry/leaderboard.html', {'users': users})


# =============================================================================
# Driver Fix Submission
# =============================================================================

@login_required
def fix_submit(request):
    if request.method == 'POST':
        component_id = request.POST.get('component_id')
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        external_url = request.POST.get('external_url', '').strip()

        if not component_id or not title or not body:
            messages.error(request, 'Component, title, and body are all required.')
            return redirect('registry:fix_submit')

        if len(title) < 10:
            messages.error(request, 'Title must be at least 10 characters.')
            return redirect('registry:fix_submit')

        component = get_object_or_404(Component, pk=component_id)
        DriverFix.objects.create(
            component=component,
            submitted_by=request.user,
            title=title,
            body=body,
            external_url=external_url or None,
            status='PENDING',
        )
        messages.success(request, 'Fix submitted! Maintainers will review it.')
        return redirect('registry:machine_list')

    components = Component.objects.all().order_by('type', 'name')
    return render(request, 'registry/fix_submit.html', {'components': components})


# =============================================================================
# User Profile
# =============================================================================

def user_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    reports = Report.objects.filter(
        user=profile_user, status='APPROVED'
    ).select_related('machine', 'distro').order_by('-created_at')
    driver_fixes = DriverFix.objects.filter(
        submitted_by=profile_user, status='ACCEPTED'
    ).select_related('component')
    owned_machines = UserMachine.objects.filter(
        user=profile_user
    ).select_related('machine')
    context = {
        'profile_user': profile_user,
        'reports': reports,
        'report_count': reports.count(),
        'driver_fixes': driver_fixes,
        'owned_machines': owned_machines,
        'trust_ratio': round(
            profile_user.positive_score * 100 /
            max(profile_user.positive_score + profile_user.negative_score, 1), 1
        ),
        'is_own_profile': request.user == profile_user,
    }
    return render(request, 'registry/user_profile.html', context)


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('registry:user_profile', username=request.user.username)
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'registry/profile_edit.html', {'form': form})


# =============================================================================
# Actions
# =============================================================================

@login_required
def flag_report(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if request.method == 'POST':
        Flag.objects.create(
            user=request.user,
            content_type=ContentType.objects.get_for_model(Report),
            object_id=report.pk,
            reason=request.POST.get('reason'),
            details=request.POST.get('details', ''),
        )
        messages.success(request, 'Report flagged. Moderators will review it.')
        if request.headers.get('HX-Request'):
            return HttpResponse('<p class="text-sm text-white/40">Flagged. Thank you.</p>')
        return redirect('registry:report_detail', pk=pk)
    reasons = Flag.FlagReason.choices
    if request.headers.get('HX-Request'):
        return render(request, 'registry/partials/flag_form.html', {'report': report, 'reasons': reasons})
    return render(request, 'registry/flag_form.html', {'report': report, 'reasons': reasons})


@login_required
def add_comment(request, pk):
    report = get_object_or_404(Report, pk=pk, status='APPROVED')
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Comment.objects.create(user=request.user, report=report, content=content)
            messages.success(request, 'Comment added.')
        if request.headers.get('HX-Request'):
            comments = report.comments.select_related('user').order_by('created_at')
            return render(request, 'registry/partials/comment_form.html', {'report': report, 'comments': comments})
    return redirect('registry:report_detail', pk=pk)


@login_required
def suggest_spec(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    if request.method == 'POST':
        field_name = request.POST.get('field_name')
        suggested_value = request.POST.get('suggested_value')
        source_url = request.POST.get('source_url')
        if field_name and suggested_value:
            SpecSuggestion.objects.create(
                machine=machine,
                suggested_by=request.user,
                field_name=field_name,
                suggested_value=suggested_value,
                source_url=source_url,
                status='PENDING'
            )
            messages.success(request, f'Suggestion for {field_name} submitted for review.')
            return redirect('registry:machine_detail', slug=machine.slug)

    spec_fields = [
        ('cpu_name', 'CPU Name'), ('cpu_manufacturer', 'CPU Manufacturer'),
        ('cpu_generation', 'CPU Generation'), ('cpu_series_tier', 'CPU Series Tier'),
        ('gpu_name', 'GPU Name'), ('gpu_manufacturer', 'GPU Manufacturer'),
        ('gpu_type', 'GPU Type'), ('ram_type', 'RAM Type'),
        ('ram_speed_mhz', 'RAM Speed (MHz)'), ('ram_base_gb', 'RAM Base (GB)'),
        ('ram_max_gb', 'RAM Max (GB)'), ('storage_type', 'Storage Type'),
        ('storage_base_gb', 'Storage Base (GB)'), ('storage_max_gb', 'Storage Max (GB)'),
        ('display_size_inches', 'Display Size (inches)'), ('display_resolution', 'Display Resolution'),
        ('display_panel_type', 'Display Panel Type'), ('battery_wh', 'Battery (Wh)')
    ]
    return render(request, 'registry/suggest_spec.html', {'machine': machine, 'spec_fields': spec_fields})


# =============================================================================
# Moderation Dashboard
# =============================================================================

@mod_required
def mod_dashboard(request):
    context = {
        'pending_reports': Report.objects.filter(status='PENDING').count(),
        'pending_specs': SpecSuggestion.objects.filter(status='PENDING').count(),
        'pending_fixes': DriverFix.objects.filter(status='PENDING').count(),
        'open_flags': Flag.objects.filter(status='PENDING').count(),
        'pending_trust_events': TrustEvent.objects.filter(mod_penalty_approved=False, points_delta__lt=0).count(),
        'total_users': User.objects.count(),
        'total_reports': Report.objects.filter(status='APPROVED').count(),
        'total_machines': Machine.objects.count(),
    }
    return render(request, 'registry/mod/dashboard.html', context)


@mod_required
def mod_reports(request):
    reports = Report.objects.filter(status='PENDING').select_related('user', 'machine', 'distro').order_by('created_at')
    return render(request, 'registry/mod/reports.html', {'reports': reports})


@mod_required
def mod_approve_report(request, pk):
    if request.method == 'POST':
        report = get_object_or_404(Report, pk=pk)
        report.status = 'APPROVED'
        report.save()
        # Create trust event for the reporter
        if report.user:
            TrustEvent.objects.create(
                user=report.user,
                event_type='REPORT_APPROVED',
                points_delta=5,
                notes=f'Report #{pk} approved.'
            )
        messages.success(request, f'Report #{pk} approved.')
    return redirect('registry:mod_reports')


@mod_required
def mod_reject_report(request, pk):
    if request.method == 'POST':
        report = get_object_or_404(Report, pk=pk)
        report.status = 'REJECTED'
        report.save()
        messages.success(request, f'Report #{pk} rejected.')
    return redirect('registry:mod_reports')


@mod_required
def mod_specs(request):
    if request.method == 'POST':
        suggestion = get_object_or_404(SpecSuggestion, pk=request.POST.get('suggestion_id'))
        action = request.POST.get('action')
        if action == 'accept':
            spec, created = MachineSpec.objects.get_or_create(machine=suggestion.machine)
            setattr(spec, suggestion.field_name, suggestion.suggested_value)
            spec.save()
            suggestion.status = 'ACCEPTED'
            messages.success(request, 'Spec suggestion accepted and applied.')
        elif action == 'reject':
            suggestion.status = 'REJECTED'
            messages.success(request, 'Spec suggestion rejected.')
        suggestion.reviewed_by = request.user
        suggestion.save()
        return redirect('registry:mod_specs')

    suggestions = SpecSuggestion.objects.filter(status='PENDING').select_related('machine', 'suggested_by').order_by('created_at')
    return render(request, 'registry/mod/specs.html', {'suggestions': suggestions})


@mod_required
def mod_fixes(request):
    if request.method == 'POST':
        fix = get_object_or_404(DriverFix, pk=request.POST.get('fix_id'))
        action = request.POST.get('action')
        if action == 'accept':
            fix.status = 'ACCEPTED'
            messages.success(request, 'Driver fix accepted.')
        elif action == 'reject':
            fix.status = 'REJECTED'
            messages.success(request, 'Driver fix rejected.')
        fix.reviewed_by = request.user
        fix.save()
        return redirect('registry:mod_fixes')

    fixes = DriverFix.objects.filter(status='PENDING').select_related('component', 'submitted_by').order_by('created_at')
    return render(request, 'registry/mod/fixes.html', {'fixes': fixes})


@mod_required
def mod_trust(request):
    if request.method == 'POST':
        event = get_object_or_404(TrustEvent, pk=request.POST.get('event_id'))
        event.mod_penalty_approved = True
        event.approved_by = request.user
        event.save()
        event.user.negative_score += abs(event.points_delta)
        event.user.save()
        messages.success(request, 'Penalty approved.')
        return redirect('registry:mod_trust')

    events = TrustEvent.objects.filter(mod_penalty_approved=False, points_delta__lt=0).select_related('user').order_by('created_at')
    return render(request, 'registry/mod/trust.html', {'events': events})


@mod_required
def mod_users(request):
    if request.method == 'POST':
        user = get_object_or_404(User, pk=request.POST.get('user_id'))
        new_role = request.POST.get('role_type')
        if new_role in dict(User.RoleType.choices):
            user.role_type = new_role
            user.save()
            messages.success(request, f'Role for {user.username} updated to {new_role}.')
        return redirect('registry:mod_users')

    users = User.objects.all().order_by('-date_joined')
    return render(request, 'registry/mod/users.html', {'users': users, 'roles': User.RoleType.choices})


@mod_required
def mod_groups(request):
    return render(request, 'registry/mod/groups.html', {})


# =============================================================================
# Partials (HTMX)
# =============================================================================

def partial_machine_cards(request):
    return HttpResponse('')


def partial_navbar_search(request):
    q = request.GET.get('q', '')
    if len(q) < 2:
        return HttpResponse('')
    machines = Machine.objects.filter(
        Q(vendor__icontains=q) | Q(model_name__icontains=q) | Q(series__icontains=q)
    )[:5]
    return render(request, 'registry/partials/navbar_search.html', {'machines': machines})


def partial_load_more(request):
    return HttpResponse('')


# =============================================================================
# API (JSON endpoints)
# =============================================================================

def api_machines(request):
    data = list(Machine.objects.annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    ).values('id', 'vendor', 'series', 'model_name', 'cpu_family', 'form_factor', 'slug', 'report_count'))
    response = JsonResponse(data, safe=False)
    response['Access-Control-Allow-Origin'] = '*'
    return response


def api_reports(request):
    data = list(Report.objects.filter(status='APPROVED').select_related(
        'user', 'machine', 'distro'
    ).values('id', 'title', 'report_type', 'boot_status', 'kernel_version', 'created_at',
             'user__username', 'machine__model_name', 'distro__name', 'distro__version')[:50])
    response = JsonResponse(data, safe=False)
    response['Access-Control-Allow-Origin'] = '*'
    return response


def api_components(request):
    data = list(Component.objects.values('id', 'type', 'name', 'driver', 'slug'))
    response = JsonResponse(data, safe=False)
    response['Access-Control-Allow-Origin'] = '*'
    return response


def api_distros(request):
    data = list(Distro.objects.annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    ).values('id', 'name', 'version', 'kernel_default', 'slug', 'report_count'))
    response = JsonResponse(data, safe=False)
    response['Access-Control-Allow-Origin'] = '*'
    return response


# =============================================================================
# Error Pages
# =============================================================================

def error_404(request, exception=None):
    return render(request, 'registry/404.html', {}, status=404)


def error_500(request):
    return render(request, 'registry/500.html', {}, status=500)
