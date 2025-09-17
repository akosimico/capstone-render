from django import template
from django.urls import reverse
from authentication.utils.tokens import make_dashboard_token

register = template.Library()

@register.simple_tag
def dashboard_link(profile):
    token = make_dashboard_token(profile)
    return reverse("dashboard_signed_with_role", args=[token, profile.role])
