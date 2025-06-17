from djoser.email import ActivationEmail, ConfirmationEmail, PasswordResetEmail, PasswordChangedConfirmationEmail
from django.conf import settings

class CustomActivationEmail(ActivationEmail):
    template_name = "email/activation.html"

    def get_context_data(self):
        context = super().get_context_data()
        context['site_name'] = settings.SITE_NAME
        return context

class CustomConfirmationEmail(ConfirmationEmail):
    template_name = "email/confirmation.html"

    def get_context_data(self):
        context = super().get_context_data()
        context['site_name'] = settings.SITE_NAME
        return context

class CustomPasswordResetEmail(PasswordResetEmail):
    template_name = "email/password_reset.html"

    def get_context_data(self):
        context = super().get_context_data()
        context['site_name'] = settings.SITE_NAME
        return context

class CustomPasswordChangedConfirmationEmail(PasswordChangedConfirmationEmail):
    template_name = "email/password_changed_confirmation.html"

    def get_context_data(self):
        context = super().get_context_data()
        context['site_name'] = settings.SITE_NAME
        return context
