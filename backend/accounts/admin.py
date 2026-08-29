from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'is_active', 'is_staff', 'created_at')
    search_fields = ('email', 'username')
    list_filter = ('is_active', 'is_staff', 'created_at')
    ordering = ('-created_at',)
