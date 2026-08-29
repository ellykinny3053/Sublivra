"""
Serializers for user registration, profile, and authentication responses.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'password_confirm')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for viewing/updating user profile."""
    track_count = serializers.SerializerMethodField()
    bundle_count = serializers.SerializerMethodField()
    playlist_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'bio', 'avatar',
            'track_count', 'bundle_count', 'playlist_count',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'email', 'created_at', 'updated_at')

    def get_track_count(self, obj):
        return obj.tracks.count() if hasattr(obj, 'tracks') else 0

    def get_bundle_count(self, obj):
        return obj.bundles.count() if hasattr(obj, 'bundles') else 0

    def get_playlist_count(self, obj):
        return obj.playlists.count() if hasattr(obj, 'playlists') else 0


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
