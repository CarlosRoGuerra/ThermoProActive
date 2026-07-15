from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["nome"]
    list_display = ["email", "nome", "perfil", "is_active", "is_staff"]
    list_filter = ["perfil", "is_active", "is_staff"]
    search_fields = ["nome", "email", "cpf"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identificação", {"fields": ("nome", "perfil", "cpf", "celular", "cargo", "conselho_classe")}),
        ("Vínculo", {"fields": ("empresa", "cliente")}),
        ("Permissões", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nome", "perfil", "password1", "password2"),
        }),
    )
