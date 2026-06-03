from rest_framework import viewsets, permissions, filters, status, pagination
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django.contrib.contenttypes.models import ContentType
from .models import (
    User, Machine, Distro, Component, Report, Comment, Vote, DriverFix, HelpGroup
)
from .serializers import (
    UserSerializer, MachineSerializer, DistroSerializer, ComponentSerializer, 
    ReportSerializer, CommentSerializer, VoteSerializer, DriverFixSerializer, 
    HelpGroupSerializer
)

class SmallResultsPagination(pagination.PageNumberPagination):
    page_size = 5
    page_size_query_param = 'limit'
    max_page_size = 20

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['username']

class MachineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Machine.objects.annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    ).order_by('-report_count')
    serializer_class = MachineSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['vendor', 'model_name', 'series']
    pagination_class = SmallResultsPagination

class DistroViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Distro.objects.annotate(
        report_count=Count('reports', filter=Q(reports__status='APPROVED'))
    ).order_by('-report_count')
    serializer_class = DistroSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'version']

class ComponentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'driver']
    pagination_class = SmallResultsPagination

class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.filter(status='APPROVED').select_related(
        'user', 'machine', 'distro', 'component'
    ).prefetch_related(
        'comp_statuses', 'attachments', 'benchmarks'
    ).annotate(
        upvotes=Count('votes', filter=Q(votes__vote_type='UPVOTE')),
        downvotes=Count('votes', filter=Q(votes__vote_type='DOWNVOTE'))
    )
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'upvotes']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def vote(self, request, pk=None):
        report = self.get_object()
        vote_type = request.data.get('vote_type')
        if vote_type not in ['UPVOTE', 'DOWNVOTE']:
            return Response({'error': 'Invalid vote type'}, status=status.HTTP_400_BAD_REQUEST)
        
        content_type = ContentType.objects.get_for_model(Report)
        vote, created = Vote.objects.update_or_create(
            user=request.user,
            content_type=content_type,
            object_id=report.id,
            defaults={'vote_type': vote_type}
        )
        return Response({'status': 'voted', 'vote_type': vote_type})

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class DriverFixViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DriverFix.objects.filter(status='ACCEPTED')
    serializer_class = DriverFixSerializer

class HelpGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HelpGroup.objects.filter(status='OPEN')
    serializer_class = HelpGroupSerializer
