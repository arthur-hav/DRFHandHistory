from django.urls import include, path
from rest_framework import routers
from pokerapp.models import HandHistory
from pokerapp import views

router = routers.DefaultRouter()
router.register(r'hand_history', views.HandHistoryViewSet)
router.register(r'actions', views.ActionViewSet)
router.register(r'seats', views.SeatViewSet)
router.register(r'players', views.PlayerViewSet)
router.register(r'streets', views.StreetViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path(r'player_hands/<player_name>/', views.PlayerHandsView.as_view(), name='player_hands'),
    path(r'player_stats/<player_name>/', views.PlayerStatsView.as_view(), name='player_stats'),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]
