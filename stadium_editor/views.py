import json
from copy import deepcopy
from zipfile import BadZipFile

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from game.models import Club, Stadium, StadiumExpansion
from game.stadium_costs import max_kapazitaet
from game.views import build_game_header, current_manager_club

from .capacity import distribute_capacities
from .blueprints.v2.dortmund_preview import load_preview
from .image_validation import InvalidImageData, normalize_design_payload
from .models import StadiumDesign, StadiumGeometry
from .contracts import geometry_blocks, visible_blocks
from .surroundings import with_dortmund_mapped_trees
from .live_scene import (
    LiveSceneError,
    build_live_scene,
    standard_design_for_geometry,
)


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
    return with_dortmund_mapped_trees(payload, club_id=stadium.club_id)


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
    pending_expansions = (
        StadiumExpansion.objects.filter(stadium=stadium, applied=False)
        .order_by('completes_at', 'pk')
    )
    return render(request, 'stadium_editor/editor.html', {
        'stadium': stadium,
        'geometry': geometry,
        'design': design.design if design else {},
        'is_editor_admin': bool(request.user.is_staff),
        'is_dortmund_editor': stadium.club_id == 3,
        'preview_capacity_limit': max_kapazitaet() if stadium.club_id == 3 else 150000,
        'pending_expansions': pending_expansions,
        'completed_expansion_count': StadiumExpansion.objects.filter(
            stadium=stadium, applied=True,
        ).count() if stadium.club_id == 3 else 0,
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
    return JsonResponse(design.design if design else {})


@login_required(login_url='/auth/login/')
@require_GET
def stadium_editor_visible_design(request):
    stadium = _owned_stadium(request)
    if not stadium:
        return JsonResponse({'error': 'Stadion nicht gefunden.'}, status=404)
    design = StadiumDesign.objects.filter(stadium=stadium).first()
    if not design:
        return JsonResponse({})
    payload = deepcopy(design.design)
    payload['blocks'] = visible_blocks(payload, design.blickrichtung)
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
    return JsonResponse({'ok': True, 'updated_at': design.updated_at.isoformat()})


@require_GET
def stadium_live_scene(request, club_id):
    try:
        club = Club.objects.select_related('stadium').get(pk=club_id)
        stadium = club.stadium
    except (Club.DoesNotExist, Stadium.DoesNotExist):
        return JsonResponse({'error': 'Stadion nicht gefunden.'}, status=404)
    try:
        geometry_row = StadiumGeometry.objects.get(stadium=stadium)
        geometry = deepcopy(geometry_row.geometry)
        if geometry_row.steckbrief:
            geometry['steckbrief'] = deepcopy(geometry_row.steckbrief)
        design = StadiumDesign.objects.filter(stadium=stadium).first()
    except StadiumGeometry.DoesNotExist:
        return JsonResponse({'error': 'Keine Stadion-Geometrie hinterlegt.'}, status=404)
    try:
        design_payload = (
            design.design if design is not None
            else standard_design_for_geometry(
                stadium, _geometry_payload(stadium, geometry))
        )
        payload = build_live_scene(stadium, geometry, design_payload)
    except (LiveSceneError, ValueError) as exc:
        return JsonResponse(
            {'error': str(exc) or 'Ungültige Stadion-Scene.'},
            status=409,
        )
    return JsonResponse(payload)


@require_GET
def stadium_live_mode(request, club_id):
    """Public 2D stadium view backed exclusively by the canonical live scene."""
    try:
        club = Club.objects.select_related('stadium').get(pk=club_id)
        stadium = club.stadium
    except (Club.DoesNotExist, Stadium.DoesNotExist):
        return HttpResponse('Stadion nicht gefunden.', status=404)
    return render(request, 'stadium_editor/live_mode.html', {
        'club': club,
        'stadium': stadium,
        'scene_url': reverse('stadium_live_scene', args=[club.pk]),
    })


@require_GET
def dortmund_preview_scene(request):
    """Review the uploaded scene without touching persisted geometry or designs."""
    try:
        stadium = Stadium.objects.get(club_id=3)
        scene = load_preview()
    except Stadium.DoesNotExist:
        return JsonResponse({'error': 'Dortmunder Stadion nicht gefunden.'}, status=404)
    except (OSError, KeyError, BadZipFile, ValueError) as exc:
        return JsonResponse({'error': f'Vorschauquelle nicht verfügbar: {exc}'}, status=503)
    scene['capacity'] = stadium.capacity_total
    scene['preview'] = True
    response = JsonResponse(scene)
    response['Cache-Control'] = 'no-store'
    return response


@require_GET
def dortmund_preview(request):
    try:
        stadium = Stadium.objects.select_related('club').get(club_id=3)
    except Stadium.DoesNotExist:
        return HttpResponse('Dortmunder Stadion nicht gefunden.', status=404)
    return render(request, 'stadium_editor/live_mode.html', {
        'club': stadium.club,
        'stadium': stadium,
        'scene_url': reverse('dortmund_preview_scene'),
        'preview': True,
        'current_url': reverse('stadium_live_mode', args=[3]),
    })


@require_GET
def dortmund_original_miniature(request):
    """Isolated asset review; no design, capacity or geometry database access."""
    return render(request, 'stadium_editor/dortmund_original_miniature.html')