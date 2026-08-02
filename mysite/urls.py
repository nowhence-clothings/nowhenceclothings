"""
URL configuration for mysite project.
https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from .views import home, about
from .sitemaps import StaticViewSitemap, ProductSitemap

from store.urls import (
    shop_urlpatterns,
    api_urlpatterns,
    account_urlpatterns,
    checkout_urlpatterns,
    legal_urlpatterns,
)

sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
}

urlpatterns = [
    path('manage-store/', admin.site.urls),

    # Top-level pages
    path('', home, name='home'),
    path('about/', about, name='about'),

    # Grouped route sets from store app
    path('shop/', include(shop_urlpatterns)),
    path('api/', include(api_urlpatterns)),
    path('account/', include(account_urlpatterns)),
    path('checkout/', include(checkout_urlpatterns)),
    path('', include(legal_urlpatterns)),

    # SEO
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', lambda r: __import__('django.http', fromlist=['HttpResponse']).HttpResponse(
        'User-agent: *\nAllow: /\nSitemap: https://NowhenceClothings.com/sitemap.xml\n',
        content_type='text/plain'
    )),
]

# Serve media in development. In production, Render can expose the media path directly
# through the app if needed by serving from MEDIA_ROOT via a simple static route.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]

# Custom error handlers (used when DEBUG=False)
handler404 = 'mysite.views.custom_404'
handler500 = 'mysite.views.custom_500'
