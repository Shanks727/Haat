"""Small shared helpers: currency formatting, role guard, image upload."""
import os
import uuid
from decimal import Decimal
from functools import wraps

from flask import abort, current_app, request, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

TILE_COLOURS = ["#F5B700", "#3D5A98", "#2F7D5B", "#C8553D", "#6B4E9B", "#1F7A8C"]


def _indian_grouping(whole: str) -> str:
    if len(whole) <= 3:
        return whole
    last3, rest = whole[-3:], whole[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return ",".join(groups + [last3])


def money(value, symbol="₹"):
    """Format a number in Indian style, e.g. 125000 -> ₹1,25,000.00"""
    d = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    sign = "-" if d < 0 else ""
    whole, frac = f"{abs(d):.2f}".split(".")
    return f"{sign}{symbol}{_indian_grouping(whole)}.{frac}"


def tile_colour(category_id):
    return TILE_COLOURS[(category_id or 0) % len(TILE_COLOURS)]


def page_url(page):
    """Build the current URL with a different ?page= value (keeps filters)."""
    args = request.args.to_dict()
    args["page"] = page
    return url_for(request.endpoint, **(request.view_args or {}), **args)


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def safe_next(target):
    """Only allow relative redirects after login (prevents open redirects)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def save_image(file_storage):
    """Save an uploaded product image and return its stored file name."""
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in current_app.config["ALLOWED_IMAGE_EXT"]:
        raise ValueError("Upload a PNG, JPG or WEBP image.")
    name = f"{uuid.uuid4().hex[:12]}_{secure_filename(file_storage.filename)}"
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], name))
    return name
