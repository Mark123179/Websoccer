"""Show-Auktion — Creator-Views (TV-Redaktion).

Zugang wie die übrigen Creator-Seiten über staff_member_required.
Hero-Bilder werden serverseitig freigestellt (rembg) und auf eine
Standard-Leinwand normiert; schlägt das fehl, wird das Original
gespeichert und eine Warnung angezeigt (kein stiller Fallback).
"""
import json
from io import BytesIO

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from game.models import Player

from . import service
from .models import ShowAuction, ShowAuctionPreset
from .validator import validate_config

# Leinwand des Hero-Freistellers: Torso bündig am unteren Rand,
# damit alle Podien der Bühne dieselbe Bildunterkante teilen.
HERO_CANVAS = (640, 760)


def _process_hero(uploaded):
    """rembg-Freisteller + Torso-Normierung. Liefert (ContentFile, Warnung|None)."""
    try:
        from PIL import Image
        from rembg import remove as rembg_remove

        raw = uploaded.read()
        cut = rembg_remove(raw)
        img = Image.open(BytesIO(cut)).convert('RGBA')
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        cw, ch = HERO_CANVAS
        scale = min(cw / img.width, ch / img.height)
        img = img.resize(
            (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
            Image.LANCZOS,
        )
        canvas = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
        canvas.paste(img, ((cw - img.width) // 2, ch - img.height), img)
        buf = BytesIO()
        canvas.save(buf, 'PNG')
        return ContentFile(buf.getvalue(), name='hero.png'), None
    except Exception as exc:  # rembg fehlt/Modell-Download scheitert etc.
        try:
            uploaded.seek(0)
        except Exception:
            pass
        return (
            ContentFile(uploaded.read(), name=uploaded.name or 'hero.png'),
            f'Freisteller nicht verfügbar ({exc.__class__.__name__}) — Original gespeichert.',
        )


@staff_member_required
def creator_auctions(request):
    auctions = (ShowAuction.objects
                .select_related('player', 'preset', 'winner_club')
                .order_by('-created_at')[:100])
    presets = ShowAuctionPreset.objects.all()
    return render(request, 'showauction/creator.html', {
        'auctions': auctions,
        'presets': presets,
        'nav_active': 'showauktion',
    })


@staff_member_required
def creator_player_search(request):
    """Harte Vereinslose für die Auktions-Anlage (kein Scouting-Pool,
    kein Raum; auction_reserved ist ausdrücklich der Show-Kanal)."""
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'ok': True, 'results': []})
    spieler = (Player.objects
               .filter(club__isnull=True)
               .exclude(pool_status__in=[Player.POOL_STATUS_SCOUTABLE,
                                         Player.POOL_STATUS_SHOW_AUCTION,
                                         Player.POOL_STATUS_UNAVAILABLE])
               .filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
               .order_by('-market_value')[:20])
    results = [{
        'id': p.pk,
        'name': p.full_name,
        'alter': p.age,
        'position': p.position or '',
        'mw': (int(p.market_value) if p.market_value is not None else None),
    } for p in spieler]
    return JsonResponse({'ok': True, 'results': results})


@staff_member_required
def creator_auction_new(request):
    presets = ShowAuctionPreset.objects.filter(is_active=True)
    if request.method == 'POST':
        preset = get_object_or_404(ShowAuctionPreset, pk=request.POST.get('preset_id'))
        player = get_object_or_404(Player, pk=request.POST.get('player_id'))
        conditions = None
        cond_raw = (request.POST.get('conditions_json') or '').strip()
        if cond_raw:
            try:
                conditions = json.loads(cond_raw)
                if not isinstance(conditions, list):
                    raise ValueError
            except ValueError:
                messages.error(request, 'Teilnahmebedingungen: ungültiges JSON (Liste erwartet).')
                return redirect('showauction_creator_new')
        overrides = None
        over_raw = (request.POST.get('config_overrides_json') or '').strip()
        if over_raw:
            try:
                overrides = json.loads(over_raw)
                if not isinstance(overrides, dict):
                    raise ValueError
            except ValueError:
                messages.error(request, 'Config-Overrides: ungültiges JSON (Objekt erwartet).')
                return redirect('showauction_creator_new')
        try:
            auction = service.create_auction(
                player=player,
                preset=preset,
                created_by=request.user,
                config_overrides=overrides,
                conditions=conditions,
                color_hex=(request.POST.get('color_hex') or '').strip() or None,
                rules_text=(request.POST.get('rules_text') or None),
            )
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect('showauction_creator_new')
        except service.AuctionError as exc:
            messages.error(request, str(exc))
            return redirect('showauction_creator_new')
        messages.success(request, f'Auktion #{auction.pk} als Entwurf angelegt — Spieler ist im Raum.')
        return redirect('showauction_creator_edit', pk=auction.pk)
    return render(request, 'showauction/creator_new.html', {
        'presets': presets,
        'nav_active': 'showauktion',
    })


@staff_member_required
def creator_auction_edit(request, pk):
    a = get_object_or_404(
        ShowAuction.objects.select_related('player', 'preset', 'winner_club'),
        pk=pk,
    )
    bids = a.bids.select_related('club').order_by('-updated_at')[:30]
    return render(request, 'showauction/creator_edit.html', {
        'a': a,
        'bids': bids,
        'cfg_pretty': json.dumps(a.config_snapshot, indent=2, ensure_ascii=False),
        'conditions_pretty': json.dumps(a.conditions or [], indent=2, ensure_ascii=False),
        'nav_active': 'showauktion',
    })


@staff_member_required
@require_POST
def creator_auction_action(request, pk):
    a = get_object_or_404(ShowAuction, pk=pk)
    action = request.POST.get('action') or ''
    try:
        if action == 'schedule':
            raw = (request.POST.get('starts_at') or '').strip()
            starts_at = parse_datetime(raw)
            if starts_at is None:
                raise service.AuctionError('Startzeitpunkt unlesbar (Format JJJJ-MM-TTTHH:MM).')
            if timezone.is_naive(starts_at):
                starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
            service.schedule_auction(a, starts_at)
            messages.success(request, f'Auktion #{a.pk} terminiert.')
        elif action == 'start_now':
            service.start_auction_now(a)
            messages.success(request, f'Auktion #{a.pk} ist LIVE.')
        elif action == 'cancel':
            service.cancel_auction(a)
            messages.success(request, f'Auktion #{a.pk} abgebrochen — Spieler hat den Raum verlassen.')
        elif action == 'upload_hero':
            up = request.FILES.get('hero_image')
            if not up:
                raise service.AuctionError('Keine Bilddatei übertragen.')
            content, warnung = _process_hero(up)
            a.hero_image.save(content.name, content, save=True)
            if warnung:
                messages.warning(request, warnung)
            else:
                messages.success(request, 'Hero-Bild freigestellt und gespeichert.')
        elif action == 'upload_logo':
            up = request.FILES.get('media_logo')
            if not up:
                raise service.AuctionError('Keine Bilddatei übertragen.')
            # Medienlogos werden NIE freigestellt (dunkle Trägerfläche, Spec §10)
            a.media_logo.save(up.name, up, save=True)
            messages.success(request, 'Medienlogo gespeichert.')
        elif action == 'update_meta':
            color = (request.POST.get('color_hex') or '').strip()
            if color:
                a.color_hex = color
            a.rules_text = request.POST.get('rules_text', a.rules_text)
            a.save(update_fields=['color_hex', 'rules_text', 'updated_at'])
            messages.success(request, 'Darstellung aktualisiert.')
        else:
            messages.error(request, f'Unbekannte Aktion: {action!r}')
    except service.AuctionError as exc:
        messages.error(request, str(exc))
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)
    return redirect('showauction_creator_edit', pk=a.pk)


@staff_member_required
def creator_presets(request):
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        slug = (request.POST.get('slug') or '').strip()
        if not name or not slug:
            messages.error(request, 'Name und Slug sind Pflicht.')
            return redirect('showauction_creator_presets')
        if ShowAuctionPreset.objects.filter(slug=slug).exists():
            messages.error(request, f'Slug „{slug}" ist bereits vergeben.')
            return redirect('showauction_creator_presets')
        preset = ShowAuctionPreset.objects.create(
            name=name, slug=slug,
            color_hex=(request.POST.get('color_hex') or '#ffd400').strip(),
            config={},
            is_active=False,
        )
        messages.success(request, f'Preset „{name}" angelegt — Achsen jetzt konfigurieren.')
        return redirect('showauction_creator_preset_edit', pk=preset.pk)
    presets = ShowAuctionPreset.objects.all()
    return render(request, 'showauction/creator_presets.html', {'presets': presets})


@staff_member_required
def creator_preset_edit(request, pk):
    preset = get_object_or_404(ShowAuctionPreset, pk=pk)
    if request.method == 'POST':
        raw = request.POST.get('config_json') or ''
        try:
            config = json.loads(raw)
        except ValueError as exc:
            messages.error(request, f'Config ist kein gültiges JSON: {exc}')
            return redirect('showauction_creator_preset_edit', pk=pk)
        try:
            config = validate_config(config)
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect('showauction_creator_preset_edit', pk=pk)
        preset.name = (request.POST.get('name') or preset.name).strip()
        preset.color_hex = (request.POST.get('color_hex') or preset.color_hex).strip()
        preset.icon = (request.POST.get('icon') or '').strip()
        preset.rules_text = request.POST.get('rules_text', preset.rules_text)
        preset.config = config
        preset.is_active = request.POST.get('is_active') == 'on'
        try:
            preset.sort_order = int(request.POST.get('sort_order') or preset.sort_order)
        except ValueError:
            pass
        preset.save()
        messages.success(request, f'Preset „{preset.name}" gespeichert (Config validiert).')
        return redirect('showauction_creator_presets')
    return render(request, 'showauction/creator_preset_edit.html', {
        'preset': preset,
        'config_pretty': json.dumps(preset.config or {}, indent=2, ensure_ascii=False),
    })
