import base64
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path
from django.views.decorators.http import require_POST
from django.utils import timezone
from game import models as m
from .runtime import package_mode, assign_review_player
from .package_validation import PackageError
from .package_preview import preview_package
from .package_service import apply_package, league_started, source
from .issue_lifecycle import refresh_lock


def creator(fn):
    @login_required
    @wraps(fn)
    def guarded(request, *args, **kwargs):
        if not package_mode() or not (request.user.is_staff or request.user.is_superuser):
            return HttpResponseForbidden("Nur Creator im Paketmodus.")
        return fn(request, *args, **kwargs)
    return guarded


@creator
def hub(request):
    issues = m.ImportIssue.objects.select_related("club", "club__league", "resolved_by").order_by(
        "resolution_status", "severity", "club__name", "pk")
    if request.GET.get("league"):
        issues = issues.filter(club__league_id=request.GET["league"])
    if request.GET.get("club"):
        issues = issues.filter(club_id=request.GET["club"])
    if request.GET.get("severity") in ("info", "player_lock", "blocking"):
        issues = issues.filter(severity=request.GET["severity"])
    return render(request, "game/package_hub.html", dict(
        leagues=m.League.objects.order_by("name"), clubs=m.Club.objects.order_by("name"),
        issues=issues, success=request.GET.get("success", ""), error=request.GET.get("error", "")))


@creator
@require_POST
def preview(request):
    try:
        upload = request.FILES["package"]
        if upload.size > 10 * 1024 * 1024:
            raise PackageError("Paket zu groß (maximal 10 MB).")
        raw = upload.read()
        league = get_object_or_404(m.League, pk=request.POST["league"])
        result = preview_package(raw, league)
        token = signing.dumps(dict(zip=base64.b64encode(raw).decode(), league=league.pk,
            user=request.user.pk, baseline=result["baseline"], guard=result["guard"]),
            salt="club-package-preview", compress=True)
        return render(request, "game/package_preview.html",
                      dict(preview=result, token=token, league=league,
                           issue_balance=result["issue_balance"], changes=result["changes"],
                           missing_images=result["missing_images"],
                           players_to_review=result["players_to_review"]))
    except (PackageError, KeyError, ValueError) as exc:
        return HttpResponseBadRequest(str(exc))


@creator
@require_POST
def confirm(request):
    try:
        payload = signing.loads(request.POST["token"], salt="club-package-preview", max_age=1800)
        if payload["user"] != request.user.pk:
            return HttpResponseForbidden()
        raw = base64.b64decode(payload["zip"], validate=True)
        with transaction.atomic():
            league = m.League.objects.select_for_update().get(pk=payload["league"])
            current = preview_package(raw, league)
            if current["baseline"] != payload["baseline"] or current["guard"] != payload.get("guard"):
                return HttpResponseBadRequest("Datenstand geändert. Bitte Vorschau neu öffnen.")
            result = apply_package(raw, league, user=request.user)
        from django.urls import reverse
        return redirect(reverse("package_creator:hub") + "?success=" +
                        ("Unverändert" if result["unchanged"] else "Paket bestätigt"))
    except (signing.BadSignature, PackageError, KeyError, ValueError, m.League.DoesNotExist) as exc:
        return HttpResponseBadRequest(str(exc))


@creator
@require_POST
def league(request):
    name = request.POST.get("name", "").strip()
    country = request.POST.get("country", "").strip()
    if not name or not country or len(name) > 100 or len(country) > 100:
        return HttpResponseBadRequest("Name und Land erforderlich.")
    m.League.objects.create(name=name, country=country,
                           is_playable=request.POST.get("is_playable") in ("1", "on", "true"))
    return redirect("package_creator:hub")


@creator
@require_POST
def issue(request, pk):
    with transaction.atomic():
        row = get_object_or_404(m.ImportIssue.objects.select_for_update().select_related("club"), pk=pk)
        if league_started(row.club.league) and not (
                row.entity == "club_reference" and row.field == "tm_id" and request.POST.get("action") in ("value", "link")):
            return HttpResponseBadRequest("Nach Ligastart ist diese Nachpflege gesperrt.")
        action = request.POST.get("action")
        player = m.Player.objects.filter(transfermarkt_id=row.entity_ref.removeprefix("tm:")).first() if row.entity == "player" and row.entity_ref.startswith("tm:") else None
        if action == "resolve":
            if row.severity == "player_lock":
                return HttpResponseBadRequest("Einzelsperren schließen sich ausschließlich aus dem Datenstand.")
        elif action == "review":
            if not player or row.field != "review_pool":
                return HttpResponseBadRequest("Kein Prüfpool-Eintrag.")
            assign_review_player(player, row.club, issue=row, user=request.user)
        elif action in ("value", "link"):
            value = row.proposed_tm_id if action == "link" else request.POST.get("value", "").strip()
            numeric = row.field.startswith(("ids.", "ratings.", "stands.", "totals.")) or row.field in (
                "tm_id", "market_value_eur", "height_cm", "founded_year")
            if numeric:
                try:
                    value = int(value)
                    if value < 0 or (row.field.startswith("ids.") or row.field == "tm_id") and value == 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    return HttpResponseBadRequest("Gültige nichtnegative Zahl / positive ID erforderlich.")
            if row.field.startswith("ids."):
                if row.entity not in ("player", "club"):
                    return HttpResponseBadRequest("Diese Gegenstandsart hat keine direkte ID-Nachpflege.")
                provider = row.field.split(".")[1]
                codes = {"fmi": "FM", "tm": "TM", "cmtracker": "CMTRACKER", "api_football": "API_FOOTBALL"}
                if provider not in codes:
                    return HttpResponseBadRequest("Unbekannte Quelle.")
                table = m.PlayerExternalId if player else m.ClubExternalId
                owner = {"player": player} if player else {"club": row.club}
                ds = source(codes[provider])
                conflicts = table.objects.filter(source=ds, external_id=str(value))
                if player:
                    conflicts = conflicts.filter(identity_kind="spieler")
                if conflicts.exclude(**owner).exists():
                    return HttpResponseBadRequest("ID gehört bereits einer anderen Identität.")
                table.objects.update_or_create(**owner, source=ds,
                    defaults=dict(external_id=str(value), status="von_hand", checked_at=timezone.now().date()))
                target = player or row.club
                mirror = {"fmi": "fm_inside_id", "tm": "transfermarkt_id",
                          "cmtracker": "cmtracker_id", "api_football": "api_football_id"}[provider]
                setattr(target, mirror, value)
                target.save(update_fields=[mirror])
            elif row.entity == "club_reference" and row.field == "tm_id":
                name = row.entity_ref
                reference = m.Club.objects.filter(transfermarkt_id=value).first()
                m.PlayerMarketValueSnapshot.objects.filter(club_original_name=name, club_tm_id__isnull=True).update(club_tm_id=value, club=reference)
                m.PlayerTransferHistory.objects.filter(from_original_name=name, from_tm_id__isnull=True).update(from_tm_id=value, from_club=reference)
                m.PlayerTransferHistory.objects.filter(to_original_name=name, to_tm_id__isnull=True).update(to_tm_id=value, to_club=reference)
                m.ClubRecord.objects.filter(club=row.club, opponent_name=name, opponent_tm_id__isnull=True).update(opponent_tm_id=value, opponent_club=reference)
                row.external_reference = dict(row.external_reference, tm_id=value, status="von_hand")
            elif player and row.field.startswith("ratings."):
                parts = row.field.split(".")
                codes = {"fminside": "FM", "cmtracker": "CMTRACKER"}
                if len(parts) != 3 or parts[1] not in codes or parts[2] not in ("rating", "potential") or value > 100:
                    return HttpResponseBadRequest("Quellrating/Potenzial muss zwischen 0 und 100 liegen.")
                rating = m.PlayerSourceRating.objects.filter(player=player, source=codes[parts[1]]).first()
                if rating is None:
                    return HttpResponseBadRequest("Ohne Quellblock bitte neues Paket liefern.")
                setattr(rating, parts[2], value)
                rating.save()
                potentials = list(player.source_ratings.exclude(potential__isnull=True).values_list("potential", flat=True))
                player.potential = max(potentials) if potentials else None
                player.save(update_fields=["potential"])
                from game.strength_service import compute_strength_for_player
                result = compute_strength_for_player(player)
                if result["computable"]:
                    m.PlayerStrengthProfile.objects.update_or_create(player=player,
                        defaults=dict(base_strength=result["base_strength"]))
            elif player and row.field == "market_value_eur":
                from decimal import Decimal
                player.market_value = Decimal(value)
                player.salary_per_match = Decimal(value) / 1_000_000 * 5000
                player.save(update_fields=["market_value", "salary_per_match"])
                m.PlayerMarketValueSnapshot.objects.get_or_create(player=player, origin="real",
                    source_row_key=f"manual-{row.pk}-{value}",
                    defaults=dict(source=source("MANUAL"), recorded_at=row.package.collected_at.date(),
                        value_eur=value, notes="Handnachpflege, kein recherchierter TM-Wert.",
                        package=row.package, update_current=False))
            elif row.entity == "club" and row.field.startswith("colors."):
                import re
                if row.field not in ("colors.primary", "colors.secondary") or not re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)):
                    return HttpResponseBadRequest("Farbwert als #RRGGBB erforderlich.")
                field = "color_" + row.field.split(".")[1]
                setattr(row.club, field, value)
                row.club.save(update_fields=[field])
            elif row.entity == "club" and row.field in ("name", "short_name", "official_name", "motto", "nickname", "founded_year"):
                if isinstance(value, str) and (not value or len(value) > 200):
                    return HttpResponseBadRequest("Wert fehlt oder ist zu lang.")
                setattr(row.club, row.field, value)
                row.club.save(update_fields=[row.field])
            elif row.entity == "club" and row.field.startswith("stands."):
                parts = row.field.split(".")
                sides = {"N": "nord", "E": "ost", "S": "sued", "W": "west"}
                if len(parts) != 3 or parts[1] not in sides or parts[2] not in ("standing", "seating", "vip"):
                    return HttpResponseBadRequest("Unbekanntes Kapazitätsfeld.")
                stadium = m.Stadium.objects.get(club=row.club)
                field = sides[parts[1]] + "_" + parts[2]
                setattr(stadium, field, value)
                setattr(stadium, "real_" + field, value)
                stadium.save(update_fields=[field, "real_" + field])
            else:
                return HttpResponseBadRequest("Dieser Quellwert benötigt ein neues Paket.")
            row.manual_value = value
        else:
            return HttpResponseBadRequest("Unbekannte Aktion.")
        if row.severity != "player_lock":
            row.resolution_status = "resolved"
            row.resolved_at = timezone.now()
            row.resolved_by = request.user
        row.save()
        if player:
            refresh_lock(player)
    return redirect("package_creator:hub")


app_name = "package_creator"
@creator
@require_POST
def images(request):
    from .package_preview import image_gaps
    from .issue_lifecycle import reconcile
    with transaction.atomic():
        club = get_object_or_404(m.Club.objects.select_for_update(), pk=request.POST.get("club"))
        run = m.SourceImportRun.objects.filter(club=club, status="applied").order_by("-pk").first()
        if not run:
            return HttpResponseBadRequest("Kein bestätigtes Paket für diesen Verein.")
        reconcile(run, image_gaps(run.package_data), field="image")
    return redirect("package_creator:hub")


urlpatterns = [
    path("", hub, name="hub"), path("preview/", preview, name="preview"),
    path("confirm/", confirm, name="confirm"), path("league/", league, name="league"),
    path("issues/<int:pk>/", issue, name="issue"),
    path("images/", images, name="images"),
]
