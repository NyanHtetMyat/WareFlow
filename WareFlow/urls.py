"""
WareFlow Root URL Configuration
────────────────────────────────
This file only delegates URLs to the correct app.
All actual URL patterns live inside each app's own urls.py.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ── Django built-in admin (for development/debugging only) ───────────────
    path('admin/', admin.site.urls),

    # ── WareFlow apps ─────────────────────────────────────────────────────────
    # accounts handles login, logout, and user management
    path('', include('accounts.urls')),

    # warehouse handles inventory, products, suppliers, locations, adjustments
    path('warehouse/', include('warehouse.urls')),

    # reports handles dashboards, KPIs, charts, low-stock reports
    path('reports/', include('reports.urls')),

    # audit handles audit log viewing and filtering
    path('audit/', include('audit.urls')),
]

# ── Serve media files during development ─────────────────────────────────────
# In production, the web server (Nginx/Apache) handles this instead.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)