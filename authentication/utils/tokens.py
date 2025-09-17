from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from authentication.models import UserProfile
from django.contrib import messages

DASHBOARD_SALT = "dashboard.link"

# Time constants
ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7

DEFAULT_MAX_AGE = ONE_WEEK  # 7 days


def make_dashboard_token(profile):
    """
    Create a signed dashboard token for a UserProfile.
    """
    payload = {
        "u": str(profile.user.id),
        "r": profile.role,
        "v": 1,
    }
    return signing.dumps(payload, salt=DASHBOARD_SALT, compress=True)


def parse_dashboard_token(token, max_age=DEFAULT_MAX_AGE):
    """
    Parse a signed dashboard token safely, ensuring max_age is numeric.
    Returns payload dict: {'u': user_id, 'r': role, 'v': version}.
    Raises BadSignature/SignatureExpired if invalid.
    """
    # Ensure max_age is int or None
    if max_age is not None:
        try:
            max_age = int(max_age)
        except (ValueError, TypeError):
            max_age = DEFAULT_MAX_AGE

    return signing.loads(token, salt=DASHBOARD_SALT, max_age=max_age)


def _resolve_profile_from_token(token, max_age=ONE_HOUR):
    """
    Internal helper: returns UserProfile from token. Raises exceptions if invalid.
    """
    payload = parse_dashboard_token(token, max_age=max_age)
    user_id = int(payload["u"])
    role = payload["r"]
    return UserProfile.objects.get(user__id=user_id, role=role)


def verify_user_token(request, token, expected_role=None, max_age=None):
    """
    Verifies a signed dashboard token and returns the corresponding UserProfile
    if valid, else returns None and adds an error message.
    """
    try:
        payload = parse_dashboard_token(token, max_age=max_age)
        user_id = payload["u"]
        token_role = payload["r"]
    except SignatureExpired:
        messages.error(request, "Your session token has expired.")
        return None
    except BadSignature:
        messages.error(request, "Invalid token. Access denied.")
        return None

    # Validate expected role if provided
    if expected_role and token_role != expected_role:
        messages.error(request, "Invalid role for this token.")
        return None

    try:
        profile = UserProfile.objects.get(user__id=user_id, role=token_role)
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found for this token.")
        return None

    if not request.user.is_authenticated or request.user.id != profile.user.id:
        messages.error(request, "This link does not belong to your account.")
        return None

    return profile
