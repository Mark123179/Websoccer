import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from game.models import Stadium
from game.views import current_manager_club

from .capacity import distribute_capacities
from .image_validation import InvalidImageData, normalize_design_payload
from .models import StadiumDesign, StadiumGeometry


def _owned_stadium(request):
    club = current_manager_club(user=request.user)
    if not club:
        return None
    try:
        return club.stadium
    except Stadium.DoesNotExist:
        return None


def _geometry_payload(stadium, geometry):
    return distribute_capacities(stadium, geometry)


@login_required(login_url='/auth/login/')
@require_GET
def stadium_editor(request):
    stadium = _owned_stadium(request)
    if not stadium:
        return HttpResponse('Dein Verein hat noch kein Stadion.', status=404)
    try:
        geometry = StadiumGeometry.objects.get(stadium=stadium)
    except StadiumGeometry.DoesNotExist:
        return render(request, 'stadium_editor/unavailable.html', status=200)
    design = StadiumDesign.objects.filter(stadium=stadium).first()
    return render(request, 'stadium_editor/editor.html', {
        'stadium': stadium,
        'geometry': geometry,
        'design': design.design if design else {},
        'is_editor_admin': bool(request.user.is_staff),
        'attribution': geometry.attribution,
    })


@login_required(login_url='/auth/login/')
@require_GET
def stadium_editor_geometry(request):
    stadium = _owned_stadium(request)
    if not stadium:
        return JsonResponse({'error': 'Stadion nicht gefunden.'}, status=404)
    try:
        row = StadiumGeometry.objects.get(stadium=stadium)
        payload = _geometry_payload(stadium, row.geometry)
    except StadiumGeometry.DoesNotExist:
        return JsonResponse({'error': 'Keine Geometrie hinterlegt.'}, status=404)
    return JsonResponse(payload)


@login_required(login_url='/auth/login/')
@require_GET
def stadium_editor_design(request):
    stadium = _owned_stadium(request)
    if not stadium:
        return JsonResponse({'error': 'Stadion nicht gefunden.'}, status=404)
    design = StadiumDesign.objects.filter(stadium=stadium).first()
    return JsonResponse(design.design if design else {})


@login_required(login_url='/auth/login/')
@require_POST
def stadium_editor_save_design(request):
    stadium = _owned_stadium(request)
    if not stadium:
        return JsonResponse({'error': 'Stadion nicht gefunden.'}, status=404)
    if len(request.body) > 2 * 1024 * 1024:
        return JsonResponse({'error': 'Design ist zu groß.'}, status=413)
    try:
        payload = json.loads(request.body.decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError
        sanitized = normalize_design_payload(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, InvalidImageData) as exc:
        return JsonResponse({'error': str(exc) or 'Ungültiges Design.'}, status=400)
    design, _created = StadiumDesign.objects.get_or_create(stadium=stadium)
    design.design = sanitized
    design.save(update_fields=['design', 'updated_at'])
    return JsonResponse({'ok': True, 'updated_at': design.updated_at.isoformat()})