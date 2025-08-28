from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, Profile, Children, OTPVerification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'full_name', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['email', 'full_name']
    ordering = ['-date_joined']
    readonly_fields = ['date_joined', 'last_login']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'profile_photo')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2'),
        }),
    )
    
    def get_profile_photo(self, obj):
        if obj.profile_photo:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 50%;" />', obj.profile_photo.url)
        return "No photo"
    get_profile_photo.short_description = 'Profile Photo'


class ChildrenInline(admin.TabularInline):
    model = Children
    extra = 0
    fields = ['name', 'age']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_full_name', 'get_email', 'get_children_count', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__full_name', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ChildrenInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('children')
    
    def get_full_name(self, obj):
        return obj.user.full_name
    get_full_name.short_description = 'Full Name'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    
    def get_children_count(self, obj):
        return obj.children.count()
    get_children_count.short_description = 'Children Count'


@admin.register(Children)
class ChildrenAdmin(admin.ModelAdmin):
    list_display = ['name', 'age', 'get_parent', 'created_at']
    list_filter = ['age', 'created_at']
    search_fields = ['name', 'profile__user__full_name', 'profile__user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile__user')
    
    def get_parent(self, obj):
        return obj.profile.user.full_name
    get_parent.short_description = 'Parent'


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'otp', 'purpose', 'is_verified', 'is_expired_status', 'created_at']
    list_filter = ['purpose', 'is_verified', 'created_at']
    search_fields = ['email']
    readonly_fields = ['created_at']
    
    def is_expired_status(self, obj):
        return obj.is_expired()
    is_expired_status.boolean = True
    is_expired_status.short_description = 'Expired'
    
    def has_add_permission(self, request):
        # Prevent manual creation of OTP records
        return False
