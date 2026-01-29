"""
Base classes for tiket workflow steps.
"""

from django.views.generic import CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db import transaction

from ..mixins import AdminRequiredMixin


class WorkflowStepMixin:
    """Base mixin for workflow step views."""
    
    def get_json_response(self, success=True, message="", errors=None, redirect=None):
        """Generate standardized JSON response for AJAX requests."""
        response = {
            'success': success,
            'message': message,
        }
        if errors:
            response['errors'] = errors
        if redirect:
            response['redirect'] = redirect
        return JsonResponse(response)
    
    def is_ajax_request(self):
        """Check if the request is an AJAX request."""
        return self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'


class WorkflowStepCreateView(LoginRequiredMixin, AdminRequiredMixin, WorkflowStepMixin, CreateView):
    """Base create view for workflow steps."""
    
    def form_valid(self, form):
        """Handle form submission with transaction management."""
        try:
            with transaction.atomic():
                response = self.perform_workflow_action(form)
                
                if isinstance(response, JsonResponse):
                    return response
                
                return super().form_valid(form)
        except Exception as e:
            return self.handle_form_error(form, str(e))
    
    def form_invalid(self, form):
        """Handle form validation errors."""
        if self.is_ajax_request():
            return self.get_json_response(
                success=False,
                errors=form.errors
            )
        return super().form_invalid(form)
    
    def perform_workflow_action(self, form):
        """Override in subclasses to implement workflow-specific logic."""
        return None
    
    def handle_form_error(self, form, error_message):
        """Handle errors during form processing."""
        if self.is_ajax_request():
            return self.get_json_response(
                success=False,
                errors={'__all__': [error_message]}
            )
        return self.form_invalid(form)


class WorkflowStepDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """Base detail view for workflow steps."""
    pass
