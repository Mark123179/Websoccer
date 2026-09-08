import json
from copy import deepcopy

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from game.models import Stadium
from game.views import build_game_header, current_manager_club

from .capacity import distribute_capacities
from .image_validation import InvalidImageData, normalize_design_payload
from .models import StadiumDesign, StadiumGeometry
from .contracts import axis_theta, geometry_blocks, hydrate_design, visible_blocks


def _owned_stadium(request):
    club = current_manager_club(user=request.user)
    if not club:
        return None
    try:
        return club.stadium
    except Stadium.DoesNotExist:
        return None


def _geometry_payload(stadium, geometry):
    payload = distribute_capacities(stadium, geometry)
    trusted = {block['id']: block for block in geometry_blocks(payload)}
    for position, block in enumerate(payload['blocks']):
        block.update(trusted[block.get('id', position)])
    payload['axisTheta'] = axis_theta(payload)
    return payload


def _hydrated_design(stadium, row, design):
    return hydrate_design(design.design, _geometry_payload(stadium, row.geometry),
                          stadium.name, design.blickrichtung)


@login_required(login_url='/auth/login/')
@require_GET
def stadium_editor(request):
    stadium = _owned_stadium(request)
    if not stadium:
        return HttpResponse('Dein Verein hat noch kein Stadion.', status=404)
    try:
        geometry = StadiumGeometry.objects.get(stadium=stadium)
    except StadiumGeometry.DoesNotExist:
        return render(request, 'stadium_editor/unavailable.html', {
            'game_header': build_game_header('Stadion', 'Editor', reverse('stadium_detail')),
        }, status=200)
    design = StadiumDesign.objects.filter(stadium=stadium).first()
    return render(request, 'stadium_editor/editor.html', {
        'stadium': stadium,
        'geometry': geometry,
        'design': design.design if design else {},
        'is_editor_admin': bool(request.user.is_staff),
        'attribution': geometry.attribution,
        'game_header': build_game_header('Stadion', 'Editor', reverse('stadium_detail')),
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
    if not design:
        return JsonResponse({})
    try:
        row = StadiumGeometry.objects.get(stadium=stadium)
        return JsonResponse(_hydrated_design(stadium, row, design))
    except StadiumGeometry.DoesNotExist:
        return JsonResponse({})


@login_required(login_url='/auth/login/')
@require_GET
def stadium_editor_visible_design(request):
    stadium = _owned_stadium(request)
    if not stadium:
        return JsonResponse({'error': 'Stadion nicht gefunden.'}, status=404)
    design = StadiumDesign.objects.filter(stadium=stadium).first()
    if not design:
        return JsonResponse({})
    try:
        row = StadiumGeometry.objects.get(stadium=stadium)
        payload = _hydrated_design(stadium, row, design)
    except StadiumGeometry.DoesNotExist:
        return JsonResponse({})
    payload['blocks'] = visible_blocks(payload, payload['blickrichtung'])
    return JsonResponse(payload)


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
        geometry = _geometry_payload(
            stadium, StadiumGeometry.objects.get(stadium=stadium).geometry)
        sanitized = normalize_design_payload(
            payload, geometry=geometry, stadium_name=stadium.name,
            blickrichtung=payload.get('blickrichtung', 'NORD'),
        )
    except StadiumGeometry.DoesNotExist:
        return JsonResponse({'error': 'Keine Geometrie hinterlegt.'}, status=409)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, InvalidImageData) as exc:
        return JsonResponse({'error': str(exc) or 'Ungültiges Design.'}, status=400)
    design, _created = StadiumDesign.objects.get_or_create(stadium=stadium)
    design.design = sanitized
    design.blickrichtung = sanitized['blickrichtung']
    design.save(update_fields=['design', 'blickrichtung', 'updated_at'])
    return JsonResponse({'ok': True, 'updated_at': design.updated_at.isoformat(),
                         'design': sanitized})