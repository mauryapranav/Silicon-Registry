from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import (
    User, Machine, Distro, Component, Report, CompStatus, 
    Comment, Vote, Flag, Benchmark, DriverFix, TrustEvent, 
    ReportAttachment, HelpGroup, HelpGroupMembership, 
    HelpGroupMessage, UserMachine, MachineSpec, SpecSuggestion
)

class UserSerializer(serializers.ModelSerializer):
    trust_ratio = serializers.ReadOnlyField()
    needs_moderation = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role_type', 'bio', 'avatar', 
            'positive_score', 'negative_score', 'is_verified', 
            'github_username', 'trust_ratio', 'needs_moderation'
        ]
        read_only_fields = ['positive_score', 'negative_score', 'is_verified']

class MachineSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineSpec
        fields = '__all__'

class MachineSerializer(serializers.ModelSerializer):
    spec = MachineSpecSerializer(read_only=True)
    report_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Machine
        fields = ['id', 'vendor', 'series', 'model_name', 'cpu_family', 'form_factor', 'spec', 'report_count']

class DistroSerializer(serializers.ModelSerializer):
    report_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Distro
        fields = ['id', 'name', 'version', 'kernel_default', 'report_count']

class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = ['id', 'type', 'name', 'driver']

class CompStatusSerializer(serializers.ModelSerializer):
    component_details = ComponentSerializer(source='component', read_only=True)

    class Meta:
        model = CompStatus
        fields = ['id', 'report', 'component', 'component_details', 'status', 'notes']

class ReportAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportAttachment
        fields = ['id', 'file', 'file_type', 'original_filename', 'uploaded_at']

class BenchmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Benchmark
        fields = '__all__'

class ReportSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    machine_details = MachineSerializer(source='machine', read_only=True)
    distro_details = DistroSerializer(source='distro', read_only=True)
    component_details = ComponentSerializer(source='component', read_only=True)
    comp_statuses = CompStatusSerializer(many=True, read_only=True)
    attachments = ReportAttachmentSerializer(many=True, read_only=True)
    benchmarks = BenchmarkSerializer(many=True, read_only=True)
    
    upvotes = serializers.IntegerField(read_only=True)
    downvotes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'user', 'user_details', 'machine', 'machine_details', 
            'distro', 'distro_details', 'component', 'component_details',
            'report_type', 'title', 'description', 'boot_status', 
            'kernel_version', 'status', 'compatibility_score', 
            'created_at', 'updated_at', 'comp_statuses', 'attachments', 
            'benchmarks', 'upvotes', 'downvotes'
        ]
        read_only_fields = ['status', 'compatibility_score']

class CommentSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'user_details', 'report', 'content', 'is_verified', 'created_at']

class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = '__all__'

class DriverFixSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverFix
        fields = '__all__'

class HelpGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = HelpGroup
        fields = '__all__'
