from rest_framework import serializers


class CodeExecuteSerializer(serializers.Serializer):
    language = serializers.CharField(max_length=50)
    code = serializers.CharField()
    testCases = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(allow_blank=True)
        ),
        required=True,
        min_length=1
    )
    input = serializers.CharField(required=False, allow_blank=True)

class TC(serializers.Serializer):
    code=serializers.CharField()

class ChatbotSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True)
    currentMsg = serializers.CharField()
    history = serializers.ListField(child=serializers.DictField(), required=False)


class VisSer(serializers.Serializer):
    code=serializers.CharField()
    input=serializers.CharField(required=False, allow_blank=True)



class HanSer(serializers.Serializer):
    userId=serializers.CharField()