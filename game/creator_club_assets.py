"""Creator-only writes and read-only previews for club 3D assets."""
import io
import os
import re
import tempfile
from pathlib import Path

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.staticfiles.finders import BaseFinder
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, UnidentifiedImageError

from .asset_urls import assets_root
from .models import Club


KIT_TYPES = (('home', 'Home'), ('away', 'Away'), ('third', 'Third'))
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_TEXTURE_PIXELS = 4096 * 4096
ORIGINAL_ROOT = Path(__file__).resolve().parents[1] / (
    'stadium_editor/static/stadium_editor/dortmund_original'
)
TEXTURE_PATTERN = re.compile(r'game/images/3dkits/([1-9]\d*_(?:home|away|third)\.png)\Z')


def texture_file(fmi_id, kit_type):
    if not fmi_id or kit_type not in dict(KIT_TYPES):
        raise ValueError('Eine FMI-ID und ein gültiger Trikottyp sind erforderlich.')
    return Path(assets_root()) / '3dkits' / f'{int(fmi_id)}_{kit_type}.png'


class ThreeDKitFinder(BaseFinder):
    """Expose durable uploads through the requested /static/ URL in development.

    Production nginx aliases the same URL directly to ASSETS_ROOT/3dkits.
    Do not collect these mutable uploads into the build's static snapshot.
    """
    def find(self, path, find_all=False, **kwargs):
        match = TEXTURE_PATTERN.fullmatch(path)
        result = None
        if match:
            candidate = Path(assets_root()) / '3dkits' / match[1]
            if candidate.is_file():
                result = str(candidate)
        return ([result] if result else []) if find_all or kwargs.get('all') else result

    def list(self, ignore_patterns):
        return iter(())


def _png_bytes(upload):
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValueError('Die PNG-Datei darf höchstens 8 MB groß sein.')
    data = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError('Die PNG-Datei darf höchstens 8 MB groß sein.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != 'PNG':
                raise ValueError('Bitte eine echte PNG-Textur hochladen.')
            width, height = image.size
            if width * height > MAX_TEXTURE_PIXELS or max(width, height) > 8192:
                raise ValueError('Die Textur darf höchstens 16 Megapixel und 8192 Pixel pro Seite haben.')
            if getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Animierte PNG-Dateien sind keine Trikottexturen.')
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            output = io.BytesIO()
            # Preserve texture layout, dimensions and alpha; never crop or resize.
            image.convert('RGBA').save(output, format='PNG')
            encoded = output.getvalue()
        if len(encoded) > MAX_UPLOAD_BYTES:
            raise ValueError('Die gespeicherte PNG-Textur wäre größer als 8 MB.')
        return encoded
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError('Die Datei ist keine lesbare, vollständige PNG-Textur.') from exc


def save_texture(upload, target):
    encoded = _png_bytes(upload)  # Validate before touching any existing texture.
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.upload-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)  # nginx must be able to read the shared asset mount.
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def original_available(club):
    return club.fm_inside_id == 907 and all(
        (ORIGINAL_ROOT / filename).is_file() for filename in ('manifest.json', 'geometry.bin')
    )


def creator_asset_context(club, stadium):
    from stadium_editor.models import StadiumGeometry

    kits = []
    for kind, label in KIT_TYPES:
        path = static(f'game/images/3dkits/{club.fm_inside_id}_{kind}.png') if club.fm_inside_id else ''
        file = texture_file(club.fm_inside_id, kind) if club.fm_inside_id else None
        uploaded = bool(file and file.is_file())
        kits.append({
            'type': kind, 'label': label, 'path': path, 'uploaded': uploaded,
            'url': f'{path}?v={file.stat().st_mtime_ns}' if uploaded else '',
        })
    geometry = StadiumGeometry.objects.filter(stadium=stadium).first() if stadium else None
    models = []
    for mode, label, available, message in (
        ('original', 'Original', original_available(club), 'Noch kein Original-3D-Modell hinterlegt.'),
        ('current', 'Aktuell', bool(geometry), 'Noch keine gespeicherte Stadiongeometrie hinterlegt.'),
    ):
        models.append({
            'label': label, 'available': available,
            'viewer_url': reverse('creator_stadium_model', args=[club.pk, mode]) if available else '',
            'message': message,
        })
    return {
        'kits_3d': kits, 'stadium_models': models,
        'stadium_geometry_warning': geometry.last_warning if geometry else '',
    }


@staff_member_required
@require_POST
def creator_upload_3d_kit(request, club_id, kit_type):
    club = get_object_or_404(Club, pk=club_id)
    try:
        target = texture_file(club.fm_inside_id, kit_type)
        upload = request.FILES.get('image')
        if upload is None:
            raise ValueError('Bitte eine PNG-Datei auswählen.')
        save_texture(upload, target)
    except ValueError as exc:
        messages.error(request, str(exc))
    except OSError:
        messages.error(request, 'Die Textur konnte nicht gespeichert werden. Die bisherige Datei bleibt erhalten.')
    else:
        messages.success(request, f'3D-Trikottextur ({dict(KIT_TYPES)[kit_type]}) gespeichert.')
    return redirect(reverse('creator_club_edit', args=[club.pk]) + '?tab=bilder')


@staff_member_required
@require_GET
def creator_stadium_model(request, club_id, mode):
    club = get_object_or_404(Club.objects.select_related('stadium'), pk=club_id)
    stadium = getattr(club, 'stadium', None)
    if mode == 'original':
        if not original_available(club):
            raise Http404('Noch kein Originalmodell hinterlegt.')
    elif mode == 'current':
        from stadium_editor.models import StadiumGeometry
        if not stadium or not StadiumGeometry.objects.filter(stadium=stadium).exists():
            raise Http404('Noch keine gespeicherte Stadiongeometrie hinterlegt.')
    else:
        raise Http404('Unbekannte Modellansicht.')
    return render(request, 'creator/stadium_model.html', {
        'club': club, 'mode': mode,
        'scene_url': reverse('stadium_live_scene', args=[club.pk]),
    })
