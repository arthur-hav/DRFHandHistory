from pokerapp.models import HandHistory, PlayerSeat, PlayerAction, Player
from rest_framework import permissions, viewsets
from rest_framework.views import APIView
from django.http import Http404
from pokerapp.serializers import HandHistorySerializer, PlayerSeatSerializer, PlayerActionSerializer, PlayerSerializer


class HandHistoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = HandHistory.objects.all().order_by('-date_played')
    serializer_class = HandHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

class PlayerSeatViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = PlayerSeat.objects.all()
    serializer_class = PlayerSeatSerializer
    permission_classes = [permissions.IsAuthenticated]

class PlayerActionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = PlayerAction.objects.all()
    serializer_class = PlayerActionSerializer
    permission_classes = [permissions.IsAuthenticated]

class PlayerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    permission_classes = [permissions.IsAuthenticated]
