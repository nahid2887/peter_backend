from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import User, Profile, OTPVerification, Children
from .utils import send_otp_email


class ChildrenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Children
        fields = ['id', 'name', 'age', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_age(self, value):
        if value < 0 or value > 18:
            raise serializers.ValidationError("Age must be between 0 and 18 years.")
        return value


class ProfileSerializer(serializers.ModelSerializer):
    children = ChildrenSerializer(many=True, read_only=True)
    
    class Meta:
        model = Profile
        fields = ['bio', 'phone_number', 'date_of_birth', 'created_at', 'updated_at', 'children']


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    profile_photo = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'profile_photo', 'date_joined', 'profile']
    
    def get_profile_photo(self, obj):
        if obj.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_photo.url)
            return obj.profile_photo.url
        return None


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    profile_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['email', 'full_name', 'password', 'confirm_password', 'profile_photo']

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        profile_photo = validated_data.pop('profile_photo', None)
        
        user = User.objects.create_user(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            password=validated_data['password'],
            profile_photo=profile_photo
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(email=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials.')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must provide email and password.')


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()
    profile_photo = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = ['full_name', 'profile_photo', 'profile']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Convert profile_photo to full URL in response
        if instance.profile_photo:
            request = self.context.get('request')
            if request:
                representation['profile_photo'] = request.build_absolute_uri(instance.profile_photo.url)
            else:
                representation['profile_photo'] = instance.profile_photo.url
        else:
            representation['profile_photo'] = None
        return representation

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        
        # Update user fields
        instance.full_name = validated_data.get('full_name', instance.full_name)
        instance.profile_photo = validated_data.get('profile_photo', instance.profile_photo)
        instance.save()
        
        # Update profile fields
        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        
        return instance


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address.")
        return value

    def save(self):
        email = self.validated_data['email']
        
        # Delete any existing OTPs for this email
        OTPVerification.objects.filter(email=email, purpose='password_reset').delete()
        
        # Generate new OTP
        otp = OTPVerification.generate_otp()
        
        # Create OTP record
        otp_record = OTPVerification.objects.create(
            email=email,
            otp=otp,
            purpose='password_reset'
        )
        
        # Send OTP via email
        email_sent = send_otp_email(email, otp, 'password_reset')
        
        if not email_sent:
            raise serializers.ValidationError("Failed to send OTP email. Please try again.")
        
        # Return OTP record with the OTP for testing purposes
        return {
            'otp_record': otp_record,
            'otp': otp,  # Include OTP in response for testing
            'expires_at': otp_record.created_at + timezone.timedelta(minutes=5)
        }


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=4)

    def validate(self, attrs):
        email = attrs.get('email')
        otp = attrs.get('otp')

        try:
            otp_record = OTPVerification.objects.filter(
                email=email,
                otp=otp,
                purpose='password_reset',
                is_verified=False
            ).latest('created_at')
        except OTPVerification.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP or email.")

        if otp_record.is_expired():
            raise serializers.ValidationError("OTP has expired. Please request a new one.")

        # Mark OTP as verified
        otp_record.is_verified = True
        otp_record.save()

        attrs['otp_record'] = otp_record
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=4)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        otp = attrs.get('otp')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError("Passwords don't match.")

        try:
            otp_record = OTPVerification.objects.filter(
                email=email,
                otp=otp,
                purpose='password_reset',
                is_verified=True
            ).latest('created_at')
        except OTPVerification.DoesNotExist:
            raise serializers.ValidationError("Invalid or unverified OTP.")

        if otp_record.is_expired():
            raise serializers.ValidationError("OTP has expired. Please start the password reset process again.")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        attrs['user'] = user
        attrs['otp_record'] = otp_record
        return attrs

    def save(self):
        user = self.validated_data['user']
        otp_record = self.validated_data['otp_record']
        new_password = self.validated_data['new_password']

        # Update user password
        user.set_password(new_password)
        user.save()

        # Delete the used OTP record
        otp_record.delete()

        return user


class UserchangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        user = self.context['request'].user
        if not user.check_password(old_password):
            raise serializers.ValidationError("Old password is incorrect.")

        if new_password != confirm_password:
            raise serializers.ValidationError("New password and confirm password do not match.")

        return attrs

    def update(self, instance, validated_data):
        """
        Update the user's password. `instance` is the User instance provided by the view.
        """
        new_password = validated_data.get('new_password')
        # Set and save the new password
        instance.set_password(new_password)
        instance.save()
        return instance