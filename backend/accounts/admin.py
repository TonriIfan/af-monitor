from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import PatientProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Console', {'fields': ('role', 'last_login_ip')}),
    )
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active', 'last_login_ip')


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'phone', 'age', 'sex')

# Register your models here.
