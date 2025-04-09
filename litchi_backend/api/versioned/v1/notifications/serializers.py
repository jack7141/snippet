from rest_framework import serializers
from api.bases.notifications.models import Notification, Subscribe, Topic, Device


class NotificationSerializer(serializers.ModelSerializer):
    protocol = serializers.CharField(source='get_protocol_display', help_text='전송 방법')
    topic = serializers.StringRelatedField(help_text='전송 주제')

    class Meta:
        model = Notification
        fields = ('protocol', 'topic', 'title', 'message', 'status', 'created_at')


class NotificationCreateSerializer(serializers.ModelSerializer):
    register = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Notification
        fields = ('protocol', 'topic', 'title', 'message', 'register', 'user')


class SubscribeSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='get_type_display')
    topics = serializers.StringRelatedField(many=True)
    email = serializers.SlugRelatedField(source='user', slug_field='email', read_only=True)

    class Meta:
        model = Subscribe
        fields = '__all__'


class NoAuthSubscribeSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='get_type_display', read_only=True, help_text='프로토콜 이름')
    topics = serializers.StringRelatedField(many=True, read_only=True, help_text='구독 주제 이름')

    class Meta:
        model = Subscribe
        fields = ('type', 'topics',)


class SubscribeCreateSerializer(serializers.ModelSerializer):
    protocol = serializers.CharField(source='type', write_only=True)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Subscribe
        fields = ('protocol', 'topics', 'user')
        extra_kwargs = {
            'topics': {'write_only': True},
        }


class SubscribeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscribe
        fields = ('topics',)


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = '__all__'


class DeviceSerializer(serializers.ModelSerializer):
    email = serializers.SlugRelatedField(source='user', slug_field='email', read_only=True)

    class Meta:
        model = Device
        exclude = ('user',)


class DeviceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('registration_id',)
        extra_kwargs = {
            'registration_id': {'write_only': True}
        }
