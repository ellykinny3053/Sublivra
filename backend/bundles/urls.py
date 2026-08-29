"""
URL patterns for bundles and playlists.
"""
from django.urls import path
from .views import (
    BundleListCreateView, BundleDetailView,
    BundleAddTrackView, BundleRemoveTrackView, BundleExportView,
    PlaylistListCreateView, PlaylistDetailView,
    PlaylistAddTrackView, PlaylistRemoveTrackView,
    PlaylistReorderView, PlaylistExportView,
)

app_name = 'bundles'

urlpatterns = [
    # Bundles (Put specific subpaths before <int:pk>/)
    path('', BundleListCreateView.as_view(), name='bundle-list'),
    path('<int:pk>/export/', BundleExportView.as_view(), name='bundle-export'),
    path('<int:pk>/tracks/', BundleAddTrackView.as_view(), name='bundle-add-track'),
    path('<int:pk>/tracks/<int:track_id>/', BundleRemoveTrackView.as_view(), name='bundle-remove-track'),
    path('<int:pk>/', BundleDetailView.as_view(), name='bundle-detail'),

    # Playlists (Put specific subpaths before <int:pk>/)
    path('playlists/', PlaylistListCreateView.as_view(), name='playlist-list'),
    path('playlists/<int:pk>/export/', PlaylistExportView.as_view(), name='playlist-export'),
    path('playlists/<int:pk>/reorder/', PlaylistReorderView.as_view(), name='playlist-reorder'),
    path('playlists/<int:pk>/tracks/', PlaylistAddTrackView.as_view(), name='playlist-add-track'),
    path('playlists/<int:pk>/tracks/<int:track_id>/', PlaylistRemoveTrackView.as_view(), name='playlist-remove-track'),
    path('playlists/<int:pk>/', PlaylistDetailView.as_view(), name='playlist-detail'),
]
