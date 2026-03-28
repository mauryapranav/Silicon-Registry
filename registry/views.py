from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django import forms
from .models import *

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['bio', 'avatar', 'github_username']
        widgets = {'bio': forms.Textarea(attrs={'rows': 4})}

def homepage(request):
# ... existing homepage view ...
    context = {
        'total_machines': Machine.objects.count(),
        'total_reports':  Report.objects.filter(status='APPROVED').count(),
        'total_users':    User.objects.count(),
        'total_distros':  Distro.objects.count(),
        'top_machines': Machine.objects.annotate(
            report_count=Count('reports', filter=Q(reports__status='APPROVED'))
        ).filter(report_count__gt=0).order_by('-report_count')[:6],
        'featured_distros': Distro.objects.annotate(
            report_count=Count('reports', filter=Q(reports__status='APPROVED'))
        ).filter(report_count__gt=0).order_by('-report_count')[:4],
    }
    return render(request, 'registry/homepage.html', context)

def about(request): return render(request, 'registry/about.html', {})
from functools import wraps

def mod_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role_type not in ['MAINTAINER','ADMIN']:
            messages.error(request, 'Access denied.')
            return redirect('registry:homepage')
        return view_func(request, *args, **kwargs)
    return wrapper

def search(request):
    q = request.GET.get('q', '').strip()
    results = {'machines': [], 'reports': [], 'components': [], 'distros': []}
    total = 0
    if q:
        results['machines']    = Machine.objects.filter(Q(vendor__icontains=q)|Q(model_name__icontains=q)|Q(series__icontains=q)).annotate(report_count=Count('reports'))[:8]
        results['reports']     = Report.objects.filter(Q(title__icontains=q)|Q(description__icontains=q), status='APPROVED').select_related('user','machine','distro')[:8]
        results['components']  = Component.objects.filter(Q(name__icontains=q)|Q(driver__icontains=q))[:6]
        results['distros']     = Distro.objects.filter(Q(name__icontains=q)|Q(version__icontains=q))[:4]
        total = sum(len(v) for v in results.values())
    return render(request, 'registry/search.html', {'q':q,'results':results,'total':total})

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
        # Also need to update the user's actual score since it's approved now
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

def api_machines(request):
    data = list(Machine.objects.annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    ).values('id','vendor','series','model_name','cpu_family','form_factor','report_count'))
    response = JsonResponse(data, safe=False)
    response['Access-Control-Allow-Origin'] = '*'
    return response

def api_reports(request):
    data = list(Report.objects.filter(status='APPROVED').select_related(
        'user','machine','distro'
    ).values('id','title','report_type','boot_status','kernel_version','created_at',
             'user__username','machine__model_name','distro__name','distro__version')[:50])
    response = JsonResponse(data, safe=False)
    response['Access-Control-Allow-Origin'] = '*'
    return response

def api_components(request):
    data = list(Component.objects.values('id','type','name','driver'))
    response = JsonResponse(data, safe=False)
    response['Access-Control-Allow-Origin'] = '*'
    return response

def api_distros(request):
    data = list(Distro.objects.annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    ).values('id','name','version','kernel_default','report_count'))
    response = JsonResponse(data, safe=False)
    response['Access-Control-Allow-Origin'] = '*'
    return response
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

    # Paginate 18 per page
    from django.core.paginator import Paginator
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

def machine_add(request): return render(request, 'registry/machine_add.html', {})

def machine_detail(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    spec = getattr(machine, 'spec', None)
    reports = Report.objects.filter(
        machine=machine, status='APPROVED'
    ).select_related('user', 'distro', 'component').prefetch_related(
        'comp_statuses__component'
    ).order_by('-created_at')

    # Component status summary across all reports
    from collections import defaultdict
    comp_summary = defaultdict(lambda: {'working':0,'issues':0,'broken':0,'name':'','type':''})
    for report in reports:
        for cs in report.comp_statuses.all():
            key = cs.component_id
            comp_summary[key]['name'] = cs.component.name
            comp_summary[key]['type'] = cs.component.type
            if cs.status == 'WORKING': comp_summary[key]['working'] += 1
            elif cs.status == 'ISSUES': comp_summary[key]['issues'] += 1
            elif cs.status == 'BROKEN': comp_summary[key]['broken'] += 1

    # Overall compat badge
    total = reports.count()
    gold  = reports.filter(boot_status='GOLD').count()
    if total == 0: compat = 'none'
    elif gold == total: compat = 'gold'
    elif gold > total / 2: compat = 'mostly_gold'
    elif reports.filter(boot_status='BROKEN').count() > total / 2: compat = 'broken'
    else: compat = 'mixed'

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

def report_detail(request, pk):
    report = get_object_or_404(
        Report.objects.select_related('user','machine','distro','component'),
        pk=pk, status='APPROVED'
    )
    comp_statuses = report.comp_statuses.select_related('component').all()
    comments      = report.comments.select_related('user').order_by('created_at')
    attachments   = report.attachments.all()
    benchmarks    = report.benchmarks.all()
    context = {
        'report': report, 'comp_statuses': comp_statuses,
        'comments': comments, 'attachments': attachments,
        'benchmarks': benchmarks,
        'comment_count': comments.count(),
    }
    return render(request, 'registry/report_detail.html', context)

@login_required
def report_submit(request):
    step = int(request.GET.get('step', 1))
    wizard_data = request.session.get('report_wizard', {})

    if request.method == 'POST':
        wizard_data.update(request.POST.dict())
        request.session['report_wizard'] = wizard_data
        if step < 4:
            return redirect(f"{request.path}?step={step+1}")
        # Final submit on step 4
        try:
            report = Report.objects.create(
                user=request.user,
                report_type=wizard_data.get('report_type'),
                machine_id=wizard_data.get('machine_id') or None,
                distro_id=wizard_data.get('distro_id') or None,
                component_id=wizard_data.get('component_id') or None,
                title=wizard_data.get('title'),
                description=wizard_data.get('description'),
                boot_status=wizard_data.get('boot_status') or None,
                kernel_version=wizard_data.get('kernel_version') or None,
                status='PENDING',
            )
            request.session.pop('report_wizard', None)
            messages.success(request, 'Report submitted! It will appear once approved by a maintainer.')
            return redirect('registry:report_detail', pk=report.pk) if report.status == 'APPROVED' else redirect('registry:homepage')
        except Exception as e:
            messages.error(request, f'Submission failed: {e}')

    context = {'step': step, 'wizard_data': wizard_data,
               'machines': Machine.objects.all().order_by('vendor','model_name'),
               'distros': Distro.objects.all().order_by('name'),
               'components': Component.objects.all().order_by('type','name'),
               'report_types': Report.ReportType.choices,
               'boot_statuses': Report.BootStatus.choices,
               }
    return render(request, 'registry/report_submit.html', context)

def user_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    reports = Report.objects.filter(
        user=profile_user, status='APPROVED'
    ).select_related('machine','distro').order_by('-created_at')
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

@login_required
def flag_report(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if request.method == 'POST':
        Flag.objects.create(
            user=request.user,
            content_type=ContentType.objects.get_for_model(Report),
            object_id=report.pk,
            reason=request.POST.get('reason'),
            details=request.POST.get('details',''),
        )
        messages.success(request, 'Report flagged. Moderators will review it.')
        if request.headers.get('HX-Request'):
            return HttpResponse('<p class="text-muted small">Flagged. Thank you.</p>')
        return redirect('registry:report_detail', pk=pk)
    reasons = Flag.FlagReason.choices
    if request.headers.get('HX-Request'):
        return render(request, 'registry/partials/flag_form.html', {'report':report,'reasons':reasons})
    return render(request, 'registry/flag_form.html', {'report':report,'reasons':reasons})

@login_required
def add_comment(request, pk):
    report = get_object_or_404(Report, pk=pk, status='APPROVED')
    if request.method == 'POST':
        content = request.POST.get('content','').strip()
        if content:
            Comment.objects.create(user=request.user, report=report, content=content)
            messages.success(request, 'Comment added.')
        if request.headers.get('HX-Request'):
            comments = report.comments.select_related('user').order_by('created_at')
            return render(request, 'registry/partials/comment_form.html', {'report':report,'comments':comments})
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
            return redirect('registry:machine_detail', pk=pk)
    
    # Get fields from MachineSpec model to suggest
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
def partial_machine_cards(request): return HttpResponse('')
def partial_navbar_search(request):
    q = request.GET.get('q', '')
    if len(q) < 2:
        return HttpResponse('')
    machines = Machine.objects.filter(
        Q(vendor__icontains=q) | Q(model_name__icontains=q) | Q(series__icontains=q)
    )[:5]
    return render(request, 'registry/partials/navbar_search.html', {'machines': machines})

def partial_load_more(request): return HttpResponse('')
def api_machines(request): return JsonResponse([], safe=False)
def api_reports(request): return JsonResponse([], safe=False)
def api_components(request): return JsonResponse([], safe=False)
def api_distros(request): return JsonResponse([], safe=False)
def error_404(request, exception=None): return render(request, 'registry/404.html', {}, status=404)
def error_500(request): return render(request, 'registry/500.html', {}, status=500)
